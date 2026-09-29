"""Audit an idle VietnamWorks raw batch against saved detail DOM offline."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from statistics import median
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from job_crawler.crawlers.vietnamworks import VietnamWorksCrawler
from job_crawler.fetchers.vietnamworks_browser import LISTING_PATHS, ROBOTS
from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.parsers.vietnamworks_detail import job_id_from_url, plain
from job_crawler.parsers.vietnamworks_listing import parse_listing


def audit(batch: Path) -> dict:
    manifest = json.loads((batch / "manifest.json").read_text())
    if manifest["source"] != "vietnamworks" or manifest["status"] == "running":
        raise ValueError("Audit an idle VietnamWorks batch")
    raw = (batch / "jobs.jsonl").read_bytes()
    records = [JobRecord.model_validate_json(line) for line in raw.splitlines() if line.strip()]
    ids = [r.source_job_id for r in records]
    assert len(ids) == len(set(ids)) == manifest["records_written"] == manifest["detail_succeeded"]
    evidence = []
    for r in records:
        assert r.raw_html_path and r.source_name == "vietnamworks"
        assert job_id_from_url(r.canonical_url) == r.source_job_id
        assert urlsplit(r.listing_url).path in LISTING_PATHS
        html = gzip.decompress((batch / r.raw_html_path).read_bytes()).decode()
        tree = HTMLParser(html)
        assert plain(tree.css_first("h1").html) == r.job_title
        company_links = {plain(n.html) for n in tree.css('a[href*="/nha-tuyen-dung/"]')}
        assert r.company_name in company_links
        sections = {}
        for heading, field in (
            ("Mô tả công việc", "job_description"),
            ("Yêu cầu công việc", "candidate_requirements"),
        ):
            h2 = next(n for n in tree.css("h2") if n.text(strip=True) == heading)
            # Independent observed content selector; excludes the prompt banner.
            container = h2.parent.css_first('div[class*="sc-1671001a-6"] > div')
            assert container is not None
            text = plain(container.html)
            assert text and text == getattr(r, field)
            sections[field] = {
                "characters": len(text),
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "first_100": text[:100],
                "last_100": text[-100:],
                "full_DOM_equals_JSONL": True,
            }
        parsed = VietnamWorksCrawler().parse_detail(
            html,
            DiscoveredJob(
                source_name=r.source_name,
                source_job_id=r.source_job_id,
                source_url=r.source_url,
                canonical_url=r.canonical_url,
                listing_url=r.listing_url,
            ),
            crawled_at=r.crawled_at,
            snapshot_date=r.snapshot_date,
            batch_id=r.batch_id,
            source_reported_total=r.source_reported_total,
            raw_html_path=r.raw_html_path,
        )
        for field in (
            "job_title",
            "company_name",
            "job_description",
            "candidate_requirements",
            "salary_raw",
            "location_raw",
            "posted_at_raw",
            "content_hash",
        ):
            assert getattr(parsed, field) == getattr(r, field), (r.source_job_id, field)
        evidence.append({"id": r.source_job_id, "html": r.raw_html_path, **sections})
    metadata = [json.loads(p.read_text()) for p in sorted((batch / "http").glob("*.json"))]
    listing_audit = []
    for m in metadata:
        if (
            urlsplit(m["requested_url"]).path in LISTING_PATHS
            and m["http_status"] == 200
            and not m["blocked"]
        ):
            html = gzip.decompress((batch / "http" / m["html_path"]).read_bytes()).decode()
            page = parse_listing(html, m["final_url"])
            listing_audit.append(
                {
                    "url": m["final_url"],
                    "requested_url": m["requested_url"],
                    "ids": [j.source_job_id for j in page.jobs],
                    "next_url": page.next_url,
                }
            )
    main_ids = {i for page in listing_audit for i in page["ids"]}
    assert set(ids) <= main_ids
    with sqlite3.connect(f"file:{batch / 'checkpoint.sqlite3'}?mode=ro", uri=True) as db:
        checkpoint = {
            name: dict(db.execute(f"SELECT status, count(*) FROM {name}_queue GROUP BY status"))
            for name in ("listing", "detail")
        }
    detail_requests = [m for m in metadata if job_id_from_url(m["requested_url"])]
    return {
        "manifest": manifest,
        "batch": str(batch),
        "records": len(records),
        "unique_ids": len(set(ids)),
        "duplicate_ids": len(ids) - len(set(ids)),
        "jobs_sha256": hashlib.sha256(raw).hexdigest(),
        "row_sha256": [hashlib.sha256(line).hexdigest() for line in raw.splitlines()],
        "missing_fields": {
            field: sum(not r.model_dump().get(field) for r in records)
            for field in JobRecord.model_fields
        }
        if records
        else {},
        "full_description_and_requirements": len(evidence),
        "content_lengths": {
            field: {"min": min(values), "median": median(values), "max": max(values)}
            for field in ("job_description", "candidate_requirements")
            if (values := [len(getattr(r, field)) for r in records])
        },
        "primary_navigation_attempts": len(metadata),
        "primary_document_responses": sum(
            len(m.get("main_document_responses", [])) for m in metadata
        ),
        "primary_status_counts": dict(Counter(str(m["http_status"]) for m in metadata)),
        "source_denial_count": sum(len(m["source_denials"]) for m in metadata),
        "robots_requests": sum(m["requested_url"] == ROBOTS for m in metadata),
        "actual_detail_navigation_attempts": len(detail_requests),
        "detail_status_counts": dict(Counter(str(m["http_status"]) for m in detail_requests)),
        "detail_URL_duplicates": len(detail_requests)
        - len({m["requested_url"] for m in detail_requests}),
        "listing_audit": listing_audit,
        "main_listing_unique_ids": len(main_ids),
        "checkpoint": checkpoint,
        "detail_evidence": evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = audit(args.batch)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "manifest",
                    "row_sha256",
                    "missing_fields",
                    "listing_audit",
                    "detail_evidence",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
