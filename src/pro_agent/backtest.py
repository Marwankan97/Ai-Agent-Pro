from __future__ import annotations

from math import sqrt
from statistics import fmean, stdev

from .models import Bar, StrategyConfig
from .strategy import decide
from .risk import approve_target, update_drawdown_guard


def _metrics(equity: list[float], daily_returns: list[float], days: int) -> dict[str, float | int]:
    if not equity or days <= 0:
        raise ValueError("backtest produced no evaluation periods")
    total_return = equity[-1] / equity[0] - 1.0
    cagr = (equity[-1] / equity[0]) ** (365.0 / days) - 1.0 if equity[-1] > 0 else -1.0
    vol = stdev(daily_returns) * sqrt(365.0) if len(daily_returns) > 1 else 0.0
    sharpe = (fmean(daily_returns) * 365.0) / vol if vol > 1e-12 else 0.0
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1.0)
    return {
        "start_equity": equity[0], "end_equity": equity[-1],
        "total_return": total_return, "cagr": cagr,
        "annualized_volatility": vol, "sharpe": sharpe,
        "max_drawdown": max_dd, "evaluation_days": days,
    }


def run_backtest(bars: list[Bar], config: StrategyConfig, initial_cash: float = 500.0) -> dict:
    config.validate()
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    warmup = max(config.momentum_days + 1, config.volatility_days + 1)
    if len(bars) < warmup + 2:
        raise ValueError(f"need at least {warmup + 2} daily bars; received {len(bars)}")

    equity = initial_cash
    peak = initial_cash
    exposure = 0.0
    halted = False
    curve = [equity]
    daily_returns: list[float] = []
    turnover = 0.0
    traded_days = 0
    fee_and_slippage = config.fee_rate + config.slippage_rate
    avg_exposure_sum = 0.0
    periods = 0

    # Signal uses close[i]. It can only be executed at open[i+1], then held
    # from that open to open[i+2]. The last bar is intentionally not an exit.
    for i in range(warmup - 1, len(bars) - 2):
        signal = decide(bars[: i + 1], config)
        target = approve_target(signal.target_exposure, halted, config.maximum_exposure)
        next_open = bars[i + 1].open
        following_open = bars[i + 2].open
        desired_change = abs(target - exposure)
        if desired_change > 1e-10:
            equity *= 1.0 - desired_change * fee_and_slippage
            turnover += desired_change
            traded_days += 1
        exposure = target
        market_return = following_open / next_open - 1.0
        equity *= 1.0 + exposure * market_return
        peak, _drawdown, halted = update_drawdown_guard(
            equity, peak, halted, config.maximum_drawdown
        )
        curve.append(equity)
        daily_returns.append(curve[-1] / curve[-2] - 1.0)
        avg_exposure_sum += exposure
        periods += 1

    strategy_metrics = _metrics(curve, daily_returns, periods)

    # Same execution window and cost convention for a passive, unlevered benchmark.
    benchmark = initial_cash * (1.0 - fee_and_slippage)
    benchmark_curve = [initial_cash, benchmark]
    benchmark_returns: list[float] = []
    first_open = bars[warmup].open
    for j in range(warmup + 1, len(bars)):
        previous = benchmark
        benchmark *= bars[j].open / bars[j - 1].open
        benchmark_curve.append(benchmark)
        benchmark_returns.append(benchmark / previous - 1.0)
    benchmark_metrics = _metrics(benchmark_curve, benchmark_returns, len(benchmark_returns))

    return {
        "strategy": strategy_metrics,
        "buy_and_hold": benchmark_metrics,
        "assumptions": {
            "initial_cash": initial_cash,
            "fee_rate_per_side": config.fee_rate,
            "slippage_bps_per_side": config.slippage_bps,
            "maximum_exposure": config.maximum_exposure,
            "target_annual_volatility": config.target_annual_volatility,
            "momentum_days": config.momentum_days,
            "volatility_days": config.volatility_days,
            "maximum_drawdown_halt": config.maximum_drawdown,
            "execution": "signal at close; execute at next daily open; hold open-to-open",
            "traded_rebalances": traded_days,
            "cumulative_exposure_turnover": turnover,
            "average_exposure": avg_exposure_sum / periods if periods else 0.0,
            "risk_halted_by_end": halted,
            "benchmark_first_open": first_open,
        },
        "equity_curve": curve,
    }
