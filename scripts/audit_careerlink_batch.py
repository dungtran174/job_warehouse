"""Offline audit of raw JSONL against complete saved detail DOM sections."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from selectolax.parser import HTMLParser

from job_crawler.models import JobRecord
from job_crawler.utils.hash import job_content_hash

FIELDS = {
    "job_title": "h1#job-title",
    "company_name": ".job-detail-header .org-name",
    "job_description": "#section-job-description .rich-text-content",
    "candidate_requirements": "#section-job-skills .rich-text-content",
    "salary_raw": "#job-salary .text-primary",
    "location_raw": "#job-location",
}


def audit(root: Path) -> dict:
    records = [
        JobRecord.model_validate_json(line)
        for line in (root / "jobs.jsonl").read_text().splitlines()
        if line.strip()
    ]
    errors = []
    rows = []
    completeness = Counter()
    seen = set()
    http_metadata = [json.loads(p.read_text()) for p in (root / "http").glob("*.json")]
    statuses = Counter(str(m["http_status"]) for m in http_metadata)
    for record in records:
        checks = {}
        if record.source_job_id in seen:
            errors.append(f"Duplicate ID: {record.source_job_id}")
        seen.add(record.source_job_id)
        if not record.raw_html_path:
            errors.append(f"Missing HTML: {record.source_job_id}")
            continue
        html = gzip.decompress((root / record.raw_html_path).read_bytes()).decode()
        tree = HTMLParser(html)
        for field, selector in FIELDS.items():
            nodes = tree.css(selector)
            if field == "location_raw" and not nodes:
                nodes = tree.css("#job-offices")
            expected = (
                re.sub(
                    r"\s+", " ", " ".join(n.text(separator=" ", strip=True) for n in nodes)
                ).strip()
                or None
            )
            actual = getattr(record, field)
            match = expected == actual
            if actual:
                completeness[field] += 1
            if not match:
                errors.append(f"DOM mismatch: {record.source_job_id}/{field}")
            checks[field] = {
                "full_dom_match": match,
                "characters": len(actual or ""),
                "sha256": hashlib.sha256((actual or "").encode()).hexdigest(),
            }
        canonical = tree.css_first('link[rel="canonical"]')
        if not canonical or canonical.attributes.get("href") != record.canonical_url:
            errors.append(f"Canonical mismatch: {record.source_job_id}")
        if job_content_hash(record.model_dump()) != record.content_hash:
            errors.append(f"Hash mismatch: {record.source_job_id}")
        posted_nodes = tree.css("#job-date .date-from")
        posted = re.sub(
            r"\s+", " ", " ".join(n.text(separator=" ", strip=True) for n in posted_nodes)
        ).strip()
        posted = posted.removeprefix("Ngày đăng tuyển").strip() or None
        if record.posted_at_raw != posted:
            errors.append(f"Posted date mismatch: {record.source_job_id}")
        if record.posted_at_raw:
            completeness["posted_at_raw"] += 1
        rows.append(
            {
                "source_job_id": record.source_job_id,
                "canonical_url": record.canonical_url,
                "fields": checks,
            }
        )
    return {
        "batch_path": str(root),
        "jsonl_lines": len(records),
        "unique_ids": len(seen),
        "field_completeness": dict(completeness),
        "http_status_counts": dict(statuses),
        "errors": errors,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.batch)
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2)
    )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
