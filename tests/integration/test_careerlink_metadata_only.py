"""Offline evidence checks for CareerLink without successful full-page capture."""

import gzip
import hashlib
import json
import runpy
import sqlite3
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx
from selectolax.parser import HTMLParser

from job_crawler.config import CrawlConfig
from job_crawler.crawlers.careerlink import CareerLinkCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.careerlink import CareerLinkHttpFetcher

FIXTURES = Path(__file__).parents[1] / "fixtures/careerlink"
START = "https://www.careerlink.vn/vieclam/tim-kiem-viec-lam"
AUDIT = runpy.run_path(str(Path(__file__).parents[2] / "scripts/audit_careerlink_batch.py"))[
    "audit"
]


def setup_routes():
    respx.get("https://www.careerlink.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    htmls = [(FIXTURES / f"detail_{i}.html").read_text() for i in (1, 2)]
    urls = [
        HTMLParser(html).css_first('link[rel="canonical"]').attributes["href"] for html in htmls
    ]
    listing = (
        "<ul class='list-group'>"
        + "".join(
            f"<li class='job-item'><a class='job-link' href='{url}'>job</a></li>" for url in urls
        )
        + "</ul>"
    )
    respx.get(START).mock(return_value=httpx.Response(200, text=listing))
    routes = [
        respx.get(url).mock(
            return_value=httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        )
        for url, html in zip(urls, htmls, strict=True)
    ]
    return htmls, urls, routes


def config(tmp_path, *, save_html=False, max_details=1):
    return CrawlConfig(
        source="careerlink",
        mode="bounded",
        start_url=START,
        output_dir=tmp_path,
        project_owner_public_test=True,
        user_agent="job-warehouse-offline-test",
        max_pages=1,
        max_details=max_details,
        fetcher="http",
        save_html=save_html,
        require_complete_content=True,
        delay_min_seconds=10,
        delay_max_seconds=15,
        max_retries=0,
    )


def batch_root(tmp_path):
    return next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))


@respx.mock
def test_metadata_only_success_has_no_full_response_body(tmp_path):
    htmls, urls, _ = setup_routes()
    cfg = config(tmp_path)
    cfg.validate()
    with CareerLinkHttpFetcher(cfg, sleep=lambda _: None) as fetcher:
        manifest = CrawlEngine(cfg, CareerLinkCrawler(), fetcher).run()
    root = batch_root(tmp_path)
    row = json.loads((root / "jobs.jsonl").read_text().splitlines()[0])
    assert manifest.records_written == 1 and row["raw_html_path"] is None
    assert row["source_job_id"] == urls[0].split("/")[-1]
    assert row["job_description"] and row["candidate_requirements"]
    assert not (root / "html").exists()
    metas = [json.loads(p.read_text()) for p in (root / "http").glob("*.json")]
    assert len(metas) == 3 and not list((root / "http").glob("*.gz"))
    assert all(m["evidence_schema_version"] == "2" and m["body_path"] is None for m in metas)
    detail = next(m for m in metas if m["requested_url"] == urls[0])
    assert detail["http_status"] == 200 and detail["challenge_detected"] is False
    assert detail["requested_job_id"] == detail["final_job_id"] == row["source_job_id"]
    assert detail["canonical_job_id"] == row["source_job_id"]
    assert detail["body_sha256"] == hashlib.sha256(htmls[0].encode()).hexdigest()
    assert manifest.run_settings[-1].success_body_storage == "metadata_only"
    audit = AUDIT(root)
    assert audit["errors"] == [] and audit["metadata_only_records"] == 1
    assert audit["html_verified_records"] == 0


@respx.mock
def test_resume_old_full_html_batch_records_mixed_evidence_version(tmp_path):
    _, urls, routes = setup_routes()
    cfg = config(tmp_path, save_html=True)
    with CareerLinkHttpFetcher(cfg, sleep=lambda _: None) as fetcher:
        first = CrawlEngine(cfg, CareerLinkCrawler(), fetcher).run()
    root = batch_root(tmp_path)
    before = (root / "jobs.jsonl").read_bytes()
    old = json.loads(before.splitlines()[0])
    old_html = (root / old["raw_html_path"]).read_bytes()
    saved_manifest = json.loads((root / "manifest.json").read_text())
    saved_manifest["run_settings"][0].pop("success_body_storage")
    (root / "manifest.json").write_text(json.dumps(saved_manifest))
    resumed = replace(
        cfg, save_html=False, resume=True, resume_batch_id=first.batch_id, max_details=2
    )
    with CareerLinkHttpFetcher(resumed, sleep=lambda _: None) as fetcher:
        second = CrawlEngine(resumed, CareerLinkCrawler(), fetcher).run()
    rows = [json.loads(line) for line in (root / "jobs.jsonl").read_text().splitlines()]
    assert (root / "jobs.jsonl").read_bytes().startswith(before)
    assert (root / old["raw_html_path"]).read_bytes() == old_html
    assert len(rows) == len({r["source_job_id"] for r in rows}) == 2
    assert rows[0]["raw_html_path"] and rows[1]["raw_html_path"] is None
    assert rows[1]["source_job_id"] == urls[1].split("/")[-1]
    assert [s.success_body_storage for s in second.run_settings] == ["full", "metadata_only"]
    assert routes[0].call_count == routes[1].call_count == 1
    audit = AUDIT(root)
    assert audit["errors"] == []
    assert audit["html_verified_records"] == audit["metadata_only_records"] == 1


@respx.mock
@pytest.mark.parametrize(
    "status,body",
    [(200, '<div class="h-captcha"></div>'), (403, "Forbidden"), (429, "Rate limited")],
)
def test_metadata_only_still_saves_blocked_body_and_stops(tmp_path, status, body):
    _, urls, routes = setup_routes()
    routes[0].mock(
        return_value=httpx.Response(status, text=body, headers={"Content-Type": "text/html"})
    )
    cfg = config(tmp_path, max_details=3)
    with CareerLinkHttpFetcher(cfg, sleep=lambda _: None) as fetcher:
        result = CrawlEngine(cfg, CareerLinkCrawler(), fetcher).run()
    root = batch_root(tmp_path)
    assert result.status == "stopped" and result.termination_reason == "access_blocked"
    assert result.detail_requested == 1 and result.records_written == 0
    assert routes[1].call_count == 0
    meta = next(
        json.loads(p.read_text())
        for p in (root / "http").glob("*.json")
        if json.loads(p.read_text())["requested_url"] == urls[0]
    )
    assert meta["http_status"] == status and meta["body_path"]
    assert meta["challenge_detected"] is (status == 200)
    assert gzip.decompress((root / "http" / meta["body_path"]).read_bytes()).decode() == body
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        assert (
            db.execute("SELECT status FROM detail_queue ORDER BY rowid LIMIT 1").fetchone()[0]
            == "pending"
        )
