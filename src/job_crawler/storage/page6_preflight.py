from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

from job_crawler.models import JobRecord, RunManifest
from job_crawler.storage.jsonl import StorageError
from job_crawler.utils.hash import job_content_hash

START_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html"
PAGE_6_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-6-vi.html"


def validate_page6_transition(root: Path, manifest: RunManifest) -> None:
    """Reject a damaged or unexpected 5-page/250-detail batch before any request."""
    if (
        manifest.source != "careerviet"
        or manifest.mode != "pilot"
        or manifest.status != "completed"
        or manifest.start_url != START_URL
        or manifest.listing_pages_requested != 5
        or manifest.listing_pages_succeeded != 5
        or manifest.listing_pages_unique != 5
        or manifest.detail_requested != 250
        or manifest.detail_succeeded != 250
        or manifest.records_written != 250
        or manifest.detail_failed != 0
        or manifest.duplicates_skipped != 0
        or manifest.unique_ids_discovered != 250
    ):
        raise StorageError("Page 6 check requires the completed 5-page/250-detail pilot batch.")

    try:
        with sqlite3.connect(
            f"{(root / 'checkpoint.sqlite3').resolve().as_uri()}?mode=ro", uri=True
        ) as checkpoint:
            if checkpoint.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise StorageError("Checkpoint integrity check failed.")
            listing_rows = checkpoint.execute(
                "SELECT url, status FROM listing_queue ORDER BY rowid"
            ).fetchall()
            expected_urls = [START_URL] + [
                f"https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-{page}-vi.html"
                for page in range(2, 7)
            ]
            if listing_rows != [
                *[(url, "completed") for url in expected_urls[:5]],
                (PAGE_6_URL, "pending"),
            ]:
                raise StorageError("Expected exactly five completed listings and pending page 6.")
            detail_rows = checkpoint.execute(
                "SELECT source_job_id, status FROM detail_queue"
            ).fetchall()
            completed_ids = {
                row[0] for row in checkpoint.execute("SELECT source_job_id FROM completed_jobs")
            }
            fingerprint_count = checkpoint.execute(
                "SELECT COUNT(*) FROM page_fingerprints"
            ).fetchone()[0]
            if (
                len(detail_rows) != 250
                or any(status != "completed" for _, status in detail_rows)
                or fingerprint_count != 5
            ):
                raise StorageError("Checkpoint detail or fingerprint counts do not match pilot.")

        lines = (root / "jobs.jsonl").read_text(encoding="utf-8").splitlines()
        records = [JobRecord.model_validate_json(line) for line in lines]
        record_ids = {record.source_job_id for record in records}
        if (
            len(records) != 250
            or len(record_ids) != 250
            or record_ids != completed_ids
            or record_ids != {job_id for job_id, _ in detail_rows}
            or any(
                record.batch_id != manifest.batch_id
                or record.source_name != "careerviet"
                or record.raw_html_path != f"html/{record.source_job_id}.html.gz"
                or record.content_hash != job_content_hash(json.loads(line))
                for record, line in zip(records, lines, strict=True)
            )
        ):
            raise StorageError("Existing jobs.jsonl or content hashes do not match checkpoint.")
        if (root / "errors.jsonl").read_text(encoding="utf-8").strip():
            raise StorageError("Page 6 check requires an error-free pilot batch.")

        html_paths = sorted((root / "html").glob("*.html.gz"))
        if len(html_paths) != 255:
            raise StorageError("Expected five listing and 250 detail Raw HTML files.")
        for path in html_paths:
            with gzip.open(path, "rb") as handle:
                while handle.read(1024 * 1024):
                    pass

        with sqlite3.connect(
            f"{(root.parents[1] / 'incremental_state.sqlite3').resolve().as_uri()}?mode=ro",
            uri=True,
        ) as incremental:
            if incremental.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise StorageError("Incremental state integrity check failed.")
            rows = incremental.execute(
                "SELECT source_job_id, last_content_hash, active FROM job_state "
                "WHERE source_name = 'careerviet'"
            ).fetchall()
            state = {job_id: (content_hash, active) for job_id, content_hash, active in rows}
            if any(
                state.get(record.source_job_id) != (record.content_hash, 1) for record in records
            ):
                raise StorageError("Incremental state does not match completed records.")
    except StorageError:
        raise
    except (OSError, UnicodeError, ValueError, sqlite3.Error, EOFError) as exc:
        raise StorageError(f"Page 6 preflight failed: {type(exc).__name__}") from exc
