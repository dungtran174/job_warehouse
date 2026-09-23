from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal


class IncrementalState:
    """Persistent per-source discovery/content state, independent of crawl batches."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_state (
                source_name TEXT NOT NULL,
                source_job_id TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_content_hash TEXT,
                last_detail_fetched_at TEXT,
                seen_count INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1,
                last_seen_batch_id TEXT NOT NULL,
                PRIMARY KEY(source_name, source_job_id)
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def observe_discovery(
        self,
        source_name: str,
        source_job_id: str,
        *,
        seen_at: datetime,
        batch_id: str,
    ) -> bool:
        timestamp = seen_at.isoformat()
        existing = self.connection.execute(
            """
            SELECT last_seen_batch_id FROM job_state
            WHERE source_name = ? AND source_job_id = ?
            """,
            (source_name, source_job_id),
        ).fetchone()
        if existing is None:
            self.connection.execute(
                """
                INSERT INTO job_state(
                    source_name, source_job_id, first_seen_at, last_seen_at,
                    seen_count, active, last_seen_batch_id
                ) VALUES (?, ?, ?, ?, 1, 1, ?)
                """,
                (source_name, source_job_id, timestamp, timestamp, batch_id),
            )
            self.connection.commit()
            return True

        if str(existing["last_seen_batch_id"]) != batch_id:
            self.connection.execute(
                """
                UPDATE job_state
                SET last_seen_at = ?, seen_count = seen_count + 1,
                    active = 1, last_seen_batch_id = ?
                WHERE source_name = ? AND source_job_id = ?
                """,
                (timestamp, batch_id, source_name, source_job_id),
            )
            self.connection.commit()
        return False

    def update_content(
        self,
        source_name: str,
        source_job_id: str,
        *,
        content_hash: str,
        fetched_at: datetime,
    ) -> Literal["new", "unchanged", "changed"]:
        row = self.connection.execute(
            """
            SELECT last_content_hash FROM job_state
            WHERE source_name = ? AND source_job_id = ?
            """,
            (source_name, source_job_id),
        ).fetchone()
        previous = str(row["last_content_hash"]) if row and row["last_content_hash"] else None
        status: Literal["new", "unchanged", "changed"]
        if previous is None:
            status = "new"
        elif previous == content_hash:
            status = "unchanged"
        else:
            status = "changed"
        self.connection.execute(
            """
            UPDATE job_state
            SET last_content_hash = ?, last_detail_fetched_at = ?, active = 1
            WHERE source_name = ? AND source_job_id = ?
            """,
            (content_hash, fetched_at.isoformat(), source_name, source_job_id),
        )
        self.connection.commit()
        return status

    def get(self, source_name: str, source_job_id: str) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT * FROM job_state WHERE source_name = ? AND source_job_id = ?",
            (source_name, source_job_id),
        ).fetchone()
        return dict(row) if row else None
