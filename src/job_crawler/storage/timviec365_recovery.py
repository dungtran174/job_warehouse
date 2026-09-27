"""Offline recovery of the page-2 arrow-selector failure, never an access retry."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from job_crawler.models import RunManifest
from job_crawler.parsers.timviec365 import START, parse_listing
from job_crawler.storage.incremental import IncrementalState
from job_crawler.storage.jsonl import StorageError
from job_crawler.storage.manifest import ManifestWriter

PAGE2 = START + "?page=2"
KEY = "timviec365_page2_arrow_recovery_v1"


def recover_page2(root: Path, metadata_path: Path) -> int:
    manifest = RunManifest.model_validate_json((root / "manifest.json").read_text())
    if manifest.source != "timviec365" or manifest.mode != "bounded":
        raise StorageError("Wrong source/mode for page-2 recovery")
    meta = json.loads(metadata_path.read_text())
    body_path = (metadata_path.parent / meta["body_path"]).resolve()
    if not body_path.is_relative_to((root / "http").resolve()):
        raise StorageError("Evidence outside batch")
    body = gzip.decompress(body_path.read_bytes())
    if (
        meta["requested_url"] != PAGE2
        or meta["final_url"] != PAGE2
        or meta["http_status"] != 200
        or meta["challenge_detected"]
        or hashlib.sha256(body).hexdigest() != meta["body_sha256"]
    ):
        raise StorageError("Not a normal, verified page-2 response")
    page = parse_listing(body.decode(), PAGE2)
    if not page.jobs or page.next_url != START + "?page=3":
        raise StorageError("No main page-2 results/forward navigation")
    with sqlite3.connect(f"file:{root}/checkpoint.sqlite3?mode=rw", uri=True) as db:
        marker = db.execute("SELECT value FROM metadata WHERE key=?", (KEY,)).fetchone()
        if marker:
            if page.fingerprint in manifest.listing_page_fingerprints:
                return 0
            manifest = RunManifest.model_validate_json(marker[0])
            added = 0
        else:
            row = db.execute("SELECT status FROM listing_queue WHERE url=?", (PAGE2,)).fetchone()
            if (
                row != ("failed",)
                or manifest.listing_pages_requested != 2
                or manifest.listing_pages_succeeded != 1
                or manifest.records_written != 3
                or manifest.detail_requested != 3
                or manifest.detail_failed
                or manifest.challenge_detected
                or manifest.pagination_termination_reason != "listing_parse_failed"
            ):
                raise StorageError("Unexpected interrupted listing state")
            existing = dict(db.execute("SELECT source_job_id,canonical_url FROM detail_queue"))
            if any(
                j.source_job_id in existing and existing[j.source_job_id] != j.canonical_url
                for j in page.jobs
            ):
                raise StorageError("Conflicting ID mapping")
            new = [j for j in page.jobs if j.source_job_id not in existing]
            added = len(new)
            if not added:
                raise StorageError("No new page-2 IDs")
            overlaps = len(page.jobs) - added
            manifest.listing_pages_succeeded += 1
            manifest.listing_pages_unique += 1
            manifest.urls_discovered += len(page.jobs)
            manifest.unique_ids_discovered += added
            manifest.cross_page_overlaps += overlaps
            manifest.duplicates_skipped += overlaps
            manifest.new_job_ids_per_page.append(added)
            manifest.listing_page_fingerprints.append(page.fingerprint)
            manifest.incremental_new_ids += added
            manifest.incremental_existing_ids += overlaps
            manifest.pagination_termination_reason = "recovered_from_saved_http"
            manifest.termination_reason = "max_details"
            with db:
                db.executemany(
                    "INSERT INTO detail_queue("
                    "source_job_id,source_name,source_url,canonical_url,listing_url) "
                    "VALUES (?,?,?,?,?)",
                    [
                        (
                            j.source_job_id,
                            j.source_name,
                            j.source_url,
                            j.canonical_url,
                            j.listing_url,
                        )
                        for j in new
                    ],
                )
                db.execute(
                    "INSERT INTO page_fingerprints(fingerprint) VALUES (?)", (page.fingerprint,)
                )
                db.execute("UPDATE listing_queue SET status='completed' WHERE url=?", (PAGE2,))
                db.execute("INSERT OR IGNORE INTO listing_queue(url) VALUES (?)", (page.next_url,))
                db.execute(
                    "INSERT INTO metadata(key,value) VALUES (?,?)",
                    (KEY, manifest.model_dump_json()),
                )
    incremental = IncrementalState(root.parents[1] / "incremental_state.sqlite3")
    try:
        for job in page.jobs:
            incremental.observe_discovery(
                job.source_name,
                job.source_job_id,
                seen_at=datetime.now(UTC),
                batch_id=manifest.batch_id,
            )
    finally:
        incremental.close()
    # Keep the historical error log. Only discovery state is reconciled, not old jobs.
    html_path = root / "html/listing-002.html.gz"
    if not html_path.exists():
        html_path.write_bytes(gzip.compress(body))
    ManifestWriter(root / "manifest.json").write(manifest)
    return added
