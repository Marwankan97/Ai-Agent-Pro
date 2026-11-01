from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

from .models import Bar

KRAKEN_BASE = "https://api.kraken.com/0/public/OHLC"
DAY_SECONDS = 86_400


def validate_series(bars: Iterable[Bar], *, require_daily: bool = True) -> list[Bar]:
    rows = list(bars)
    if len(rows) < 2:
        raise ValueError("at least two OHLC bars are required")
    previous = None
    for bar in rows:
        bar.validate()
        if previous is not None:
            if bar.timestamp <= previous:
                raise ValueError("OHLC timestamps must be strictly increasing and unique")
            if require_daily and bar.timestamp - previous != DAY_SECONDS:
                raise ValueError(
                    f"missing or non-daily candle between {previous} and {bar.timestamp}; refusing to forward-fill"
                )
        previous = bar.timestamp
    return rows


def load_csv(path: str | Path) -> list[Bar]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    bars: list[Bar] = []
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must contain columns: {', '.join(sorted(required))}")
        for line_no, row in enumerate(reader, start=2):
            try:
                bars.append(Bar(
                    timestamp=int(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid CSV row {line_no}: {exc}") from exc
    return validate_series(bars)


def save_csv(bars: Iterable[Bar], path: str | Path) -> None:
    rows = validate_series(bars)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for bar in rows:
            writer.writerow([bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume])


def fetch_kraken_ohlc(pair: str = "XBTUSD", timeout: float = 15.0) -> list[Bar]:
    """Fetch daily public OHLC only. No private API, credentials, or order endpoints."""
    pair = pair.strip().upper()
    if not pair.isalnum() or len(pair) > 20:
        raise ValueError("pair must be an alphanumeric Kraken REST pair symbol")
    query = urllib.parse.urlencode({"pair": pair, "interval": 1440})
    request = urllib.request.Request(
        f"{KRAKEN_BASE}?{query}",
        headers={"User-Agent": "Ai-Agent-Pro/0.1 (public-market-data; paper-only)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"Kraken HTTP status {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
    errors = payload.get("error") or []
    if errors:
        raise RuntimeError("Kraken public API error: " + "; ".join(map(str, errors)))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Kraken response is missing result object")
    pair_keys = [key for key in result if key != "last"]
    if len(pair_keys) != 1:
        raise RuntimeError(f"expected one OHLC pair result, received keys: {pair_keys}")
    raw_rows = result[pair_keys[0]]
    if not isinstance(raw_rows, list) or len(raw_rows) < 2:
        raise RuntimeError("Kraken returned insufficient OHLC data")
    # Kraken documents that the final OHLC row is the current, uncommitted candle.
    # Drop it unconditionally; it must never enter a backtest or paper decision.
    closed_rows = raw_rows[:-1]
    bars: list[Bar] = []
    for raw in closed_rows:
        if not isinstance(raw, list) or len(raw) < 7:
            raise RuntimeError("unexpected Kraken OHLC row schema")
        bars.append(Bar(
            timestamp=int(raw[0]), open=float(raw[1]), high=float(raw[2]),
            low=float(raw[3]), close=float(raw[4]), volume=float(raw[6]),
        ))
    return validate_series(bars)
