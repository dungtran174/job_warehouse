from __future__ import annotations

import sqlite3
from pathlib import Path

from job_crawler.models import DiscoveredJob


class RepeatedPageFingerprint(RuntimeError):
    """The same listing fingerprint was already committed."""


class CheckpointConflict(RuntimeError):
    """A source job ID or listing state conflicts with the checkpoint."""


class Checkpoint:
    """Technical crawl state only; this is not an application OLTP database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS listing_queue (
                url TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS detail_queue (
                source_job_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                listing_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS page_fingerprints (
                fingerprint TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS completed_jobs (
                source_job_id TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.connection.execute(
            "UPDATE listing_queue SET status = 'pending' WHERE status = 'processing'"
        )
        self.connection.execute(
            "UPDATE detail_queue SET status = 'pending' WHERE status = 'processing'"
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def enqueue_listing(self, url: str) -> bool:
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO listing_queue(url) VALUES (?)", (url,)
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def next_listing(self) -> str | None:
        row = self.connection.execute(
            "SELECT url FROM listing_queue WHERE status = 'pending' ORDER BY rowid LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        url = str(row["url"])
        self.connection.execute(
            "UPDATE listing_queue SET status = 'processing' WHERE url = ?", (url,)
        )
        self.connection.commit()
        return url

    def finish_listing(self, url: str, status: str = "completed") -> None:
        self.connection.execute("UPDATE listing_queue SET status = ? WHERE url = ?", (status, url))
        self.connection.commit()

    def add_fingerprint(self, fingerprint: str) -> bool:
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO page_fingerprints(fingerprint) VALUES (?)", (fingerprint,)
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def commit_listing_page(
        self, url: str, fingerprint: str, jobs: list[DiscoveredJob]
    ) -> tuple[int, int]:
        """Atomically enqueue every new ID before completing its listing page."""
        new_count = 0
        overlaps = 0
        seen: set[str] = set()
        with self.connection:
            row = self.connection.execute(
                "SELECT status FROM listing_queue WHERE url = ?", (url,)
            ).fetchone()
            if row is None or row["status"] != "processing":
                raise CheckpointConflict("Listing is not in processing state.")
            if (
                self.connection.execute(
                    "INSERT OR IGNORE INTO page_fingerprints(fingerprint) VALUES (?)",
                    (fingerprint,),
                ).rowcount
                != 1
            ):
                raise RepeatedPageFingerprint(fingerprint)
            for job in jobs:
                if job.source_job_id in seen:
                    raise CheckpointConflict("Duplicate ID within listing page.")
                seen.add(job.source_job_id)
                existing = self.connection.execute(
                    "SELECT source_name, canonical_url FROM detail_queue WHERE source_job_id = ?",
                    (job.source_job_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["source_name"] != job.source_name
                        or existing["canonical_url"] != job.canonical_url
                    ):
                        raise CheckpointConflict(
                            f"Conflicting mapping for job ID {job.source_job_id}."
                        )
                    overlaps += 1
                    continue
                self.connection.execute(
                    "INSERT INTO detail_queue("
                    "source_job_id, source_name, source_url, canonical_url, listing_url"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        job.source_job_id,
                        job.source_name,
                        job.source_url,
                        job.canonical_url,
                        job.listing_url,
                    ),
                )
                new_count += 1
            if (
                self.connection.execute(
                    "UPDATE listing_queue SET status = 'completed' WHERE url = ?", (url,)
                ).rowcount
                != 1
            ):
                raise CheckpointConflict("Listing completion failed.")
        return new_count, overlaps

    def enqueue_detail(self, job: DiscoveredJob) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO detail_queue(
                source_job_id, source_name, source_url, canonical_url, listing_url
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                job.source_job_id,
                job.source_name,
                job.source_url,
                job.canonical_url,
                job.listing_url,
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def next_detail(self) -> DiscoveredJob | None:
        row = self.connection.execute(
            """
            SELECT source_job_id, source_name, source_url, canonical_url, listing_url
            FROM detail_queue WHERE status = 'pending' ORDER BY rowid LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        job = DiscoveredJob.model_validate(dict(row))
        self.connection.execute(
            "UPDATE detail_queue SET status = 'processing' WHERE source_job_id = ?",
            (job.source_job_id,),
        )
        self.connection.commit()
        return job

    def finish_detail(self, source_job_id: str, status: str) -> None:
        self.connection.execute(
            "UPDATE detail_queue SET status = ? WHERE source_job_id = ?",
            (status, source_job_id),
        )
        self.connection.commit()

    def mark_completed(self, source_job_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO completed_jobs(source_job_id) VALUES (?)",
                (source_job_id,),
            )
            self.connection.execute(
                "UPDATE detail_queue SET status = 'completed' WHERE source_job_id = ?",
                (source_job_id,),
            )

    def is_completed(self, source_job_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM completed_jobs WHERE source_job_id = ?", (source_job_id,)
        ).fetchone()
        return row is not None

    def sync_completed(self, source_job_ids: set[str]) -> None:
        with self.connection:
            self.connection.executemany(
                "INSERT OR IGNORE INTO completed_jobs(source_job_id) VALUES (?)",
                ((job_id,) for job_id in source_job_ids),
            )
            self.connection.executemany(
                "UPDATE detail_queue SET status = 'completed' WHERE source_job_id = ?",
                ((job_id,) for job_id in source_job_ids),
            )

    def count_details(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM detail_queue").fetchone()
        return int(row["count"])

    def has_pending_details(self) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM detail_queue WHERE status = 'pending' LIMIT 1"
        ).fetchone()
        return row is not None

    def set_metadata(self, key: str, value: str) -> None:
        self.connection.execute(
            """
            INSERT INTO metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.connection.commit()

    def get_metadata(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None
