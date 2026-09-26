import gzip
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx
from selectolax.parser import HTMLParser

from job_crawler.config import ConfigError, CrawlConfig
from job_crawler.crawlers.careerlink import CareerLinkCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.careerlink import CareerLinkHttpFetcher, is_challenge

ROOT = Path(__file__).parents[1] / "fixtures/careerlink"
START = "https://www.careerlink.vn/vieclam/tim-kiem-viec-lam"


def config(tmp_path):
    return CrawlConfig(
        source="careerlink",
        mode="bounded",
        start_url=START,
        output_dir=tmp_path,
        project_owner_public_test=True,
        user_agent="job-warehouse-offline-test",
        max_pages=1,
        max_details=1,
        fetcher="http",
        save_html=True,
        require_complete_content=True,
        delay_min_seconds=3,
        delay_max_seconds=3,
        max_retries=0,
    )


def setup_routes():
    respx.get("https://www.careerlink.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    urls = []
    routes = []
    for i in (1, 2, 3):
        html = (ROOT / f"detail_{i}.html").read_text()
        url = HTMLParser(html).css_first('link[rel="canonical"]').attributes["href"]
        urls.append(url)
        routes.append(
            respx.get(url).mock(
                return_value=httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
            )
        )
    listing = (
        '<ul class="list-group">'
        + "".join(
            f'<li class="job-item"><a class="job-link" href="{u}">title</a></li>'
            for u in urls + urls[:1]
        )
        + "</ul>"
    )
    route = respx.get(START).mock(return_value=httpx.Response(200, text=listing))
    return route, routes, urls


@respx.mock
def test_resume_dedup_and_http_evidence(tmp_path):
    listing, details, _ = setup_routes()
    c = config(tmp_path)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        first = CrawlEngine(c, CareerLinkCrawler(), f).run()
    c = replace(c, max_details=3, resume=True, resume_batch_id=first.batch_id)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        second = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert second.records_written == second.detail_succeeded == second.detail_requested == 3
    assert listing.call_count == 1 and all(r.call_count == 1 for r in details)
    root = next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))
    rows = [json.loads(line) for line in (root / "jobs.jsonl").read_text().splitlines()]
    assert len({r["source_job_id"] for r in rows}) == 3
    assert all(r["job_description"] and r["candidate_requirements"] for r in rows)
    assert len(list((root / "http").glob("*.json"))) == 6  # two robots + listing + 3 details
    assert all((root / r["raw_html_path"]).exists() for r in rows)
    assert second.authorization_reference is None


@respx.mock
@pytest.mark.parametrize(
    "status,body",
    [
        (403, "Forbidden"),
        (429, "Rate limited"),
        (200, "<title>Just a moment</title>"),
        (200, "Please verify you are human"),
    ],
)
def test_stop_preserves_evidence_and_pending_checkpoint(tmp_path, status, body):
    _, details, urls = setup_routes()
    details[0].mock(
        return_value=httpx.Response(status, text=body, headers={"Content-Type": "text/html"})
    )
    c = replace(config(tmp_path), max_details=20)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        result = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert result.status == "stopped" and result.records_written == 0
    assert result.detail_requested == 1 and details[1].call_count == 0
    root = next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))
    metas = [json.loads(p.read_text()) for p in (root / "http").glob("*.json")]
    meta = next(m for m in metas if m["requested_url"] == urls[0])
    assert meta["http_status"] == status
    assert gzip.decompress((root / "http" / meta["body_path"]).read_bytes()).decode() == body
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        assert db.execute("SELECT status FROM detail_queue LIMIT 1").fetchone()[0] == "pending"


def test_passive_login_widget_is_not_a_challenge():
    assert not is_challenge("""<div id="loginModal"><form id="jobseeker_login_form">
        <div id="captcha_container"></div></form></div>""")
    assert is_challenge('<div id="captcha_container">Solve CAPTCHA</div>')
    assert is_challenge(
        '<div id="loginModal"><form id="jobseeker_login_form">'
        '<div id="captcha_container">Solve CAPTCHA</div></form></div>'
    )
    assert is_challenge("<div>cf-chl-test</div>")


@pytest.mark.parametrize(
    "change",
    [
        {"max_pages": 7},
        {"max_details": 301},
        {"max_pages": None},
        {"max_details": None},
        {"source": "vietnamworks"},
        {"fetcher": "auto"},
        {"delay_min_seconds": 2},
        {"max_retries": 1},
        {"save_html": False},
        {"require_complete_content": False},
    ],
)
def test_bounded_config_guards(tmp_path, change):
    with pytest.raises(ConfigError):
        replace(config(tmp_path), **change).validate()
