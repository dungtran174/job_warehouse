import gzip
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx

from job_crawler.config import ConfigError, CrawlConfig
from job_crawler.crawlers.vietnamworks import VietnamWorksCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.vietnamworks import VietnamWorksFetcher

ROOT = Path(__file__).parents[1] / "fixtures/vietnamworks"
EXPECTED = json.loads((ROOT / "detail_expected.json").read_text())
START = "https://www.vietnamworks.com/tim-viec-lam/tim-tat-ca-viec-lam"
UA = "job-warehouse-test/0.1 (contact=data@example.org)"


def config(tmp_path, **kw):
    return CrawlConfig(
        source="vietnamworks",
        start_url=START,
        output_dir=tmp_path,
        project_owner_public_test=True,
        user_agent=UA,
        max_pages=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        save_html=True,
        require_complete_content=True,
        fetcher="http",
        **kw,
    )


def listing():
    return (
        '<div class="block-job-list">'
        + "".join(
            '<div class="search_list"><a href="' + item["url"] + '?source=searchResults">title</a>'
            '<a href="' + item["url"] + '">duplicate</a></div>'
            for item in EXPECTED.values()
        )
        + '</div><ul class="pagination"><li class="active"><button>1</button></li>'
        "<li><button disabled>></button></li></ul>"
    )


@respx.mock
def test_batch_resume_no_refetch_no_duplicate_and_raw_html(tmp_path):
    respx.get("https://www.vietnamworks.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    route = respx.get(START).mock(return_value=httpx.Response(200, text=listing()))
    detail_routes = []
    for job_id, item in EXPECTED.items():
        detail_routes.append(
            respx.get(item["url"]).mock(
                return_value=httpx.Response(200, text=(ROOT / f"detail_{job_id}.html").read_text())
            )
        )
    c = config(tmp_path, max_details=1)
    with HttpFetcher(c) as f:
        first = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    c = replace(c, max_details=3, resume=True, resume_batch_id=first.batch_id)
    with HttpFetcher(c) as f:
        second = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    with HttpFetcher(c) as f:
        third = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    assert first.records_written == 1
    assert second.records_written == third.records_written == 3
    assert second.detail_requested == 3
    assert second.unique_ids_discovered == 3
    assert route.call_count == 1
    assert all(r.call_count == 1 for r in detail_routes)
    root = next(tmp_path.glob("vietnamworks/snapshot_date=*/batch_id=*"))
    records = [json.loads(x) for x in (root / "jobs.jsonl").read_text().splitlines()]
    assert len({x["source_job_id"] for x in records}) == 3
    for r in records:
        assert r["job_description"] and r["candidate_requirements"] and r["company_name"]
        with gzip.open(root / r["raw_html_path"], "rt") as handle:
            assert handle.read() == (ROOT / f"detail_{r['source_job_id']}.html").read_text()
    assert second.access_basis == "project_owner_public_test"
    assert second.authorization_reference is None
    assert (root / "errors.jsonl").read_text() == ""


@respx.mock
def test_blocked_detail_stops_and_keeps_checkpoint(tmp_path):
    respx.get("https://www.vietnamworks.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get(START).mock(return_value=httpx.Response(200, text=listing()))
    first_id, first = next(iter(EXPECTED.items()))
    respx.get(first["url"]).mock(return_value=httpx.Response(403, text="Forbidden"))
    with HttpFetcher(config(tmp_path, max_details=20)) as f:
        result = CrawlEngine(config(tmp_path, max_details=20), VietnamWorksCrawler(), f).run()
    assert result.status == "stopped"
    assert result.detail_requested == 1 and result.records_written == 0
    root = next(tmp_path.glob("vietnamworks/snapshot_date=*/batch_id=*"))
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        assert (
            db.execute(
                "SELECT status FROM detail_queue WHERE source_job_id=?", (first_id,)
            ).fetchone()[0]
            == "pending"
        )


@respx.mock
def test_auto_never_renders_http_denial(tmp_path, monkeypatch):
    f = VietnamWorksFetcher(config(tmp_path, max_details=3))
    respx.get(START).mock(return_value=httpx.Response(403, text="Forbidden"))
    monkeypatch.setattr(f.browser, "get", lambda url: pytest.fail("must not bypass 403"))
    from job_crawler.fetchers.base import FetchError

    with pytest.raises(FetchError):
        f.get(START)
    f.close()


def test_owner_vietnamworks_cap_is_twenty(tmp_path):
    config(tmp_path, max_details=20).validate()
    with pytest.raises(ConfigError):
        config(tmp_path, max_details=21).validate()
    with pytest.raises(ConfigError):
        replace(config(tmp_path, max_details=20), mode="pilot").validate()


@respx.mock
def test_terminal_listing_error_does_not_attempt_queued_details(tmp_path):
    from job_crawler.fetchers.base import FetchError

    respx.get("https://www.vietnamworks.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get(START).mock(return_value=httpx.Response(200, text=listing()))
    first_id, item = next(iter(EXPECTED.items()))
    respx.get(item["url"]).mock(
        return_value=httpx.Response(200, text=(ROOT / f"detail_{first_id}.html").read_text())
    )
    c = config(tmp_path, max_details=1)
    with HttpFetcher(c) as f:
        first = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    root = next(tmp_path.glob("vietnamworks/snapshot_date=*/batch_id=*"))
    page2 = "https://www.vietnamworks.com/viec-lam?page=2"
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        db.execute("INSERT INTO listing_queue(url) VALUES (?)", (page2,))

    class TerminalFetcher(HttpFetcher):
        def get(self, url):
            if url == page2:
                raise FetchError("Terminal page error", url=url, attempt=1, terminal=True)
            return super().get(url)

    c = replace(c, max_pages=2, max_details=3, resume=True, resume_batch_id=first.batch_id)
    with TerminalFetcher(c) as f:
        result = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    assert result.records_written == result.detail_requested == 1
    assert result.status == "stopped"
    assert result.termination_reason == "listing_fetch_failed"


@respx.mock
def test_discovery_landing_http_200_does_not_fetch_details_or_render(tmp_path, monkeypatch):
    url = "https://www.vietnamworks.com/tim-viec-lam"
    respx.get("https://www.vietnamworks.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    route = respx.get(url).mock(
        return_value=httpx.Response(
            200, text=(ROOT / "discovery_landing_20260929.html").read_text()
        )
    )
    c = replace(config(tmp_path, max_details=3), start_url=url, fetcher="auto")
    f = VietnamWorksFetcher(c)
    monkeypatch.setattr(
        f.browser, "get", lambda _url: pytest.fail("Landing is not a JS search-results shell")
    )
    with f:
        result = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    assert route.call_count == 1
    assert result.listing_pages_requested == 1
    assert result.listing_pages_succeeded == 0
    assert result.unique_ids_discovered == 0
    assert result.detail_requested == result.records_written == 0
    assert result.pagination_termination_reason == "no_jobs_found"
    assert not result.challenge_detected
    assert not result.http_fallback_to_playwright
    root = next(tmp_path.glob("vietnamworks/snapshot_date=*/batch_id=*"))
    assert (root / "jobs.jsonl").read_text() == ""


@respx.mock
def test_browser_listing_block_preserves_pending_and_offline_resume(tmp_path, monkeypatch):
    from job_crawler.fetchers.base import FetchError, FetchResponse

    respx.get("https://www.vietnamworks.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    route = respx.get(START).mock(return_value=httpx.Response(200, text="<html>JS shell</html>"))
    c = replace(config(tmp_path, max_details=3), fetcher="auto")
    f = VietnamWorksFetcher(c)

    def denied(url):
        raise FetchError("Browser stopped", url=url, attempt=1, status_code=403, blocked=True)

    monkeypatch.setattr(f.browser, "get", denied)
    with f:
        blocked = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    assert blocked.status == "stopped"
    assert blocked.fetcher_used == "playwright"
    assert blocked.http_fallback_to_playwright
    assert blocked.challenge_detected
    assert blocked.detail_requested == 0
    root = next(tmp_path.glob("vietnamworks/snapshot_date=*/batch_id=*"))
    with sqlite3.connect(root / "checkpoint.sqlite3") as db:
        assert db.execute("SELECT status FROM listing_queue").fetchone()[0] == "pending"

    # This is offline only: simulate a later source-allowed resume, never auto-retry a denial.
    c = replace(c, max_pages=2, resume=True, resume_batch_id=blocked.batch_id)
    for job_id, item in EXPECTED.items():
        respx.get(item["url"]).mock(
            return_value=httpx.Response(200, text=(ROOT / f"detail_{job_id}.html").read_text())
        )
    f = VietnamWorksFetcher(c)
    monkeypatch.setattr(
        f.browser,
        "get",
        lambda url: FetchResponse(
            url=url,
            text=listing(),
            status_code=200,
            headers={},
            attempt=1,
            duration_seconds=0.0,
            fetcher="playwright",
        ),
    )
    with f:
        resumed = CrawlEngine(c, VietnamWorksCrawler(), f).run()
    assert resumed.batch_id == blocked.batch_id
    assert resumed.records_written == 3
    assert resumed.listing_pages_requested == 2
    assert resumed.listing_pages_succeeded == 1
    assert route.call_count == 2
