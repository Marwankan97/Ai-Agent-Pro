# AI Agent Pro

**Deterministic, auditable, paper-only spot trading system.** This repository starts from an empty baseline and deliberately contains no capability to place, cancel, or amend exchange orders, withdraw funds, borrow, use margin, or trade derivatives.

> **Status:** engineering prototype. The local test suite is executable; live Kraken public-data retrieval is implemented but has not been verified from this runtime; no historical profitability claim is made. The paper ledger is a local simulation, not an exchange account.

## First release scope

- Instrument: Kraken Spot `XBTUSD` (Bitcoin against USD), one market only.
- Decision frequency: daily, using closed UTC daily candles.
- Strategy hypothesis: positive 90-day time-series momentum, scaled by trailing 30-day realized volatility to a 20% annualized volatility target, capped at 65% long exposure. Otherwise the target is 0%.
- Risk governor: sticky paper halt at a 25% peak-to-trough drawdown. A halt sets the next target to cash; it never clears itself automatically.
- Execution model: signal after a daily close; simulated rebalance at the next daily open; hold open-to-open. Fees and slippage are charged on traded notional.
- State: SQLite transactional event ledger with idempotency keys and a SHA-256 hash chain.
- AI/LLM: deliberately excluded from the trading decision and safety path. No model-generated output can authorize actions or change risk limits.
- Live trading: absent by design. There is no private Kraken API client and no order-submission code in this release.

This is a testable baseline hypothesis, **not a claim that momentum is the best-performing BTC strategy**. It must be evaluated on point-in-time data, costs, walk-forward splits, and a prospective paper period before any strategy-quality conclusion.

## Requirements

- Python 3.11 or newer.
- Runtime has no third-party dependencies. `pytest` is required only for the development test suite.
- Internet access is needed only for the `fetch` command or `paper-cycle` without `--csv`.

## Install and test

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
pro-agent --help
```

You can also run directly from a checkout without installing:

```bash
PYTHONPATH=src python -m pro_agent.cli --help
```

## Obtain market data

```bash
pro-agent fetch --pair XBTUSD --out data/raw/xbtusd_daily.csv
```

The fetcher calls Kraken's **public** Spot REST OHLC endpoint. It drops the final row because Kraken documents that it is the current, uncommitted candle. Kraken's OHLC endpoint is limited to 720 rows; this is not a multi-year historical archive. The fetcher also rejects missing or non-daily timestamps rather than forward-filling them.

For reproducible research, supply an independently sourced, documented CSV with this exact schema:

```csv
timestamp,open,high,low,close,volume
```

`timestamp` is the UTC Unix timestamp in seconds at the daily candle open. Rows must be ascending, unique, daily and complete. Prices must be positive and OHLC ranges valid. Do not mix venues or silently stitch instruments.

## Run a cost-aware backtest

```bash
pro-agent backtest --csv data/raw/xbtusd_daily.csv --cash 500
```

Defaults are deliberately explicit: 0.80% fee per side and 10 bps slippage per side. These are stress assumptions, not a verified quote for an individual Kraken account. Override them only with documented fee-tier evidence and retain the original stress case. The benchmark is unlevered buy-and-hold over the same evaluation period. Metrics are descriptive, not predictive.

Backtesting will fail if there are insufficient warm-up bars or any daily gap. It does not optimize parameters and does not use the future close to execute the signal that generated it.

## Start a local paper ledger

Use a CSV first if you need a deterministic offline run:

```bash
pro-agent paper-cycle --csv data/raw/xbtusd_daily.csv --db state/paper.sqlite3 --cash 500
pro-agent status --db state/paper.sqlite3
pro-agent verify --db state/paper.sqlite3
```

Or fetch the latest closed Kraken candles directly (requires internet):

```bash
pro-agent paper-cycle --pair XBTUSD --db state/paper.sqlite3 --cash 500
```

The first invocation initializes a virtual cash account at the latest closed bar and records a target for the next open; it does not replay historical trades. Later invocations process only unseen daily bars. A repeated invocation against the same candles is an idempotent no-op. A missing candle blocks processing; the program does not fabricate a price or skip the gap. Each processed bar is committed atomically to SQLite.

Paper state is local to the database file. Back it up only after stopping concurrent writers. A database hash-chain check detects accidental or unauthorized modification of recorded events, but does not provide encryption, authentication, or protection against an attacker who can rewrite the database and recompute the entire chain.

## Safety boundary

- No exchange credentials are requested, read, persisted, or accepted.
- No private exchange endpoint is called.
- No order, withdrawal, margin, or derivatives capability exists.
- All market data is untrusted numeric input; text from the API is not interpreted as instructions.
- The strategy cannot change the fee assumptions, drawdown limit, or permissions.
- A paper drawdown halt is sticky and sets the next target to zero.

Do not deploy this prototype as a real trading service. It has not received an independent security review, exchange-integration test, or prospective validation. A future live adapter would require a separate design and explicit authorization; it is outside this repository's current executable scope.

## Documentation

- [Architecture and control boundaries](docs/architecture.md)
- [Research and technology selection](docs/research.md)
- [Operational use and recovery](docs/operations.md)
- [Acceptance tests and current evidence](docs/validation.md)
