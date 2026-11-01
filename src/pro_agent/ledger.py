from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class Ledger:
    """SQLite event log with transactional state snapshots and a SHA-256 hash chain."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                event_time INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                state_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            )
        """)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def latest_state(self) -> dict | None:
        row = self.db.execute("SELECT state_json FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        return json.loads(row["state_json"]) if row else None

    def append(self, event_id: str, event_type: str, event_time: int,
               payload: dict, state_after: dict) -> bool:
        payload_json = canonical_json(payload)
        state_json = canonical_json(state_after)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            duplicate = self.db.execute(
                "SELECT event_type,event_time,payload_json,state_json FROM events WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if duplicate:
                same = (
                    duplicate["event_type"] == event_type
                    and duplicate["event_time"] == event_time
                    and duplicate["payload_json"] == payload_json
                    and duplicate["state_json"] == state_json
                )
                self.db.execute("ROLLBACK")
                if not same:
                    raise RuntimeError(f"idempotency key collision for event_id={event_id}")
                return False
            previous = self.db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous_hash = previous["event_hash"] if previous else "0" * 64
            material = canonical_json({
                "event_id": event_id, "event_type": event_type, "event_time": event_time,
                "payload_json": payload_json, "state_json": state_json,
                "previous_hash": previous_hash,
            })
            event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
            self.db.execute(
                "INSERT INTO events(event_id,event_type,event_time,payload_json,state_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
                (event_id, event_type, event_time, payload_json, state_json, previous_hash, event_hash),
            )
            self.db.execute("COMMIT")
            return True
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def verify(self) -> dict:
        rows = self.db.execute("SELECT * FROM events ORDER BY seq").fetchall()
        previous_hash = "0" * 64
        for expected_seq, row in enumerate(rows, start=1):
            if row["seq"] != expected_seq:
                return {"ok": False, "reason": "sequence_gap", "seq": row["seq"]}
            if row["previous_hash"] != previous_hash:
                return {"ok": False, "reason": "previous_hash_mismatch", "seq": row["seq"]}
            material = canonical_json({
                "event_id": row["event_id"], "event_type": row["event_type"],
                "event_time": row["event_time"], "payload_json": row["payload_json"],
                "state_json": row["state_json"], "previous_hash": row["previous_hash"],
            })
            actual = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if actual != row["event_hash"]:
                return {"ok": False, "reason": "event_hash_mismatch", "seq": row["seq"]}
            previous_hash = actual
        return {"ok": True, "events": len(rows), "head": previous_hash}

    def summary(self) -> dict:
        state = self.latest_state()
        count = self.db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        return {"events": count, "state": state, "integrity": self.verify()}
