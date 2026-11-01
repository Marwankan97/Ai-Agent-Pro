import pytest

from pro_agent.market import load_csv, save_csv
from pro_agent.models import Bar


def test_csv_round_trip(tmp_path, synthetic_bars):
    path = tmp_path / "bars.csv"
    original = synthetic_bars(120)
    save_csv(original, path)
    assert load_csv(path) == original


def test_duplicate_timestamp_rejected(tmp_path, synthetic_bars):
    bars = synthetic_bars(4)
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,open,high,low,close,volume\n" + "\n".join(
        f"{b.timestamp},{b.open},{b.high},{b.low},{b.close},{b.volume}" for b in [bars[0], bars[0]]
    ))
    with pytest.raises(ValueError, match="strictly increasing"):
        load_csv(path)


def test_daily_gap_rejected(tmp_path, synthetic_bars):
    bars = synthetic_bars(4)
    bars[2] = Bar(bars[2].timestamp + 86_400, bars[2].open, bars[2].high, bars[2].low, bars[2].close, bars[2].volume)
    path = tmp_path / "gap.csv"
    from pro_agent.market import validate_series
    with pytest.raises(ValueError, match="missing or non-daily"):
        validate_series(bars)


def test_kraken_fetch_drops_current_uncommitted_candle(monkeypatch):
    import json
    from pro_agent.market import fetch_kraken_ohlc

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self):
            payload = {
                "error": [],
                "result": {
                    "XXBTZUSD": [
                        [1_700_000_000, "10", "11", "9", "10.5", "10.2", "12", 3],
                        [1_700_086_400, "10.5", "12", "10", "11.5", "11", "13", 4],
                        [1_700_172_800, "11.5", "100", "10", "90", "50", "99", 5],
                    ],
                    "last": "cursor",
                },
            }
            return json.dumps(payload).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response())
    bars = fetch_kraken_ohlc()
    assert len(bars) == 2
    assert bars[-1].close == 11.5


def test_kraken_api_error_is_not_treated_as_market_data(monkeypatch):
    import json
    from pro_agent.market import fetch_kraken_ohlc

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return json.dumps({"error": ["EQuery:Unknown asset pair"], "result": {}}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response())
    with pytest.raises(RuntimeError, match="Kraken public API error"):
        fetch_kraken_ohlc()
