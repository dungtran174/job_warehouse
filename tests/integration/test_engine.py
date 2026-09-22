import json

import httpx
import respx

from job_crawler.config import CrawlConfig
from job_crawler.crawlers.topcv import TopCVCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.http import HttpFetcher

START_URL = "https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&sba=1"
USER_AGENT = "job-warehouse-crawler/0.1 (+public-research; contact=data@example.org)"


@respx.mock
def test_engine_writes_a_bounded_sample_without_duplicate_ids(tmp_path, read_fixture) -> None:
    respx.get("https://www.topcv.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get(START_URL).mock(
        return_value=httpx.Response(
            200,
            text=read_fixture("listing_page_1.html"),
            headers={"Content-Type": "text/html"},
        )
    )
    respx.get("https://www.topcv.vn/viec-lam/data-engineer/1001.html").mock(
        return_value=httpx.Response(
            200,
            text=read_fixture("detail_full.html"),
            headers={"Content-Type": "text/html"},
        )
    )
    respx.get("https://www.topcv.vn/viec-lam/backend-engineer/1002.html").mock(
        return_value=httpx.Response(
            200,
            text=read_fixture("detail_missing_optional.html"),
            headers={"Content-Type": "text/html"},
        )
    )
    config = CrawlConfig(
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=2,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, TopCVCrawler(), fetcher).run()

    assert manifest.status == "completed"
    assert manifest.listing_pages_requested == 1
    assert manifest.unique_ids_discovered == 2
    assert manifest.detail_requested == 2
    assert manifest.records_written == 2
    batch = next(tmp_path.glob("topcv/snapshot_date=*/batch_id=*"))
    jobs = [json.loads(line) for line in (batch / "jobs.jsonl").read_text().splitlines()]
    assert {job["source_job_id"] for job in jobs} == {"1001", "1002"}
    assert (batch / "manifest.json").is_file()
    assert (batch / "errors.jsonl").read_text() == ""
    assert (batch / "checkpoint.sqlite3").is_file()


@respx.mock
def test_robots_denial_stops_before_listing_request(tmp_path) -> None:
    robots = respx.get("https://www.topcv.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /tim-viec-lam-moi-nhat\n")
    )
    listing = respx.get(START_URL).mock(return_value=httpx.Response(200, text="unused"))
    config = CrawlConfig(
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, TopCVCrawler(), fetcher).run()
    assert manifest.status == "stopped"
    assert manifest.termination_reason == "robots_denied"
    assert robots.called
    assert not listing.called


@respx.mock
def test_listing_block_stops_before_queued_details(tmp_path, read_fixture) -> None:
    respx.get("https://www.topcv.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get(START_URL).mock(
        return_value=httpx.Response(
            200,
            text=read_fixture("listing_page_1.html"),
            headers={"Content-Type": "text/html"},
        )
    )
    second_listing = respx.get("https://www.topcv.vn/tim-viec-lam-moi-nhat?page=2").mock(
        return_value=httpx.Response(403, text="denied")
    )
    detail = respx.get("https://www.topcv.vn/viec-lam/data-engineer/1001.html").mock(
        return_value=httpx.Response(200, text=read_fixture("detail_full.html"))
    )
    config = CrawlConfig(
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=2,
        max_details=20,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, TopCVCrawler(), fetcher).run()
    assert manifest.status == "stopped"
    assert manifest.termination_reason == "access_blocked"
    assert second_listing.called
    assert not detail.called
