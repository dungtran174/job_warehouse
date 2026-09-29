"""Read-only batch inspection: never create storage or reset processing queues."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Any

CORE_FIELDS = ("job_title", "company_name", "job_description", "candidate_requirements")


def read_batch_status(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    invalid_lines = []
    raw_lines = 0
    for number, line in enumerate((root / "jobs.jsonl").read_bytes().splitlines(), 1):
        if not line.strip():
            continue
        raw_lines += 1
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or not record.get("source_job_id"):
                raise ValueError("Not a job record")
            rows.append(record)
        except (ValueError, UnicodeDecodeError):
            invalid_lines.append(number)
    identities = {(row.get("source_name"), row["source_job_id"]) for row in rows}
    missing_core = {
        field: sum(not isinstance(row.get(field), str) or not row[field].strip() for row in rows)
        for field in CORE_FIELDS
    }
    queue: dict[str, dict[str, int]] = {}
    # Checkpoint uses SQLite rollback journal, not the incremental WAL database.
    # immutable + ro avoids even creating sidecars; results are a point-in-time view.
    uri = (root / "checkpoint.sqlite3").as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        for table in ("listing_queue", "detail_queue"):
            queue[table] = dict(
                connection.execute(f"SELECT status, COUNT(*) FROM {table} GROUP BY status")  # noqa: S608
            )
        pending_listing = [
            row[0]
            for row in connection.execute(
                "SELECT url FROM listing_queue WHERE status IN ('pending','processing') "
                "ORDER BY rowid"
            )
        ]
        pending_details = [
            {"id": row[0], "url": row[1], "status": row[2]}
            for row in connection.execute(
                "SELECT source_job_id, canonical_url, status FROM detail_queue "
                "WHERE status IN ('pending','processing') ORDER BY rowid"
            )
        ]
    errors = []
    for line in (root / "errors.jsonl").read_bytes().splitlines():
        # A running writer may have an incomplete last line.
        with suppress(ValueError, UnicodeDecodeError):
            errors.append(json.loads(line))
    return {
        "batch_root": str(root),
        "batch_id": manifest["batch_id"],
        "source": manifest["source"],
        "mode": manifest["mode"],
        "start_url": manifest["start_url"],
        "status": manifest["status"],
        "termination_reason": manifest.get("termination_reason"),
        "pagination_termination_reason": manifest.get("pagination_termination_reason"),
        "raw_lines": raw_lines,
        "parsed_records": len(rows),
        "unique_source_ids": len(identities),
        "duplicate_source_ids": len(rows) - len(identities),
        "invalid_jsonl_lines": invalid_lines,
        "missing_core_fields": missing_core,
        "listing_attempts": manifest.get("listing_pages_requested"),
        "listing_successes": manifest.get("listing_pages_succeeded"),
        "discovered_unique_ids": manifest.get("unique_ids_discovered"),
        "detail_attempts": manifest.get("detail_requested"),
        "detail_successes": manifest.get("detail_succeeded"),
        "detail_failures_cumulative": manifest.get("detail_failed"),
        "manifest_records_written": manifest.get("records_written"),
        "challenge_detected_last_run": manifest.get("challenge_detected"),
        "last_run_settings": (manifest.get("run_settings") or [None])[-1],
        "queue_counts": queue,
        "pending_listing_urls": pending_listing,
        "pending_details": pending_details,
        "error_lines": len(errors),
        "error_stages": dict(Counter(error.get("stage") for error in errors)),
        "last_errors": errors[-3:],
        "note": "Read-only; during crawl manifest/JSONL/checkpoint can briefly differ. "
        "Core nonempty fields are not a full HTML completeness audit.",
    }
