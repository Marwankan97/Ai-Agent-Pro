from __future__ import annotations

from math import isfinite


def update_drawdown_guard(equity: float, peak_equity: float, already_halted: bool,
                          maximum_drawdown: float) -> tuple[float, float, bool]:
    """Independent sticky risk governor; returns (new_peak, drawdown, halted)."""
    if not isfinite(equity) or not isfinite(peak_equity) or equity < 0 or peak_equity <= 0:
        raise ValueError("risk governor received invalid equity")
    if not 0 < maximum_drawdown < 1:
        raise ValueError("maximum_drawdown must be in (0, 1)")
    new_peak = max(peak_equity, equity)
    drawdown = equity / new_peak - 1.0
    halted = bool(already_halted) or drawdown <= -maximum_drawdown
    return new_peak, drawdown, halted


def approve_target(strategy_target: float, halted: bool, maximum_exposure: float) -> float:
    """Clamp strategy output to the independent long-only permission envelope."""
    if not isfinite(strategy_target) or not 0 <= maximum_exposure <= 1:
        raise ValueError("invalid target or exposure permission")
    if halted:
        return 0.0
    return min(maximum_exposure, max(0.0, strategy_target))
