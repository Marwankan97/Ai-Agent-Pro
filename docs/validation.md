# Acceptance criteria and evidence

## Acceptance criteria fixed for v0.1

1. Deterministic signal: identical closed OHLC history and configuration produce identical exposure and reason.
2. Time integrity: signal is computed only through candle close `t`; execution is modeled at the next daily open; current uncommitted Kraken candle is excluded.
3. Cost model: every exposure change pays one-way fee and slippage; passive benchmark uses the same entry cost convention.
4. Risk policy: exposure is in `[0, maximum_exposure]`; drawdown halt is sticky and directs the next target to zero.
5. Input integrity: reject malformed prices, duplicate/out-of-order bars and missing daily candles.
6. Ledger: unique event IDs, transactional writes, repeat-cycle idempotency and a verifiable SHA-256 event chain.
7. Permission boundary: no private exchange client, order, cancel, withdrawal, leverage or live-trading implementation.
8. Reproducibility: tests run offline with deterministic synthetic fixtures; synthetic data is never presented as market-performance evidence.

## Local evidence (2026-11-01)

- Python runtime inspected: Python 3.13.5.
- Available test runner inspected: pytest installed.
- Third-party trading packages inspected: `ccxt`, `vectorbt`, and `backtrader` were not installed.
- Tests: see the repository CI workflow and test suite. The synthetic fixtures are generated in tests and are not exchange data.
- GitHub repository access: metadata verified; repo was empty before initialization; push permission available through the GitHub integration.
- Direct container access to GitHub failed with `Could not resolve host: github.com`; live Kraken endpoint connectivity is also unverified from this runtime.

## Explicitly not verified

- No real Kraken candle request completed in this runtime.
- No genuine multi-year historical dataset was downloaded or backtested.
- No empirical out-of-sample return, Sharpe, drawdown or profitability claim is made.
- No authenticated API, order validation, simulated exchange fill, or live order integration was tested. There is no such code in v0.1.
- No prospective paper observation period has elapsed.
- No installation or systemd deployment was performed on the user's Fitlet.

## Release interpretation

A passing software test suite is evidence about the tested invariants only. It does not show that the strategy is profitable, robust to all market regimes, or safe for live capital. v0.1 is accepted as a paper-engineering prototype only; it is not accepted as a deployable live trading system.
