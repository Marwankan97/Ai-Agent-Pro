# Architecture and control boundaries

## Design objective

Deliver a small, reproducible daily paper-trading system for one spot market on a low-resource Linux host. The main engineering objective is correctness and auditability, not latency or broad exchange coverage.

## Components

1. **Market data (`market.py`)** — retrieves public Kraken daily OHLC only, drops the current uncommitted candle, parses numeric fields, and rejects malformed, duplicated, unordered, or missing daily bars.
2. **Strategy (`strategy.py`)** — calculates a deterministic target exposure from history ending at the last closed candle. It has no I/O, network, database, model calls, or credentials.
3. **Backtest (`backtest.py`)** — applies the close-to-next-open information boundary, one-way fee and slippage costs, and an unlevered buy-and-hold comparator.
4. **Paper portfolio (`paper.py`)** — simulates fills at the next daily open, tracks cash and base-asset units, values the portfolio at each close, and applies a sticky drawdown halt.
5. **Ledger (`ledger.py`)** — persists each state transition in SQLite under `BEGIN IMMEDIATE`, with a unique event ID, canonical JSON and a chained SHA-256 digest.
6. **CLI (`cli.py`)** — exposes explicit data, backtest, paper-cycle, status and verification commands.

## Decision rule (v0.1)

Let `r_90 = close[t] / close[t-90] - 1`. Let `sigma_30` be the sample standard deviation of the previous 30 daily log returns, annualized by `sqrt(365)`. If `r_90 <= 0`, target exposure is zero. Otherwise:

`target = min(0.65, 0.20 / sigma_30)`

The target is always long-only and at most 65% of marked equity. There is no shorting, leverage, borrowing, derivatives, averaging down, or intraday decision-making. Warm-up periods stay in cash.

These constants are frozen implementation defaults for a research baseline, not optimized parameters or an empirical optimum. A separate research process must compare pre-registered alternatives and report all out-of-sample periods before changing them.

## Time and execution model

A signal uses the close of candle `t`. It becomes eligible for execution at the open of candle `t+1`. Backtest P&L accrues from open `t+1` to open `t+2`. The currently forming Kraken candle is never used. Missing daily bars stop processing because silently forward-filling a 24/7 market can alter both momentum and realized volatility.

## Independent safety boundary

The drawdown governor observes portfolio equity after each mark. At or below a 25% drawdown from the running peak it permanently sets `halted=true` and sets the next target exposure to zero. It is not reset by an LLM, config file, market message, or strategy output. The paper-only program does not possess an exchange order client, so the zero target is a simulated next-open liquidation, not a real order.

## Audit and idempotency

Each paper bar event is keyed by its UTC timestamp. SQLite enforces uniqueness and stores the state snapshot in the same transaction as the event. Re-running the same closed candles does not create duplicate state transitions. The event hash commits to event metadata, canonical payload, state snapshot and previous event hash. `verify` detects tampering and chain discontinuity.

A local hash chain is an integrity aid, not a cryptographic trust anchor: an attacker with full database control can rewrite the complete chain. File permissions, host security and offline backups remain necessary.

## Why no LLM agent?

The trading policy is a small numerical rule with explicit inputs and deterministic outputs. An LLM provides no demonstrated benefit to this decision and would add non-determinism, prompt-injection exposure and additional secrets/network dependencies. Natural-language analysis, if introduced later, must be read-only and must not control orders, risk limits, or credentials.
