from __future__ import annotations

import argparse
import json
import sys

from .backtest import run_backtest
from .ledger import Ledger
from .market import fetch_kraken_ohlc, load_csv, save_csv
from .models import StrategyConfig
from .paper import process_new_bars


def _config(args: argparse.Namespace) -> StrategyConfig:
    return StrategyConfig(
        momentum_days=args.momentum_days,
        volatility_days=args.volatility_days,
        target_annual_volatility=args.target_vol,
        maximum_exposure=args.max_exposure,
        maximum_drawdown=args.max_drawdown,
        fee_rate=args.fee_rate,
        slippage_bps=args.slippage_bps,
    )


def _data(args: argparse.Namespace):
    if getattr(args, "csv", None):
        return load_csv(args.csv)
    return fetch_kraken_ohlc(getattr(args, "pair", "XBTUSD"))


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--momentum-days", type=int, default=90)
    parser.add_argument("--volatility-days", type=int, default=30)
    parser.add_argument("--target-vol", type=float, default=0.20)
    parser.add_argument("--max-exposure", type=float, default=0.65)
    parser.add_argument("--max-drawdown", type=float, default=0.25)
    parser.add_argument("--fee-rate", type=float, default=0.008,
                         help="per-side fee assumption; verify your account tier before interpreting results")
    parser.add_argument("--slippage-bps", type=float, default=10.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pro-agent", description="Deterministic paper-only trading agent")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch closed daily public Kraken OHLC candles")
    fetch.add_argument("--pair", default="XBTUSD")
    fetch.add_argument("--out", default="data/raw/xbtusd_daily.csv")

    backtest = sub.add_parser("backtest", help="run a cost-aware next-open backtest")
    backtest.add_argument("--csv", required=True)
    backtest.add_argument("--cash", type=float, default=500.0)
    _add_common(backtest)

    paper = sub.add_parser("paper-cycle", help="process closed bars into the local paper ledger")
    paper.add_argument("--csv", help="CSV input; if omitted, fetch public Kraken OHLC")
    paper.add_argument("--pair", default="XBTUSD")
    paper.add_argument("--db", default="state/pro-agent.sqlite3")
    paper.add_argument("--cash", type=float, default=500.0, help="used only on first initialization")
    _add_common(paper)

    status = sub.add_parser("status", help="show paper ledger status and integrity")
    status.add_argument("--db", default="state/pro-agent.sqlite3")

    verify = sub.add_parser("verify", help="verify the append-only event hash chain")
    verify.add_argument("--db", default="state/pro-agent.sqlite3")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "fetch":
            bars = fetch_kraken_ohlc(args.pair)
            save_csv(bars, args.out)
            print(json.dumps({"saved": args.out, "closed_bars": len(bars),
                              "first_timestamp": bars[0].timestamp,
                              "last_timestamp": bars[-1].timestamp}, indent=2))
            return 0
        if args.command == "backtest":
            bars = load_csv(args.csv)
            result = run_backtest(bars, _config(args), args.cash)
            result.pop("equity_curve", None)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "paper-cycle":
            bars = _data(args)
            with Ledger(args.db) as ledger:
                result = process_new_bars(ledger, bars, _config(args), args.cash)
                result["integrity"] = ledger.verify()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "status":
            with Ledger(args.db) as ledger:
                print(json.dumps(ledger.summary(), indent=2, sort_keys=True))
            return 0
        if args.command == "verify":
            with Ledger(args.db) as ledger:
                result = ledger.verify()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["ok"] else 2
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
