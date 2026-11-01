from __future__ import annotations

from typing import Any

from .ledger import Ledger
from .market import DAY_SECONDS
from .models import Bar, StrategyConfig
from .strategy import decide
from .risk import approve_target, update_drawdown_guard


def _fill_target(state: dict, open_price: float, target: float, config: StrategyConfig) -> dict:
    cash = float(state["cash"])
    units = float(state["units"])
    equity_at_open = cash + units * open_price
    desired_units = max(0.0, target) * equity_at_open / open_price
    delta = desired_units - units
    fee = 0.0
    slippage_cost = 0.0
    if delta > 1e-14:
        fill_price = open_price * (1.0 + config.slippage_rate)
        quantity = delta
        affordable = cash / (fill_price * (1.0 + config.fee_rate)) if cash > 0 else 0.0
        quantity = min(quantity, affordable)
        notional = quantity * fill_price
        fee = notional * config.fee_rate
        slippage_cost = quantity * (fill_price - open_price)
        cash -= notional + fee
        units += quantity
    elif delta < -1e-14:
        quantity = min(units, -delta)
        fill_price = open_price * (1.0 - config.slippage_rate)
        notional = quantity * fill_price
        fee = notional * config.fee_rate
        slippage_cost = quantity * (open_price - fill_price)
        cash += notional - fee
        units -= quantity
    cash = max(0.0, cash)
    return {
        "cash": cash, "units": units, "fee_paid": fee,
        "slippage_cost": slippage_cost,
        "executed_exposure_at_open": (units * open_price / equity_at_open) if equity_at_open > 0 else 0.0,
    }


def initialize_paper(ledger: Ledger, bars: list[Bar], config: StrategyConfig, initial_cash: float) -> dict:
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    latest = bars[-1]
    signal = decide(bars, config)
    state = {
        "mode": "PAPER_ONLY",
        "cash": float(initial_cash), "units": 0.0,
        "equity": float(initial_cash), "peak_equity": float(initial_cash),
        "drawdown": 0.0, "halted": False,
        "current_exposure": 0.0, "pending_target": signal.target_exposure,
        "last_bar_timestamp": latest.timestamp, "last_close": latest.close,
        "last_signal_reason": signal.reason, "cumulative_fees": 0.0,
        "cumulative_slippage_cost": 0.0,
    }
    ledger.append(
        f"paper:init:{latest.timestamp}", "paper_initialized", latest.timestamp,
        {"initial_cash": initial_cash, "last_closed_bar": latest.timestamp,
         "initial_signal": {
             "target_exposure": signal.target_exposure, "reason": signal.reason,
             "momentum_return": signal.momentum_return,
             "annualized_volatility": signal.annualized_volatility,
         }}, state,
    )
    return state


def process_new_bars(ledger: Ledger, bars: list[Bar], config: StrategyConfig,
                     initial_cash: float = 500.0) -> dict[str, Any]:
    state = ledger.latest_state()
    if state is None:
        state = initialize_paper(ledger, bars, config, initial_cash)
        return {"initialized": True, "processed_bars": 0, "state": state}

    last_ts = int(state["last_bar_timestamp"])
    new_bars = [bar for bar in bars if bar.timestamp > last_ts]
    if not new_bars:
        return {"initialized": False, "processed_bars": 0, "idempotent_noop": True, "state": state}

    all_by_ts = {bar.timestamp: bar for bar in bars}
    for bar in new_bars:
        if bar.timestamp != int(state["last_bar_timestamp"]) + DAY_SECONDS:
            raise ValueError("paper ledger gap detected; refusing to skip candles or infer missing prices")
        fill = _fill_target(state, bar.open, float(state["pending_target"]), config)
        equity = fill["cash"] + fill["units"] * bar.close
        peak, drawdown, halted = update_drawdown_guard(
            equity, float(state["peak_equity"]), bool(state["halted"]),
            config.maximum_drawdown,
        )
        history = [candidate for ts, candidate in all_by_ts.items() if ts <= bar.timestamp]
        signal = decide(history, config)
        next_target = approve_target(signal.target_exposure, halted, config.maximum_exposure)
        state = {
            "mode": "PAPER_ONLY", "cash": fill["cash"], "units": fill["units"],
            "equity": equity, "peak_equity": peak, "drawdown": drawdown,
            "halted": halted,
            "current_exposure": (fill["units"] * bar.close / equity) if equity > 0 else 0.0,
            "pending_target": next_target,
            "last_bar_timestamp": bar.timestamp, "last_close": bar.close,
            "last_signal_reason": "RISK_HALT" if halted else signal.reason,
            "cumulative_fees": float(state["cumulative_fees"]) + fill["fee_paid"],
            "cumulative_slippage_cost": float(state["cumulative_slippage_cost"]) + fill["slippage_cost"],
        }
        event_payload = {
            "bar_timestamp": bar.timestamp, "open": bar.open, "close": bar.close,
            "executed_pending_target": float(fill["executed_exposure_at_open"]),
            "fee_paid": fill["fee_paid"], "slippage_cost": fill["slippage_cost"],
            "signal_target_for_next_open": next_target,
            "signal_reason": state["last_signal_reason"],
        }
        ledger.append(f"paper:bar:{bar.timestamp}", "paper_bar_processed", bar.timestamp, event_payload, state)
    return {"initialized": False, "processed_bars": len(new_bars), "state": state}
