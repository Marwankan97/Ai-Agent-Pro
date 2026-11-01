# Research notes and engineering selection

**Checked:** 2026-11-01. Online project and exchange documentation was consulted for the engineering choice. The runtime container could not resolve GitHub or reach external hosts, so source-code installation tests and a live public API request were not possible here.

## Selection criteria

Weighted qualitatively for this use case: (1) correctness and ability to test the time model, (2) small and auditable operational surface, (3) fit on a Debian 13 / 8 GB class host, (4) API and data semantics, (5) maintenance and license obligations, (6) cost and external service independence.

## Alternatives reviewed

| Candidate | Strengths relevant here | Cost / limitation for this first release | Decision |
|---|---|---|---|
| Custom Python + stdlib + SQLite | Minimal dependencies; easy to inspect; deterministic daily pipeline; native SQLite transactions and local operation | We must own and test every invariant; not a complete multi-venue trading framework | **Selected** for one symbol, daily, paper-only scope |
| Freqtrade | Mature crypto bot; Kraken spot listed; backtesting, dry-run and exchange integration already exist | Broad operational surface and substantial dependency graph; GPLv3 licensing; this project needs a very small bespoke ledger/risk boundary | Not adopted; re-evaluate if multi-strategy exchange support becomes a requirement |
| NautilusTrader | Rust-native deterministic engine; official Kraken adapter; high-performance event-driven architecture | Heavier engine than this daily process needs; current docs distinguish stable v1 from v2 release candidates, so v2 API is not treated as a production-stable baseline | Not adopted for v0.1 |
| QuantConnect LEAN | Broad multi-asset event-driven backtest/live engine; Apache-2.0 project | Much broader runtime and .NET/Docker operational footprint than the single-market paper scope | Not adopted for v0.1 |
| CCXT | MIT-licensed exchange abstraction across many venues; supports Python and Kraken | Adds a third-party abstraction/dependency; does not replace the need for a custom ledger, risk governor or validation model | Not needed for one Kraken public endpoint; reconsider for multi-exchange expansion |

## Data-source facts that affect the implementation

- Kraken's REST API symbols are not always identical between REST and WebSocket interfaces. The AssetPairs/Assets endpoints are the official way to discover current pair aliases and precision; the configured REST symbol must be checked against the selected market. The fetcher defaults to `XBTUSD` and does not attempt to trade or infer exchange precision.
- Kraken documents a 720-row cap for REST OHLC. The last row is the current, uncommitted candle. The client removes that row and rejects incomplete or discontinuous data. For longer history, a separately validated archive or trade-history-to-OHLC pipeline will be needed.
- Kraken documents API rate limits. The daily poll is intentionally low frequency; the implementation does not poll rapidly or retry in a tight loop.
- Kraken's `validate=true` behavior checks order parameters without creating an order ID. It is not a fill simulation, and this code does not call AddOrder even in validation mode.

## Research strategy boundary

Positive time-series momentum and volatility scaling are used only as a transparent baseline hypothesis, not as a claim of superiority. The first release does not search a parameter grid, select winners, or publish a profitability conclusion. The correct next research gate is to acquire a verified multi-year OHLC dataset, freeze all candidate rules before evaluation, use chronological walk-forward/holdout periods, model realistic account fees and spread/slippage, report all tried variants, and compare to cash and unlevered buy-and-hold. A 720-day endpoint snapshot is insufficient to support a robust multi-year conclusion.

## Source register

- Kraken Advanced API FAQ: OHLC history limit and historical trades alternative — https://support.kraken.com/articles/advanced-api-faq
- Kraken API symbols and tickers (updated 2026-10-29): REST/WebSocket symbols and AssetPairs metadata — https://support.kraken.com/articles/360000920306-api-symbols-and-tickers
- Kraken rate limits (updated 2026-08-10): https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-
- Kraken order validation behavior — https://support.kraken.com/articles/advanced-api-faq
- Freqtrade project dependencies and GPLv3 declaration — https://github.com/freqtrade/freqtrade/blob/develop/pyproject.toml
- NautilusTrader repository and license statement — https://github.com/nautechsystems/nautilus_trader
- NautilusTrader supported Python/platform matrix and v1/v2 install distinction — https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/getting_started/installation.md
- QuantConnect LEAN repository and Apache-2.0 license — https://github.com/QuantConnect/Lean
- CCXT package metadata and MIT license — https://github.com/ccxt/ccxt/blob/master/pyproject.toml and https://github.com/ccxt/ccxt/blob/master/python/LICENSE.txt
