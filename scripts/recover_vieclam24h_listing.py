"""Offline, idempotent repair of a listing parse failure using captured HTML."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from job_crawler.engine import MISSING_FIELD_NAMES, REQUIRED_RECORD_FIELDS
from job_crawler.models import DiscoveredJob
from job_crawler.parsers.vieclam24h import job_url, listing_url_allowed, parse_detail, parse_listing
from job_crawler.storage.incremental import IncrementalState
from job_crawler.storage.jsonl import BatchStorage


def recover(batch: Path, url: str) -> dict:
    if not listing_url_allowed(url):
        raise ValueError("Not a public Việc Làm 24h listing")
    original = json.loads((batch / "manifest.json").read_text())
    if original["source"] != "vieclam24h" or original["status"] == "running":
        raise ValueError("Recovery requires an idle Việc Làm 24h batch")
    if original["challenge_detected"] or original["termination_reason"] in {
        "access_blocked",
        "browser_challenge",
        "robots_denied",
        "robots_unavailable",
    }:
        raise ValueError("Do not reopen an access-blocked batch via parser recovery")
    candidates = []
    for path in (batch / "http").glob("*.json"):
        meta = json.loads(path.read_text())
        if meta.get("requested_url") == url and meta.get("http_status") == 200:
            if meta.get("blocked") or meta.get("challenge_type"):
                raise ValueError("Captured listing was access-blocked")
            candidates.append(meta)
    if len(candidates) != 1:
        raise ValueError("Require exactly one captured accessible listing response")
    meta = candidates[0]
    html = gzip.decompress((batch / "http" / meta["html_path"]).read_bytes())
    if hashlib.sha256(html).hexdigest() != meta["html_sha256"]:
        raise ValueError("Saved HTML checksum mismatch")
    page = parse_listing(html.decode(), meta["final_url"])
    raw_hash = hashlib.sha256((batch / "jobs.jsonl").read_bytes()).hexdigest()
    storage = BatchStorage.resume(batch)
    incremental = IncrementalState(batch.parent.parent / "incremental_state.sqlite3")
    try:
        state = storage.checkpoint.connection.execute(
            "SELECT status FROM listing_queue WHERE url=?", (url,)
        ).fetchone()
        if state is None:
            raise ValueError("Listing absent from checkpoint")
        if state["status"] == "completed":
            return {"already_recovered": True, "new_requests": 0}
        if state["status"] != "failed":
            raise ValueError("Recover only a failed parser listing")
        errors = [
            json.loads(line)
            for line in (batch / "errors.jsonl").read_text().splitlines()
            if line.strip()
        ]
        if not any(e["url"] == url and e["stage"] == "listing_parse" for e in errors):
            raise ValueError("No matching historical parser error")
        storage.checkpoint.finish_listing(url, "processing")
        try:
            new_ids, overlaps = storage.checkpoint.commit_listing_page(
                url, page.fingerprint, page.jobs
            )
        except Exception:
            storage.checkpoint.finish_listing(url, "failed")
            raise
        if page.next_url:
            storage.checkpoint.enqueue_listing(page.next_url)
        manifest = storage.read_manifest()
        manifest.listing_pages_succeeded += 1
        manifest.listing_pages_unique += 1
        manifest.urls_discovered += len(page.jobs)
        manifest.unique_ids_discovered = storage.checkpoint.count_details()
        manifest.listing_page_fingerprints.append(page.fingerprint)
        manifest.new_job_ids_per_page.append(new_ids)
        manifest.cross_page_overlaps += overlaps
        manifest.duplicates_skipped += overlaps
        for job in page.jobs:
            is_new = incremental.observe_discovery(
                job.source_name,
                job.source_job_id,
                seen_at=datetime.fromisoformat(meta["requested_at"]),
                batch_id=manifest.batch_id,
            )
            if is_new:
                manifest.incremental_new_ids += 1
            else:
                manifest.incremental_existing_ids += 1
        manifest.pagination_termination_reason = "recovered_from_saved_listing"
        if (
            not manifest.detail_failed
            and manifest.listing_pages_requested == manifest.listing_pages_succeeded
        ):
            manifest.status = "completed"
        storage.save_page_html(
            f"listing-recovered-{manifest.listing_pages_succeeded:03d}", html.decode()
        )
        storage.write_manifest(manifest)
        assert hashlib.sha256((batch / "jobs.jsonl").read_bytes()).hexdigest() == raw_hash
        report = {
            "recovered_at": datetime.now(UTC).isoformat(),
            "url": url,
            "new_requests": 0,
            "new_ids": new_ids,
            "overlaps": overlaps,
            "next_url": page.next_url,
            "jobs_jsonl_unchanged": True,
            "historical_errors_preserved": True,
            "before_manifest": original,
            "after_manifest": manifest.model_dump(mode="json"),
        }
        (batch / "listing-offline-recovery.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        return {k: v for k, v in report.items() if k not in {"before_manifest", "after_manifest"}}
    finally:
        incremental.close()
        storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("url")
    parser.add_argument(
        "--detail", action="store_true", help="Recover a detail parser failure offline"
    )
    args = parser.parse_args()
    operation = recover_detail if args.detail else recover
    print(json.dumps(operation(args.batch, args.url), ensure_ascii=False, indent=2))


def recover_detail(batch: Path, url: str) -> dict:
    identity = job_url(url)
    if identity is None:
        raise ValueError("Not a public Việc Làm 24h detail")
    original = json.loads((batch / "manifest.json").read_text())
    if original["source"] != "vieclam24h" or original["status"] == "running":
        raise ValueError("Recovery requires an idle Việc Làm 24h batch")
    if original["challenge_detected"] or original["termination_reason"] in {
        "access_blocked",
        "browser_challenge",
        "robots_denied",
        "robots_unavailable",
    }:
        raise ValueError("Do not reopen an access-blocked batch via parser recovery")
    captures = [json.loads(path.read_text()) for path in (batch / "http").glob("*.json")]
    captures = [
        m for m in captures if m.get("requested_url") == url and m.get("http_status") == 200
    ]
    if len(captures) != 1 or captures[0].get("blocked") or captures[0].get("challenge_type"):
        raise ValueError("Require one accessible HTTP 200 detail capture")
    meta = captures[0]
    html = gzip.decompress((batch / "http" / meta["html_path"]).read_bytes())
    if hashlib.sha256(html).hexdigest() != meta["html_sha256"]:
        raise ValueError("Saved HTML checksum mismatch")
    errors_path = batch / "errors.jsonl"
    errors = errors_path.read_bytes()
    if not any(
        e["url"] == url and e["stage"] == "detail_parse"
        for e in (json.loads(line) for line in errors.splitlines() if line.strip())
    ):
        raise ValueError("No matching historical detail parser error")
    prefix = (batch / "jobs.jsonl").read_bytes()
    storage = BatchStorage.resume(batch)
    incremental = IncrementalState(batch.parent.parent / "incremental_state.sqlite3")
    try:
        row = storage.checkpoint.connection.execute(
            "SELECT * FROM detail_queue WHERE source_job_id=?", (identity[0],)
        ).fetchone()
        if row is None:
            raise ValueError("Detail absent from checkpoint")
        if row["status"] == "completed":
            return {"already_recovered": True, "new_requests": 0}
        if row["status"] != "failed":
            raise ValueError("Recover only a failed parser detail")
        job = DiscoveredJob.model_validate(
            {
                key: row[key]
                for key in (
                    "source_job_id",
                    "source_name",
                    "source_url",
                    "canonical_url",
                    "listing_url",
                )
            }
        )
        relative_html = f"html/{identity[0]}.html.gz"
        existing_html = batch / relative_html
        if existing_html.exists():
            if gzip.decompress(existing_html.read_bytes()) != html:
                raise ValueError("Original detail HTML disagrees with captured response")
        else:
            storage.save_html(identity[0], html.decode())
        manifest = storage.read_manifest()
        record = parse_detail(
            html.decode(),
            job,
            crawled_at=datetime.fromisoformat(meta.get("received_at", meta["requested_at"])),
            snapshot_date=date.fromisoformat(batch.parent.name.removeprefix("snapshot_date=")),
            batch_id=manifest.batch_id,
            source_reported_total=manifest.source_reported_total,
            raw_html_path=relative_html,
        )
        if any(getattr(record, field) in (None, "", []) for field in REQUIRED_RECORD_FIELDS):
            raise ValueError("Recovered detail still lacks core fields")
        if manifest.detail_failed <= 0:
            raise ValueError("Historical failure count inconsistent")
        assert storage.append_job(record), "Do not append a duplicate recovered ID"
        storage.checkpoint.mark_completed(identity[0])
        manifest.records_written += 1
        manifest.detail_succeeded += 1
        manifest.detail_failed -= 1
        for field in MISSING_FIELD_NAMES:
            if getattr(record, field) in (None, "", []):
                manifest.missing_fields[field] = manifest.missing_fields.get(field, 0) + 1
        hash_status = incremental.update_content(
            record.source_name,
            record.source_job_id,
            content_hash=record.content_hash,
            fetched_at=record.crawled_at,
        )
        setattr(
            manifest,
            f"content_hash_{hash_status}",
            getattr(manifest, f"content_hash_{hash_status}") + 1,
        )
        manifest.status = "completed_with_errors" if manifest.detail_failed else "completed"
        manifest.finished_at = datetime.now(UTC)
        manifest.termination_reason = "recovered_detail_from_saved_html"
        storage.write_manifest(manifest)
        assert (batch / "jobs.jsonl").read_bytes().startswith(prefix)
        assert errors_path.read_bytes() == errors
        report = {
            "recovered_at": datetime.now(UTC).isoformat(),
            "url": url,
            "new_requests": 0,
            "appended_records": 1,
            "existing_rows_unchanged": True,
            "historical_errors_preserved": True,
            "before_manifest": original,
            "after_manifest": manifest.model_dump(mode="json"),
        }
        (batch / f"detail-offline-recovery-{identity[0]}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        return {k: v for k, v in report.items() if k not in {"before_manifest", "after_manifest"}}
    finally:
        incremental.close()
        storage.close()


if __name__ == "__main__":
    main()
