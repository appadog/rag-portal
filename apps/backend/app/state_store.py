"""Small SQLite snapshot store for the local RAG Portal runtime.

The domain model intentionally remains in memory while it is being evolved.
This store gives that model durable process-restart behaviour without coupling
the API layer to an ORM before the production schema is settled.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS portal_state (
                  key TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    def load(self, key: str = "runtime") -> dict | None:
        with self.lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM portal_state WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, payload: dict, key: str = "runtime") -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self.lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO portal_state(key, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (key, encoded),
            )

