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
        delay_min_seconds=10,
        delay_max_seconds=15,
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
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (429, "Rate limited"),
        (200, '<div class="h-captcha"></div>'),
        (200, "<title>Just a moment</title>"),
        (200, "Please verify you are human"),
    ],
)
def test_stop_preserves_evidence_and_pending_checkpoint(tmp_path, status, body):
    _, details, urls = setup_routes()
    details[0].mock(
        return_value=httpx.Response(status, text=body, headers={"Content-Type": "text/html"})
    )
    c = replace(config(tmp_path), max_details=20, target_records=3)
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
        {"max_pages": 9},
        {"max_details": 331},
        {"max_details": 301},  # extra attempt allowance requires a valid target
        {"max_pages": None},
        {"max_details": None},
        {"source": "vietnamworks"},
        {"fetcher": "auto"},
        {"delay_min_seconds": 2},
        {"max_retries": 1},
        {"require_complete_content": False},
    ],
)
def test_bounded_config_guards(tmp_path, change):
    with pytest.raises(ConfigError):
        replace(config(tmp_path), **change).validate()


@pytest.mark.parametrize("target", [0, 301])
def test_invalid_target(tmp_path, target):
    with pytest.raises(ConfigError, match="target-records"):
        replace(config(tmp_path), target_records=target).validate()


def test_extra_attempt_allowance_is_explicit_and_keeps_other_source_caps(tmp_path):
    replace(config(tmp_path), max_pages=8, max_details=330, target_records=300).validate()
    with pytest.raises(ConfigError, match="delay"):
        replace(
            config(tmp_path), max_pages=8, max_details=330, target_records=300, delay_min_seconds=3
        ).validate()
    with pytest.raises(ConfigError):
        replace(config(tmp_path), mode="sample", target_records=3).validate()


@pytest.mark.parametrize("source", ["timviec365", "vieclam24h", "vietnamworks"])
def test_other_bounded_sources_keep_300_attempt_cap(tmp_path, source):
    c = replace(
        config(tmp_path),
        source=source,
        max_details=301,
        fetcher="http" if source == "timviec365" else "playwright",
        headed=source != "timviec365",
    )
    with pytest.raises(ConfigError, match="between 1 and 300"):
        c.validate()


@respx.mock
def test_target_counts_total_unique_raw_and_resume_does_not_fetch_completed(tmp_path):
    listing, details, _ = setup_routes()
    c = replace(config(tmp_path), max_details=330, target_records=2)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        first = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert first.records_written == first.detail_requested == 2
    assert first.termination_reason == "target_records"
    assert details[2].call_count == 0
    c = replace(c, resume=True, resume_batch_id=first.batch_id, target_records=3)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        second = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert second.records_written == second.detail_requested == 3
    assert second.termination_reason == "target_records"
    assert listing.call_count == 1 and all(d.call_count == 1 for d in details)
    assert [s.target_records for s in second.run_settings] == [2, 3]
    assert second.run_settings[-1].max_details == 330


@respx.mock
def test_already_met_target_makes_no_network_requests_and_repairs_counter(tmp_path):
    _, _, _ = setup_routes()
    c = replace(config(tmp_path), max_details=330, target_records=1)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        first = CrawlEngine(c, CareerLinkCrawler(), f).run()
    root = next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))
    saved = json.loads((root / "manifest.json").read_text())
    saved["records_written"] = saved["detail_succeeded"] = 0
    (root / "manifest.json").write_text(json.dumps(saved))
    respx.reset()
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        result = CrawlEngine(
            replace(c, resume=True, resume_batch_id=first.batch_id), CareerLinkCrawler(), f
        ).run()
    assert result.records_written == result.detail_succeeded == 1
    assert result.termination_reason == "target_records"
    assert respx.calls.call_count == 0


@respx.mock
def test_target_never_overrides_attempt_budget_or_claims_exhausted_listing_complete(tmp_path):
    _, _, _ = setup_routes()
    c = replace(config(tmp_path), max_details=1, target_records=3)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        first = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert first.records_written == 1 and first.termination_reason == "max_details"
    c = replace(c, max_details=5, target_records=4, resume=True, resume_batch_id=first.batch_id)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        result = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert result.records_written == 3
    assert result.termination_reason == "target_unmet_no_pending_details"


@respx.mock
def test_resume_discovers_next_main_pages_then_appends_only_new_details(tmp_path):
    first_listing, details, urls = setup_routes()

    def page(url, following=None):
        html = (
            '<ul class="list-group"><li class="job-item">'
            f'<a class="job-link" href="{url}">job</a></li></ul>'
        )
        if following:
            html += f'<div class="pagination"><a rel="next" href="{following}">next</a></div>'
        return html

    page2 = "https://www.careerlink.vn/vieclam/list?page=2"
    page3 = "https://www.careerlink.vn/vieclam/list?page=3"
    first_listing.mock(return_value=httpx.Response(200, text=page(urls[0], page2)))
    listing2 = respx.get(page2).mock(return_value=httpx.Response(200, text=page(urls[1], page3)))
    listing3 = respx.get(page3).mock(return_value=httpx.Response(200, text=page(urls[2])))
    c = replace(config(tmp_path), target_records=1)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        first = CrawlEngine(c, CareerLinkCrawler(), f).run()
    root = next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))
    before = (root / "jobs.jsonl").read_bytes()
    c = replace(
        c,
        max_pages=3,
        max_details=330,
        target_records=3,
        resume=True,
        resume_batch_id=first.batch_id,
    )
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        result = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert result.records_written == result.unique_ids_discovered == 3
    assert result.listing_pages_requested == 3
    assert result.termination_reason == "target_records"
    assert (root / "jobs.jsonl").read_bytes().startswith(before)
    assert first_listing.call_count == listing2.call_count == listing3.call_count == 1
    assert all(route.call_count == 1 for route in details)


@respx.mock
def test_resume_keeps_failed_ids_without_retry_when_target_is_increased(tmp_path):
    _, details, _ = setup_routes()
    details[0].mock(return_value=httpx.Response(404, text="Not found"))
    c = replace(config(tmp_path), max_details=3, target_records=2)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        first = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert first.status == "stopped" and first.records_written == 0
    c = replace(c, max_details=330, resume=True, resume_batch_id=first.batch_id)
    with CareerLinkHttpFetcher(c, sleep=lambda _: None) as f:
        result = CrawlEngine(c, CareerLinkCrawler(), f).run()
    assert result.records_written == 2 and result.detail_requested == 3
    assert result.detail_failed == 1 and result.status == "completed_with_errors"
    assert details[0].call_count == 1
    root = next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        assert (
            db.execute("SELECT count(*) FROM detail_queue WHERE status='failed'").fetchone()[0] == 1
        )
