from dataclasses import replace

from pro_agent.backtest import run_backtest
from pro_agent.models import StrategyConfig
from pro_agent.strategy import decide


def test_warmup_produces_cash_signal(synthetic_bars):
    cfg = StrategyConfig(momentum_days=90, volatility_days=30)
    signal = decide(synthetic_bars(90), cfg)
    assert signal.target_exposure == 0
    assert signal.reason.startswith("WARMUP")


def test_positive_trend_is_capped(synthetic_bars):
    cfg = StrategyConfig(momentum_days=30, volatility_days=20, maximum_exposure=0.4)
    signal = decide(synthetic_bars(100, trend=0.004, wobble=0.001), cfg)
    assert 0 <= signal.target_exposure <= 0.4
    assert signal.reason in {"TREND_POSITIVE", "MOMENTUM_NOT_POSITIVE"}


def test_nonpositive_momentum_means_zero_exposure(synthetic_bars):
    bars = synthetic_bars(150, trend=-0.004, wobble=0.0001)
    cfg = StrategyConfig(momentum_days=60, volatility_days=30)
    signal = decide(bars, cfg)
    assert signal.target_exposure == 0
    assert signal.reason == "MOMENTUM_NOT_POSITIVE"


def test_costs_do_not_improve_strategy_returns(synthetic_bars):
    bars = synthetic_bars(360)
    cheap = StrategyConfig(fee_rate=0, slippage_bps=0)
    costly = replace(cheap, fee_rate=0.01, slippage_bps=30)
    a = run_backtest(bars, cheap)["strategy"]["end_equity"]
    b = run_backtest(bars, costly)["strategy"]["end_equity"]
    assert b <= a


def test_backtest_reports_benchmark_and_next_open(synthetic_bars):
    result = run_backtest(synthetic_bars(360), StrategyConfig())
    assert "buy_and_hold" in result
    assert result["assumptions"]["execution"].startswith("signal at close")
    assert result["strategy"]["evaluation_days"] > 0
