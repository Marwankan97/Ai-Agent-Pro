from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class Bar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self) -> None:
        values = (self.open, self.high, self.low, self.close, self.volume)
        if not all(isfinite(v) for v in values):
            raise ValueError(f"non-finite OHLCV value at {self.timestamp}")
        if self.timestamp < 0 or min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError(f"invalid timestamp or non-positive price at {self.timestamp}")
        if self.volume < 0 or self.high < max(self.open, self.close, self.low):
            raise ValueError(f"invalid high/volume at {self.timestamp}")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError(f"invalid low at {self.timestamp}")


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    momentum_days: int = 90
    volatility_days: int = 30
    target_annual_volatility: float = 0.20
    maximum_exposure: float = 0.65
    maximum_drawdown: float = 0.25
    fee_rate: float = 0.008
    slippage_bps: float = 10.0

    def validate(self) -> None:
        if self.momentum_days < 2 or self.volatility_days < 2:
            raise ValueError("lookback windows must be at least 2")
        if not 0 < self.target_annual_volatility <= 1:
            raise ValueError("target_annual_volatility must be in (0, 1]")
        if not 0 < self.maximum_exposure <= 1:
            raise ValueError("maximum_exposure must be in (0, 1]")
        if not 0 < self.maximum_drawdown < 1:
            raise ValueError("maximum_drawdown must be in (0, 1)")
        if not 0 <= self.fee_rate < 0.1:
            raise ValueError("fee_rate must be in [0, 0.1)")
        if not 0 <= self.slippage_bps <= 500:
            raise ValueError("slippage_bps must be in [0, 500]")

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000.0


@dataclass(frozen=True, slots=True)
class Signal:
    target_exposure: float
    momentum_return: float | None
    annualized_volatility: float | None
    reason: str
