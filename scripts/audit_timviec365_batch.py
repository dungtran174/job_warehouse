"""Offline milestone audit; never fetches pages or changes a raw batch."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from selectolax.parser import HTMLParser

from job_crawler.models import JobRecord
from job_crawler.utils.hash import job_content_hash


def audit(batch: Path) -> dict:
    payload = (batch / "jobs.jsonl").read_bytes()
    records = [JobRecord.model_validate_json(line) for line in payload.splitlines()]
    ids = {r.source_job_id for r in records}
    if len(ids) != len(records):
        raise ValueError("Duplicate ID in raw JSONL")
    comparisons = []
    for record in records:
        if record.content_hash != job_content_hash(record.model_dump()):
            raise ValueError(f"Hash mismatch: {record.source_job_id}")
        if not record.raw_html_path:
            raise ValueError("Missing HTML evidence")
        path = (batch / record.raw_html_path).resolve()
        if not path.is_relative_to(batch.resolve()):
            raise ValueError("HTML path outside batch")
        tree = HTMLParser(gzip.decompress(path.read_bytes()).decode())
        title = tree.css_first("h1.titleNew[data-id]")
        if title is None or title.attributes["data-id"] != record.source_job_id:
            raise ValueError("Detail ID mismatch")
        company = tree.css_first(".boxTitleNameNtd a.linkNtd")
        canonical = tree.css_first('link[rel="canonical"]')
        if (
            company is None
            or canonical is None
            or re.sub(r"\s+", " ", title.text(separator=" ", strip=True)) != record.job_title
            or re.sub(r"\s+", " ", company.text(separator=" ", strip=True)) != record.company_name
            or canonical.attributes.get("href") != record.canonical_url
        ):
            raise ValueError("Detail title/company/canonical mismatch")
        lengths = {}
        for heading, field in (
            ("Mô tả công việc", "job_description"),
            ("Yêu cầu", "candidate_requirements"),
        ):
            nodes = [n for n in tree.css("h2.titleInfoSpecific") if n.text(strip=True) == heading]
            if len(nodes) != 1:
                raise ValueError(f"Missing/ambiguous {field}: {record.source_job_id}")
            body = nodes[0].parent.parent.css_first(".boxMainInfoSpecific")
            expected = re.sub(r"\s+", " ", body.text(separator=" ", strip=True)).strip()
            actual = getattr(record, field)
            if not expected or expected != actual:
                raise ValueError(f"Truncated/different {field}: {record.source_job_id}")
            lengths[field] = {"chars": len(actual), "head": actual[:80], "tail": actual[-80:]}
        if record.posted_at_raw is not None:
            raise ValueError("Unexpected posting date: review against update-date label")
        comparisons.append({"id": record.source_job_id, "whole_sections_match": True, **lengths})
    metas = [json.loads(p.read_text()) for p in sorted((batch / "http").glob("*.json"))]
    times = [datetime.fromisoformat(m["requested_at"]) for m in metas]
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:], strict=False)]
    # From response completion to the next request: distinguish configured delay from latency.
    idle = [
        (
            datetime.fromisoformat(b["requested_at"]) - datetime.fromisoformat(a["received_at"])
        ).total_seconds()
        for a, b in zip(metas, metas[1:], strict=False)
    ]
    with sqlite3.connect(f"file:{batch}/checkpoint.sqlite3?mode=ro", uri=True) as db:
        queue = dict(db.execute("SELECT status,COUNT(*) FROM detail_queue GROUP BY status"))
    all_ids = set()
    for path in batch.parent.parent.glob("snapshot_date=*/batch_id=*/jobs.jsonl"):
        all_ids.update(json.loads(line)["source_job_id"] for line in path.read_text().splitlines())
    coverage = {
        field: sum(getattr(r, field) not in (None, "", []) for r in records)
        for field in (
            "job_title",
            "company_name",
            "job_description",
            "candidate_requirements",
            "salary_raw",
            "location_raw",
            "posted_at_raw",
        )
    }
    return {
        "batch": str(batch),
        "records": len(records),
        "batch_unique_ids": len(ids),
        "source_total_unique_ids": len(all_ids),
        "jobs_sha256": hashlib.sha256(payload).hexdigest(),
        "manifest": json.loads((batch / "manifest.json").read_text()),
        "queue": queue,
        "errors": [json.loads(line) for line in (batch / "errors.jsonl").read_text().splitlines()],
        "nonempty_fields": coverage,
        "whole_html_sections_verified": len(comparisons),
        "request_count": len(metas),
        "http_statuses": dict(Counter(m["http_status"] for m in metas)),
        "request_gap_seconds_min": min(gaps) if gaps else None,
        "idle_seconds_min": min(idle) if idle else None,
        "detail_request_ids": [
            m["requested_url"]
            for m in metas
            if "-p" in m["requested_url"] and m["requested_url"].endswith(".html")
        ],
        "detail_audit": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.batch)
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "records",
                    "source_total_unique_ids",
                    "whole_html_sections_verified",
                    "queue",
                    "nonempty_fields",
                    "http_statuses",
                    "idle_seconds_min",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
