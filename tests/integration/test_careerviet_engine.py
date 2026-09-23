import json
import sqlite3

import httpx
import respx

from job_crawler.config import CrawlConfig
from job_crawler.crawlers.careerviet import CareerVietCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.http import HttpFetcher

START_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html"
PAGE_2_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-2-vi.html"
PAGE_3_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-3-vi.html"
USER_AGENT = "job-warehouse-crawler/0.1 (+public-research; contact=data@example.org)"


@respx.mock
def test_careerviet_engine_writes_manifest_checkpoint_and_deduplicated_records(
    tmp_path, read_source_fixture
) -> None:
    respx.get("https://careerviet.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get(START_URL).mock(
        return_value=httpx.Response(
            200,
            text=read_source_fixture("careerviet", "listing_page_1.html"),
            headers={"Content-Type": "text/html"},
        )
    )
    respx.get("https://careerviet.vn/vi/tim-viec-lam/ky-su-du-lieu.35C00001.html").mock(
        return_value=httpx.Response(
            200,
            text=read_source_fixture("careerviet", "detail_full.html"),
        )
    )
    respx.get("https://careerviet.vn/vi/tim-viec-lam/lap-trinh-vien.35C00002.html").mock(
        return_value=httpx.Response(
            200,
            text=read_source_fixture("careerviet", "detail_missing_optional.html"),
        )
    )
    config = CrawlConfig(
        source="careerviet",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=2,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, CareerVietCrawler(), fetcher).run()

    assert manifest.status == "completed"
    assert manifest.listing_pages_succeeded == 1
    assert manifest.urls_discovered == 2
    assert manifest.unique_ids_discovered == 2
    assert manifest.detail_succeeded == 2
    assert manifest.records_written == 2
    batch = next(tmp_path.glob("careerviet/snapshot_date=*/batch_id=*"))
    jobs = [json.loads(line) for line in (batch / "jobs.jsonl").read_text().splitlines()]
    assert {job["source_job_id"] for job in jobs} == {"35C00001", "35C00002"}
    assert json.loads((batch / "manifest.json").read_text())["source"] == "careerviet"
    assert (batch / "checkpoint.sqlite3").is_file()
    assert (batch / "errors.jsonl").read_text() == ""


@respx.mock
def test_exact_batch_resume_continues_pending_without_refetch_or_duplicates(
    tmp_path, read_source_fixture
) -> None:
    listing_html = read_source_fixture("careerviet", "listing_page_1.html").replace(
        '<div class="pagination">',
        """
        <div class="job-item">
          <a class="job_link"
             href="/vi/tim-viec-lam/kiem-thu-vien.35C00003.html">Kiểm thử viên</a>
        </div>
        <div class="pagination">
        """,
    )
    robots = respx.get("https://careerviet.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    listing = respx.get(START_URL).mock(return_value=httpx.Response(200, text=listing_html))
    first_detail = respx.get(
        "https://careerviet.vn/vi/tim-viec-lam/ky-su-du-lieu.35C00001.html"
    ).mock(
        return_value=httpx.Response(200, text=read_source_fixture("careerviet", "detail_full.html"))
    )
    second_detail = respx.get(
        "https://careerviet.vn/vi/tim-viec-lam/lap-trinh-vien.35C00002.html"
    ).mock(
        return_value=httpx.Response(
            200, text=read_source_fixture("careerviet", "detail_missing_optional.html")
        )
    )
    third_detail = respx.get(
        "https://careerviet.vn/vi/tim-viec-lam/kiem-thu-vien.35C00003.html"
    ).mock(return_value=httpx.Response(500, text="must remain pending"))

    phase_a = CrawlConfig(
        source="careerviet",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
    )
    with HttpFetcher(phase_a, sleep=lambda _seconds: None) as fetcher:
        first_manifest = CrawlEngine(phase_a, CareerVietCrawler(), fetcher).run()

    phase_b = CrawlConfig(
        source="careerviet",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=2,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
        resume=True,
        resume_batch_id=first_manifest.batch_id,
    )
    with HttpFetcher(phase_b, sleep=lambda _seconds: None) as fetcher:
        second_manifest = CrawlEngine(phase_b, CareerVietCrawler(), fetcher).run()
    with HttpFetcher(phase_b, sleep=lambda _seconds: None) as fetcher:
        third_manifest = CrawlEngine(phase_b, CareerVietCrawler(), fetcher).run()

    assert first_manifest.records_written == 1
    assert second_manifest.batch_id == first_manifest.batch_id
    assert second_manifest.detail_requested == 2
    assert second_manifest.detail_succeeded == 2
    assert second_manifest.records_written == 2
    for field_name in (
        "batch_id",
        "listing_pages_requested",
        "urls_discovered",
        "unique_ids_discovered",
        "detail_requested",
        "detail_succeeded",
        "detail_failed",
        "records_written",
        "duplicates_skipped",
        "termination_reason",
    ):
        assert getattr(third_manifest, field_name) == getattr(second_manifest, field_name)
    assert listing.call_count == 1
    assert first_detail.call_count == 1
    assert second_detail.call_count == 1
    assert third_detail.call_count == 0
    assert robots.call_count == 3
    assert len(list(tmp_path.glob("careerviet/snapshot_date=*/batch_id=*"))) == 1
    batch = next(tmp_path.glob("careerviet/snapshot_date=*/batch_id=*"))
    jobs = [json.loads(line) for line in (batch / "jobs.jsonl").read_text().splitlines()]
    keys = [(job["source_name"], job["source_job_id"]) for job in jobs]
    assert keys == [("careerviet", "35C00001"), ("careerviet", "35C00002")]


@respx.mock
def test_strict_content_gate_stops_before_writing_incomplete_record(
    tmp_path, read_source_fixture
) -> None:
    respx.get("https://careerviet.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get(START_URL).mock(
        return_value=httpx.Response(
            200, text=read_source_fixture("careerviet", "listing_page_1.html")
        )
    )
    incomplete = read_source_fixture("careerviet", "detail_missing_optional.html").replace(
        '"name": "Công ty Mẫu Hai"', '"name": ""'
    )
    respx.get("https://careerviet.vn/vi/tim-viec-lam/ky-su-du-lieu.35C00001.html").mock(
        return_value=httpx.Response(200, text=incomplete)
    )
    config = CrawlConfig(
        source="careerviet",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
        require_complete_content=True,
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, CareerVietCrawler(), fetcher).run()

    assert manifest.status == "stopped"
    assert manifest.termination_reason == "missing_required_fields"
    assert manifest.records_written == 0
    assert manifest.records_missing_required == 1
    batch = next(tmp_path.glob("careerviet/snapshot_date=*/batch_id=*"))
    assert (batch / "jobs.jsonl").read_text() == ""
    error = json.loads((batch / "errors.jsonl").read_text())
    assert error["error_type"] == "MissingRequiredFields"
    assert "company_name" in error["message"]


@respx.mock
def test_pagination_resume_only_requests_pending_unique_pages(
    tmp_path, read_source_fixture
) -> None:
    robots = respx.get("https://careerviet.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    first_page = respx.get(START_URL).mock(
        return_value=httpx.Response(
            200, text=read_source_fixture("careerviet", "listing_page_1.html")
        )
    )
    second_page = respx.get(PAGE_2_URL).mock(
        return_value=httpx.Response(
            200, text=read_source_fixture("careerviet", "listing_page_2.html")
        )
    )
    third_page = respx.get(PAGE_3_URL).mock(
        return_value=httpx.Response(
            200, text=read_source_fixture("careerviet", "listing_last.html")
        )
    )
    detail_urls = {
        "35C00001": "ky-su-du-lieu",
        "35C00002": "lap-trinh-vien",
        "35C00003": "kiem-thu-vien",
        "35C00004": "quan-tri-he-thong",
        "35C00005": "ky-su-ha-tang",
    }
    detail_routes = []
    for job_id, slug in detail_urls.items():
        route = respx.get(f"https://careerviet.vn/vi/tim-viec-lam/{slug}.{job_id}.html").mock(
            return_value=httpx.Response(
                200, text=read_source_fixture("careerviet", "detail_full.html")
            )
        )
        detail_routes.append(route)

    phase_a = CrawlConfig(
        source="careerviet",
        mode="medium",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=1,
        max_details=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
    )
    with HttpFetcher(phase_a, sleep=lambda _seconds: None) as fetcher:
        first_manifest = CrawlEngine(phase_a, CareerVietCrawler(), fetcher).run()

    phase_b = CrawlConfig(
        source="careerviet",
        mode="pilot",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=3,
        max_details=5,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-PILOT",
        fetcher="http",
        resume=True,
        resume_batch_id=first_manifest.batch_id,
    )
    with HttpFetcher(phase_b, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(phase_b, CareerVietCrawler(), fetcher).run()

    assert manifest.batch_id == first_manifest.batch_id
    assert manifest.mode == "pilot"
    assert manifest.authorization_reference == "APPROVAL-TEST"
    assert manifest.authorization_references == ["APPROVAL-TEST", "APPROVAL-PILOT"]
    assert manifest.listing_pages_requested == 3
    assert manifest.listing_pages_unique == 3
    assert len(set(manifest.listing_page_fingerprints)) == 3
    assert manifest.new_job_ids_per_page == [2, 2, 1]
    assert manifest.pagination_termination_reason == "next_page_disabled_or_absent"
    assert manifest.unique_ids_discovered == 5
    assert manifest.records_written == 5
    assert first_page.call_count == 1
    assert second_page.call_count == 1
    assert third_page.call_count == 1
    assert robots.call_count == 2
    assert all(route.call_count == 1 for route in detail_routes)
    with sqlite3.connect(tmp_path / "careerviet" / "incremental_state.sqlite3") as database:
        assert database.execute("SELECT COUNT(*) FROM job_state").fetchone()[0] == 5


@respx.mock
def test_repeated_page_fingerprint_stops_pagination(tmp_path, read_source_fixture) -> None:
    respx.get("https://careerviet.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    first_html = read_source_fixture("careerviet", "listing_page_1.html")
    repeated_html = first_html.replace(START_URL, PAGE_2_URL).replace(
        '<li class="active"><a role="button">1</a></li>',
        '<li><a role="button">1</a></li><li class="active"><a role="button">2</a></li>',
    )
    respx.get(START_URL).mock(return_value=httpx.Response(200, text=first_html))
    respx.get(PAGE_2_URL).mock(return_value=httpx.Response(200, text=repeated_html))
    respx.get("https://careerviet.vn/vi/tim-viec-lam/ky-su-du-lieu.35C00001.html").mock(
        return_value=httpx.Response(200, text=read_source_fixture("careerviet", "detail_full.html"))
    )
    config = CrawlConfig(
        source="careerviet",
        mode="medium",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=2,
        max_details=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, CareerVietCrawler(), fetcher).run()
    assert manifest.listing_pages_requested == 2
    assert manifest.listing_pages_unique == 1
    assert manifest.duplicate_listing_pages == 1
    assert manifest.new_job_ids_per_page == [2, 0]
    assert manifest.pagination_termination_reason == "repeated_page_fingerprint"


@respx.mock
def test_redirect_to_first_page_stops_with_structured_reason(tmp_path, read_source_fixture) -> None:
    respx.get("https://careerviet.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    first = respx.get(START_URL).mock(
        side_effect=[
            httpx.Response(200, text=read_source_fixture("careerviet", "listing_page_1.html")),
            httpx.Response(200, text=read_source_fixture("careerviet", "listing_page_1.html")),
        ]
    )
    respx.get(PAGE_2_URL).mock(return_value=httpx.Response(302, headers={"Location": START_URL}))
    config = CrawlConfig(
        source="careerviet",
        mode="medium",
        start_url=START_URL,
        output_dir=tmp_path,
        max_pages=2,
        max_details=1,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        authorization_reference="APPROVAL-TEST",
        fetcher="http",
    )
    with HttpFetcher(config, sleep=lambda _seconds: None) as fetcher:
        manifest = CrawlEngine(config, CareerVietCrawler(), fetcher).run()
    assert manifest.status == "stopped"
    assert manifest.termination_reason == "listing_redirected_to_start"
    assert manifest.pagination_termination_reason == "listing_redirected_to_start"
    assert first.call_count == 2
