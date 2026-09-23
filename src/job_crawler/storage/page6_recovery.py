from __future__ import annotations

import gzip
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from job_crawler.crawlers.careerviet import CareerVietCrawler
from job_crawler.models import JobRecord, RunManifest
from job_crawler.storage.incremental import IncrementalState
from job_crawler.storage.jsonl import StorageError
from job_crawler.storage.manifest import ManifestWriter
from job_crawler.utils.hash import job_content_hash

PAGE_6_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-6-vi.html"


def recover_page6_from_saved_html(root: Path) -> int:
    """Reconcile the known interrupted page 6 without any HTTP or old-record writes.

    The insert is atomic; rerunning after an interrupted insert/manifest update is safe.
    """
    try:
        manifest = RunManifest.model_validate_json((root / "manifest.json").read_text())
        if (
            manifest.source != "careerviet"
            or manifest.mode != "page6-check"
            or manifest.status != "stopped"
            or manifest.termination_reason != "duplicate_job_id"
            or manifest.listing_pages_requested != 6
            or manifest.detail_requested != 250
            or manifest.records_written != 250
            or manifest.detail_succeeded != 250
            or manifest.detail_failed != 0
            or manifest.duplicates_skipped != 1
            or len(manifest.new_job_ids_per_page) != 6
            or manifest.new_job_ids_per_page[:5] != [50] * 5
            or manifest.new_job_ids_per_page[-1] not in {41, 49}
            or manifest.unique_ids_discovered not in {291, 299}
        ):
            raise StorageError("Unexpected page 6 manifest; refusing recovery.")
        lines = (root / "jobs.jsonl").read_text(encoding="utf-8").splitlines()
        records = [JobRecord.model_validate_json(line) for line in lines]
        record_ids = {record.source_job_id for record in records}
        if (
            len(records) != 250
            or len(record_ids) != 250
            or any(
                record.batch_id != manifest.batch_id
                or record.source_name != "careerviet"
                or record.content_hash != job_content_hash(json.loads(line))
                for record, line in zip(records, lines, strict=True)
            )
            or (root / "errors.jsonl").read_text(encoding="utf-8").strip()
        ):
            raise StorageError("Existing jobs/errors JSONL is inconsistent.")
        html_paths = list((root / "html").glob("*.html.gz"))
        if len(html_paths) != 256:
            raise StorageError("Expected 250 detail and six listing gzip files.")
        page_html = ""
        for path in html_paths:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                text = handle.read()
            if path.name == "listing-006.html.gz":
                page_html = text
        page = CareerVietCrawler().parse_listing(page_html, PAGE_6_URL)
        page_ids = {job.source_job_id for job in page.jobs}
        overlap = page_ids & record_ids
        new_jobs = [job for job in page.jobs if job.source_job_id not in record_ids]
        if (
            len(page.jobs) != 50
            or len(page_ids) != 50
            or len(overlap) != 1
            or len(new_jobs) != 49
            or page.fingerprint != manifest.listing_page_fingerprints[-1]
        ):
            raise StorageError("Saved page 6 does not contain 49 new IDs and one overlap.")

        state_path = root.parents[1] / "incremental_state.sqlite3"
        with sqlite3.connect(f"{state_path.resolve().as_uri()}?mode=ro", uri=True) as state:
            if state.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise StorageError("Incremental state integrity check failed.")

        checkpoint_path = root / "checkpoint.sqlite3"
        with sqlite3.connect(
            f"{checkpoint_path.resolve().as_uri()}?mode=rw", uri=True
        ) as checkpoint:
            checkpoint.row_factory = sqlite3.Row
            if checkpoint.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise StorageError("Checkpoint integrity check failed.")
            listing_rows = checkpoint.execute(
                "SELECT url,status FROM listing_queue ORDER BY rowid"
            ).fetchall()
            if (
                len(listing_rows) != 6
                or any(row["status"] != "completed" for row in listing_rows)
                or [row["url"] for row in listing_rows]
                != [
                    "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html",
                    *[
                        f"https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-{n}-vi.html"
                        for n in range(2, 7)
                    ],
                ]
                or checkpoint.execute("SELECT count(*) FROM page_fingerprints").fetchone()[0] != 6
            ):
                raise StorageError("Listing checkpoint is inconsistent.")
            rows = checkpoint.execute(
                "SELECT source_job_id,source_name,canonical_url,status FROM detail_queue"
            ).fetchall()
            queued = {str(row["source_job_id"]): row for row in rows}
            if (
                not record_ids.issubset(queued)
                or not set(queued).issubset(page_ids | record_ids)
                or len(queued) < 291
                or len(queued) > 299
                or {
                    str(row[0])
                    for row in checkpoint.execute("SELECT source_job_id FROM completed_jobs")
                }
                != record_ids
            ):
                raise StorageError("Detail checkpoint is inconsistent.")
            for job in page.jobs:
                if job.source_job_id in queued:
                    row = queued[job.source_job_id]
                    if (
                        row["source_name"] != job.source_name
                        or row["canonical_url"] != job.canonical_url
                        or row["status"]
                        != ("completed" if job.source_job_id in record_ids else "pending")
                    ):
                        raise StorageError("Conflicting job ID mapping or status.")
            if any(queued[job_id]["status"] != "completed" for job_id in record_ids):
                raise StorageError("Old detail status changed.")
            missing = [job for job in new_jobs if job.source_job_id not in queued]
            if len(missing) not in {0, 8}:
                raise StorageError(
                    "Expected either eight missing IDs or an already repaired queue."
                )
            with checkpoint:
                checkpoint.executemany(
                    "INSERT INTO detail_queue("
                    "source_job_id,source_name,source_url,canonical_url,listing_url"
                    ") VALUES (?,?,?,?,?)",
                    (
                        (
                            job.source_job_id,
                            job.source_name,
                            job.source_url,
                            job.canonical_url,
                            job.listing_url,
                        )
                        for job in missing
                    ),
                )

        incremental = IncrementalState(state_path)
        try:
            seen_at = datetime.now(UTC)
            for job in new_jobs:
                incremental.observe_discovery(
                    job.source_name,
                    job.source_job_id,
                    seen_at=seen_at,
                    batch_id=manifest.batch_id,
                )
        finally:
            incremental.close()
        manifest.new_job_ids_per_page[-1] = 49
        manifest.unique_ids_discovered = 299
        manifest.cross_page_overlaps = 1
        manifest.incremental_new_ids = 299
        manifest.incremental_existing_ids = 1
        ManifestWriter(root / "manifest.json").write(manifest)
        return len(missing)
    except StorageError:
        raise
    except (OSError, ValueError, UnicodeError, sqlite3.Error, EOFError) as exc:
        raise StorageError(f"Page 6 recovery failed: {type(exc).__name__}") from exc
