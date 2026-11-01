import pytest

from pro_agent.ledger import Ledger
from pro_agent.models import StrategyConfig
from pro_agent.paper import process_new_bars


def test_ledger_hash_chain_and_tamper_detection(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with Ledger(path) as ledger:
        assert ledger.append("evt1", "test", 1, {"x": 1}, {"cash": 10})
        assert ledger.append("evt2", "test", 2, {"x": 2}, {"cash": 11})
        assert not ledger.append("evt2", "test", 2, {"x": 2}, {"cash": 11})
        assert ledger.verify()["ok"]
    with Ledger(path) as ledger:
        ledger.db.execute("UPDATE events SET payload_json='{}' WHERE seq=1")
        assert ledger.verify()["reason"] == "event_hash_mismatch"


def test_paper_initializes_once_and_is_idempotent(tmp_path, synthetic_bars):
    path = tmp_path / "paper.sqlite3"
    bars = synthetic_bars(150)
    with Ledger(path) as ledger:
        first = process_new_bars(ledger, bars, StrategyConfig(), 500)
        assert first["initialized"]
        before = ledger.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        second = process_new_bars(ledger, bars, StrategyConfig(), 500)
        after = ledger.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert second["idempotent_noop"]
        assert before == after == 1
        assert ledger.verify()["ok"]


def test_paper_processes_only_new_bars(tmp_path, synthetic_bars):
    bars = synthetic_bars(160)
    with Ledger(tmp_path / "paper.sqlite3") as ledger:
        process_new_bars(ledger, bars[:150], StrategyConfig(), 500)
        result = process_new_bars(ledger, bars, StrategyConfig(), 500)
        assert result["processed_bars"] == 10
        assert result["state"]["last_bar_timestamp"] == bars[-1].timestamp
        assert ledger.verify()["ok"]


def test_paper_gap_fails_without_mutating_state(tmp_path, synthetic_bars):
    bars = synthetic_bars(160)
    with Ledger(tmp_path / "paper.sqlite3") as ledger:
        process_new_bars(ledger, bars[:150], StrategyConfig(), 500)
        count_before = ledger.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        with pytest.raises(ValueError, match="gap detected"):
            process_new_bars(ledger, bars[:150] + bars[151:], StrategyConfig(), 500)
        count_after = ledger.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count_after == count_before


def test_paper_never_spends_more_than_cash(tmp_path, synthetic_bars):
    bars = synthetic_bars(160, trend=0.01, wobble=0.0001)
    with Ledger(tmp_path / "paper.sqlite3") as ledger:
        result = process_new_bars(ledger, bars, StrategyConfig(), 500)
        state = result["state"]
        assert state["cash"] >= 0
        assert state["units"] >= 0
        assert state["mode"] == "PAPER_ONLY"


def test_idempotency_key_cannot_hide_conflicting_event(tmp_path):
    with Ledger(tmp_path / "ledger.sqlite3") as ledger:
        assert ledger.append("same", "test", 1, {"v": 1}, {"cash": 10})
        with pytest.raises(RuntimeError, match="idempotency key collision"):
            ledger.append("same", "test", 1, {"v": 2}, {"cash": 10})
        assert ledger.verify()["ok"]


def test_drawdown_halt_is_sticky_and_forces_zero_target():
    from pro_agent.risk import approve_target, update_drawdown_guard

    peak, dd, halted = update_drawdown_guard(500.0, 500.0, False, 0.25)
    assert not halted and dd == 0
    peak, dd, halted = update_drawdown_guard(370.0, peak, halted, 0.25)
    assert halted and dd <= -0.25
    _, _, halted_again = update_drawdown_guard(490.0, peak, halted, 0.25)
    assert halted_again
    assert approve_target(0.65, halted_again, 0.65) == 0.0


def test_paper_risk_halt_persists_and_targets_cash(tmp_path, synthetic_bars):
    from pro_agent.models import Bar

    bars = synthetic_bars(152, trend=0.003, wobble=0.0001)
    # Initialize at bar 149, then force a large adverse close on bar 150.
    bars[150] = Bar(bars[150].timestamp, bars[150].open, bars[150].open,
                    bars[150].open * 0.49, bars[150].open * 0.50, bars[150].volume)
    bars[151] = Bar(bars[151].timestamp, bars[150].close, bars[150].close,
                    bars[150].close, bars[150].close, bars[151].volume)
    with Ledger(tmp_path / "risk-paper.sqlite3") as ledger:
        process_new_bars(ledger, bars[:150], StrategyConfig(momentum_days=60, volatility_days=20), 500)
        result = process_new_bars(ledger, bars, StrategyConfig(momentum_days=60, volatility_days=20), 500)
        assert result["state"]["halted"] is True
        assert result["state"]["pending_target"] == 0.0
        assert result["state"]["last_signal_reason"] == "RISK_HALT"
        assert result["state"]["units"] == 0.0
        assert ledger.verify()["ok"]
