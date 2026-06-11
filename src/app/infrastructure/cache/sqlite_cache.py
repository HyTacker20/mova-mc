"""SQLite-backed cache for translation results and QA verdicts."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class SqliteCache:
    """Persistent cache for translation results and QA verdicts.

    Two tables:
    - ``cache``: translation text, keyed by content hash (original table).
    - ``qa_verdict``: QA judge outcomes, keyed by a separate hash.

    Thread-safe: a single connection is shared across threads (WAL mode)
    with a lock serializing all DB access.
    """

    def __init__(self, db_path: str | Path = "translation_cache.db") -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def _ensure_connection(self) -> sqlite3.Connection:
        """Return the shared connection. Caller must hold ``self._lock``."""
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS qa_verdict ("
                "  key TEXT PRIMARY KEY,"
                "  verdict TEXT NOT NULL,"
                "  score INTEGER,"
                "  issue TEXT,"
                "  attempts INTEGER DEFAULT 0,"
                "  judged_at TEXT"
                ")"
            )
            self._conn.commit()
        return self._conn

    # ── Translation cache ─────────────────────────────────────────────

    def get(self, key: str) -> str | None:
        with self._lock:
            conn = self._ensure_connection()
            row = conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def get_many(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        with self._lock:
            conn = self._ensure_connection()
            placeholders = ",".join("?" for _ in keys)
            rows = conn.execute(
                f"SELECT key, value FROM cache WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
            return {row[0]: row[1] for row in rows}

    def set(self, key: str, value: str) -> None:
        with self._lock:
            conn = self._ensure_connection()
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def set_many(self, pairs: dict[str, str]) -> None:
        if not pairs:
            return
        with self._lock:
            conn = self._ensure_connection()
            conn.executemany(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                list(pairs.items()),
            )
            conn.commit()

    # ── QA verdict store ──────────────────────────────────────────────

    def get_verdict(self, key: str) -> tuple[str, int | None, str | None, int] | None:
        """Return ``(verdict, score, issue, attempts)`` or ``None`` if missing."""
        with self._lock:
            conn = self._ensure_connection()
            row = conn.execute(
                "SELECT verdict, score, issue, attempts FROM qa_verdict WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            return (row[0], row[1], row[2], row[3])

    def get_verdicts(self, keys: list[str]) -> dict[str, tuple[str, int | None, str | None, int]]:
        if not keys:
            return {}
        with self._lock:
            conn = self._ensure_connection()
            placeholders = ",".join("?" for _ in keys)
            rows = conn.execute(
                f"SELECT key, verdict, score, issue, attempts FROM qa_verdict WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
            return {row[0]: (row[1], row[2], row[3], row[4]) for row in rows}

    def set_verdict(
        self, key: str, verdict: str, score: int | None = None,
        issue: str | None = None, attempts: int = 0,
    ) -> None:
        from datetime import datetime, timezone

        with self._lock:
            conn = self._ensure_connection()
            conn.execute(
                "INSERT OR REPLACE INTO qa_verdict (key, verdict, score, issue, attempts, judged_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, verdict, score, issue, attempts, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def set_verdicts(
        self,
        entries: dict[str, tuple[str, int | None, str | None, int]],
    ) -> None:
        if not entries:
            return
        from datetime import datetime, timezone

        judged_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._ensure_connection()
            conn.executemany(
                "INSERT OR REPLACE INTO qa_verdict (key, verdict, score, issue, attempts, judged_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (key, verdict, score, issue, attempts, judged_at)
                    for key, (verdict, score, issue, attempts) in entries.items()
                ],
            )
            conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
