import gzip
import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
from selectolax.parser import HTMLParser

from job_crawler.config import ConfigError, CrawlConfig
from job_crawler.crawlers.timviec365 import Timviec365Crawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.base import FetchError
from job_crawler.fetchers.factory import create_fetcher
from job_crawler.fetchers.timviec365 import ROBOTS, Timviec365HttpFetcher, robots_denies
from job_crawler.parsers.timviec365 import START, job_url, parse_detail, parse_listing

FIXTURES = Path(__file__).parents[1] / "fixtures/timviec365"
IDS = ("2070499", "2070495", "2070494")


def detail(job_id):
    return (FIXTURES / f"detail_{job_id}.html").read_text()


def url(job_id):
    return HTMLParser(detail(job_id)).css_first('link[rel="canonical"]').attributes["href"]


def listing():
    cards = "".join(
        f'<div class="item_vl" data-newid="{i}" data-newghim="0">'
        f'<h2 class="box_title_new"><a class="title_new" href="{url(i)}">Preview</a>'
        "</h2></div>"
        for i in (*IDS, IDS[0])
    )
    return (
        '<div class="boxContentListNew"><div class="boxShowListNew">' + cards + "</div></div>"
        '<div class="box_post"><a href="/advertisement-p999.html">Ad</a></div>'
        '<ul class="pagination"><li class="pagi_pre">'
        '<a href="/viec-lam?page=2">&gt;</a></li></ul>'
    )


def record(html, job_id=IDS[0]):
    job = next(j for j in parse_listing(listing(), START).jobs if j.source_job_id == job_id)
    now = datetime.now(UTC)
    return parse_detail(
        html,
        job,
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
    )


@pytest.mark.parametrize("job_id", IDS)
def test_detail_has_complete_sections_and_no_invented_posting_date(job_id):
    row = record(detail(job_id), job_id)
    assert row.source_job_id == job_id and row.source_name == "timviec365"
    assert row.company_name and row.job_title
    assert row.job_description == f"Đoạn đầu kiểm thử {job_id}-1. Đoạn cuối kiểm thử {job_id}-1."
    assert f"Đoạn cuối kiểm thử {job_id}-3." in row.candidate_requirements
    assert row.candidate_requirements.endswith(row.requirement_tags[-1])
    assert row.salary_raw and row.location_raw and row.application_deadline_raw
    assert row.posted_at_raw is None  # timeUpdate is not datePosted.
    assert len(row.content_hash) == 64


def test_optional_missing_never_uses_listing_or_recommended_content():
    html = f'<link rel="canonical" href="{url(IDS[0])}">'
    html += f'<div class="boxDetailInfo"><h1 class="titleNew" data-id="{IDS[0]}">Title</h1></div>'
    html += '<aside><a class="company_name">Wrong company</a><p>Preview</p></aside>'
    row = record(html)
    assert row.company_name is row.salary_raw is row.location_raw is None
    assert row.job_description is row.candidate_requirements is None
    assert row.posted_at_raw is None
    with pytest.raises(ValueError, match="ID"):
        record(html.replace(f'data-id="{IDS[0]}"', 'data-id="999"'))
    with pytest.raises(ValueError, match="ID"):
        record(html.replace(f"-p{IDS[0]}.html", "-p999.html"))


def test_main_listing_dedup_and_pagination():
    page = parse_listing(listing(), START)
    assert [j.source_job_id for j in page.jobs] == list(IDS)
    assert page.next_url == START + "?page=2"
    assert not parse_listing('<a href="/featured-p999.html">Ad</a>', START).jobs
    assert job_url("https://storage1.timviec365.vn/job-p1.html") is None
    with pytest.raises(ValueError, match="pagination"):
        parse_listing(listing().replace("/viec-lam?page=2", "https://other.example/"), START)
    with pytest.raises(ValueError, match="pagination"):
        parse_listing(listing().replace("page=2", "page=3"), START)
    with pytest.raises(ValueError, match="ID mismatch"):
        parse_listing(listing().replace('data-newid="2070499"', 'data-newid="999"'), START)
    assert not parse_listing(listing().replace('data-newghim="0"', 'data-newghim="1"'), START).jobs


def config(tmp_path):
    return CrawlConfig(
        source="timviec365",
        start_url=START,
        output_dir=tmp_path,
        project_owner_public_test=True,
        user_agent="job-warehouse-offline-test",
        max_pages=1,
        max_details=1,
        fetcher="http",
        save_html=True,
        require_complete_content=True,
        delay_min_seconds=10,
        delay_max_seconds=10,
        max_retries=0,
    )


def routes():
    respx.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nAllow: /"))
    main = respx.get(START).mock(return_value=httpx.Response(200, text=listing()))
    details = [
        respx.get(url(i)).mock(return_value=httpx.Response(200, text=detail(i))) for i in IDS
    ]
    return main, details


@respx.mock
def test_raw_resume_dedup_and_capture(tmp_path):
    main, details = routes()
    c = config(tmp_path)
    with Timviec365HttpFetcher(c, sleep=lambda _: None) as fetcher:
        first = CrawlEngine(c, Timviec365Crawler(), fetcher).run()
    root = next(tmp_path.glob("timviec365/snapshot_date=*/batch_id=*"))
    original_line = (root / "jobs.jsonl").read_bytes()
    c = replace(c, max_details=3, resume=True, resume_batch_id=first.batch_id)
    for _ in range(2):
        with Timviec365HttpFetcher(c, sleep=lambda _: None) as fetcher:
            last = CrawlEngine(c, Timviec365Crawler(), fetcher).run()
    assert last.detail_requested == last.detail_succeeded == last.records_written == 3
    assert main.call_count == 1 and all(r.call_count == 1 for r in details)
    assert (root / "jobs.jsonl").read_bytes().startswith(original_line)
    rows = [json.loads(line) for line in (root / "jobs.jsonl").read_text().splitlines()]
    assert len({r["source_job_id"] for r in rows}) == 3
    assert all((root / r["raw_html_path"]).exists() for r in rows)
    assert last.access_basis == "project_owner_public_test" and last.authorization_reference is None
    with create_fetcher(c) as fetcher:
        assert isinstance(fetcher, Timviec365HttpFetcher)


@respx.mock
@pytest.mark.parametrize(
    "status,body",
    [
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (429, "Slow down"),
        (200, "<div>hCaptcha</div>"),
        (200, "x" * 200001 + "cf-chl-test"),
        (200, "<title>Just a moment</title>"),
        (302, "Redirect"),
    ],
)
def test_stop_without_retry_and_save_body(tmp_path, status, body):
    _, details = routes()
    details[0].mock(
        return_value=httpx.Response(
            status, text=body, headers={"Retry-After": "120", "Location": "/other"}
        )
    )
    c = replace(config(tmp_path), max_details=3)
    with Timviec365HttpFetcher(c, sleep=lambda _: None) as fetcher:
        result = CrawlEngine(c, Timviec365Crawler(), fetcher).run()
        with pytest.raises(FetchError, match="already stopped"):
            fetcher.get(url(IDS[0]))
    assert result.status == "stopped" and result.records_written == 0
    assert result.detail_requested == 1 and details[0].call_count == 1
    assert details[1].call_count == details[2].call_count == 0
    root = next(tmp_path.glob("timviec365/snapshot_date=*/batch_id=*"))
    metas = [json.loads(p.read_text()) for p in (root / "http").glob("*.json")]
    meta = next(m for m in metas if m["requested_url"] == url(IDS[0]))
    assert meta["http_status"] == status and meta["retry_after"] == "120"
    assert gzip.decompress((root / "http" / meta["body_path"]).read_bytes()).decode() == body
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        assert db.execute("SELECT status FROM detail_queue LIMIT 1").fetchone()[0] == "pending"


def test_robots_specific_disallow_wildcards_and_host_scope():
    text = (
        "User-agent: *\nAllow: /\nDisallow: /tim-kiem\n"
        "Disallow: /*?type_search=\nDisallow: /admin/*"
    )
    assert robots_denies(text, "https://timviec365.vn/tim-kiem")
    assert robots_denies(text, START + "?type_search=1")
    assert not robots_denies(text, START)
    assert robots_denies("User-agent: *\nDisallow: /", url(IDS[0]))


@respx.mock
def test_robots_and_pdf_host_denied_before_request(tmp_path):
    respx.get(ROBOTS).mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\nDisallow: /viec-lam")
    )
    c = config(tmp_path)
    with Timviec365HttpFetcher(c, sleep=lambda _: None) as fetcher:
        fetcher.configure_run(tmp_path, "offline")
        fetcher.get(ROBOTS)
        with pytest.raises(FetchError, match="robots denied"):
            fetcher.get(START)
    assert len(respx.calls) == 1
    with Timviec365HttpFetcher(c, sleep=lambda _: None) as fetcher:
        fetcher.configure_run(tmp_path, "offline")
        with pytest.raises(FetchError, match="scope"):
            fetcher.get("https://storage1.timviec365.vn/file.pdf")
    assert len(respx.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"max_pages": 2},
        {"max_details": 4},
        {"mode": "medium"},
        {"fetcher": "auto"},
        {"delay_min_seconds": 9},
        {"max_retries": 1},
        {"save_html": False},
        {"require_complete_content": False},
        {"project_owner_public_test": False},
        {"authorization_reference": "not-a-real-reference"},
    ],
)
def test_sample_guards(tmp_path, change):
    with pytest.raises(ConfigError):
        replace(config(tmp_path), **change).validate()
