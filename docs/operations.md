# Operations, stop and recovery

## Normal use

Run from the repository root with the virtual environment activated. Keep the database in a directory with restrictive ownership and permissions; do not commit it to Git.

```bash
umask 077
mkdir -p state data/raw
pro-agent fetch --pair XBTUSD --out data/raw/xbtusd_daily.csv
pro-agent paper-cycle --csv data/raw/xbtusd_daily.csv --db state/pro-agent.sqlite3 --cash 500
pro-agent status --db state/pro-agent.sqlite3
pro-agent verify --db state/pro-agent.sqlite3
```

The paper account's starting cash is consumed only when the database is initialized. Supplying a different `--cash` later does not reset the account. To avoid accidental reset, do not delete the database as a response to an error.

## Safe stop

The process is command-driven and exits after one operation; there is no continuously running daemon. Stop scheduling future invocations. Do not remove the database while a process may be active.

## Recovery procedure

1. Stop all scheduled/manual instances using the same SQLite file.
2. Copy the database and its `-wal`/`-shm` companions, if present, to a restricted backup location.
3. Run `pro-agent verify --db ...` against the copy.
4. If verification fails, preserve the original and investigate; do not rewrite the hash chain or reset the drawdown halt to make the system appear healthy.
5. If a data gap is reported, obtain the missing closed daily candles from a separately validated source and restore the contiguous series. Do not interpolate prices.
6. Resume only after the event chain and candle continuity are valid.

## Host service deployment

No systemd unit or timer is installed by this repository. Do not schedule it on a host until the public-data fetch, system clock, data continuity and local backup procedure have been verified there. A timer must prevent overlapping invocations and should alert on non-zero exit status and stale data.

## Credentials

This version has no credentials and no configuration for authenticated Kraken endpoints. Do not add API keys to `.env`, command-line flags, source files or SQLite. Future execution work requires a separately reviewed design and explicit authorization.
