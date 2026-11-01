from __future__ import annotations

from math import log, sqrt
from statistics import stdev

from .models import Bar, Signal, StrategyConfig

TRADING_DAYS = 365.0


def decide(bars: list[Bar], config: StrategyConfig) -> Signal:
    """Close-of-day trend filter plus inverse-volatility target; no future data."""
    config.validate()
    required = max(config.momentum_days + 1, config.volatility_days + 1)
    if len(bars) < required:
        return Signal(0.0, None, None, f"WARMUP:{len(bars)}/{required}")

    closes = [bar.close for bar in bars]
    momentum = closes[-1] / closes[-1 - config.momentum_days] - 1.0
    returns = [log(closes[i] / closes[i - 1]) for i in range(len(closes) - config.volatility_days, len(closes))]
    volatility = stdev(returns) * sqrt(TRADING_DAYS)
    if momentum <= 0:
        return Signal(0.0, momentum, volatility, "MOMENTUM_NOT_POSITIVE")
    if volatility <= 1e-12:
        return Signal(0.0, momentum, volatility, "VOLATILITY_UNDEFINED")
    exposure = min(config.maximum_exposure, config.target_annual_volatility / volatility)
    return Signal(max(0.0, min(config.maximum_exposure, exposure)), momentum, volatility, "TREND_POSITIVE")
