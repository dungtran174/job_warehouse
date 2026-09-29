"""Audit saved Việc Làm 24h JSONL against whole detail DOM/embedded content offline."""

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
from statistics import median

from selectolax.parser import HTMLParser

from job_crawler.models import JobRecord
from job_crawler.parsers.vieclam24h import START_URL, job_url, parse_listing
from job_crawler.utils.hash import job_content_hash


def text_content(html: str) -> str:
    return re.sub(r"\s+", " ", HTMLParser(html).root.text(separator=" ", strip=True)).strip()


def audit(batch: Path) -> dict:
    manifest = json.loads((batch / "manifest.json").read_text())
    if manifest["source"] != "vieclam24h" or manifest["status"] == "running":
        raise ValueError("Audit an idle Việc Làm 24h batch")
    raw = (batch / "jobs.jsonl").read_bytes()
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    ids = [row["source_job_id"] for row in records]
    assert len(ids) == len(set(ids)) == manifest["records_written"]
    assert len(ids) == manifest["detail_succeeded"]
    evidence = []
    for row in records:
        JobRecord.model_validate(row)
        assert job_content_hash(row) == row["content_hash"]
        html_path = batch / row["raw_html_path"]
        html = gzip.decompress(html_path.read_bytes()).decode()
        tree = HTMLParser(html)
        detail = json.loads(tree.css_first("script#__NEXT_DATA__").text())["props"]["initialState"][
            "api"
        ]["jobDetailHiddenContact"]["data"]
        assert str(detail["id"]) == row["source_job_id"]
        assert job_url(row["canonical_url"])[0] == row["source_job_id"]
        assert text_content(tree.css_first("main h1").html) == row["job_title"]
        posting = next(
            obj
            for node in tree.css('script[type="application/ld+json"]')
            if isinstance(obj := json.loads(node.text()), dict) and obj.get("@type") == "JobPosting"
        )
        assert posting["hiringOrganization"]["name"] == row["company_name"]
        assert " ".join(row["company_name"].split()) in text_content(tree.css_first("main").html)
        parts = {}
        for heading, field, embedded_field in (
            ("Mô tả công việc", "job_description", "description_html"),
            ("Yêu cầu công việc", "candidate_requirements", "other_requirement_html"),
        ):
            node = next(n for n in tree.css("main h2") if text_content(n.html) == heading)
            full_dom = text_content(node.parent.css_first(".text-description").html)
            assert full_dom and full_dom == row[field]
            assert full_dom == text_content(detail[embedded_field])
            parts[field] = {
                "characters": len(full_dom),
                "text_sha256": hashlib.sha256(full_dom.encode()).hexdigest(),
                "full_dom_equals_embedded_and_jsonl": True,
            }
        posted_labels = [
            n
            for n in tree.css("main div")
            if text_content(n.html) == "Ngày đăng"
            and not any(child.tag == "div" for child in n.iter())
        ]
        if posted_labels:
            assert row["posted_at_raw"] == text_content(posted_labels[0].next.html)
        else:
            assert row["posted_at_raw"] == posting.get("datePosted")
        expiry = posting.get("validThrough")
        expired = bool(
            expiry and datetime.fromisoformat(expiry) < datetime.fromisoformat(row["crawled_at"])
        )
        evidence.append(
            {
                "id": row["source_job_id"],
                "html": row["raw_html_path"],
                "expired_at_crawl": expired,
                **parts,
            }
        )
    metadata = [json.loads(path.read_text()) for path in (batch / "http").glob("*.json")]
    listings = []
    for meta in metadata:
        if (
            meta["requested_url"].startswith(START_URL)
            and meta["http_status"] == 200
            and not meta["blocked"]
        ):
            html = gzip.decompress((batch / "http" / meta["html_path"]).read_bytes()).decode()
            page = parse_listing(html, meta["final_url"])
            listings.append(
                {
                    "url": meta["final_url"],
                    "ids": [j.source_job_id for j in page.jobs],
                    "next_url": page.next_url,
                }
            )
    with sqlite3.connect(f"file:{batch / 'checkpoint.sqlite3'}?mode=ro", uri=True) as db:
        checkpoint = {
            name: dict(db.execute(f"SELECT status, count(*) FROM {name}_queue GROUP BY status"))
            for name in ("listing", "detail")
        }
    return {
        "manifest": manifest,
        "records": len(records),
        "unique_ids": len(set(ids)),
        "duplicate_ids": len(ids) - len(set(ids)),
        "jobs_sha256": hashlib.sha256(raw).hexdigest(),
        "row_sha256": [hashlib.sha256(line).hexdigest() for line in raw.splitlines()],
        "missing_fields": {key: sum(not row.get(key) for row in records) for key in records[0]}
        if records
        else {},
        "full_description_and_requirements": len(evidence),
        "expired_at_crawl": sum(e["expired_at_crawl"] for e in evidence),
        "content_lengths": {
            field: {"min": min(values), "median": median(values), "max": max(values)}
            for field in ("job_description", "candidate_requirements")
            if (values := [len(row[field]) for row in records])
        },
        "primary_navigation_count": len(metadata),
        "primary_status_counts": dict(Counter(str(m["http_status"]) for m in metadata)),
        "primary_blocked": sum(m["blocked"] for m in metadata),
        "listing_audit": listings,
        "main_listing_unique_ids": len({job_id for page in listings for job_id in page["ids"]}),
        "checkpoint": checkpoint,
        "detail_evidence": evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(args.batch)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in {
                    "manifest",
                    "row_sha256",
                    "listing_audit",
                    "detail_evidence",
                    "missing_fields",
                }
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
