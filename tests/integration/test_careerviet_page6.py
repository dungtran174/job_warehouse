from collections import Counter
from pathlib import Path

import httpx
import pytest

from job_crawler.config import CrawlConfig
from job_crawler.crawlers.careerviet import CareerVietCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.storage.jsonl import StorageError
from job_crawler.storage.page6_preflight import validate_page6_transition

START_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html"
USER_AGENT = "job-warehouse-crawler/0.1 (+public-research; contact=data@example.org)"


def listing_url(page: int) -> str:
    if page == 1:
        return START_URL
    return f"https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-{page}-vi.html"


def listing_html(page: int) -> str:
    ids = (
        [*range(251, 292), 250, *range(292, 300)]
        if page == 6
        else range((page - 1) * 50 + 1, page * 50 + 1)
    )
    anchors = "".join(
        f'<a class="job_link" href="/vi/tim-viec-lam/test.35C{job_id:05X}.html">Job</a>'
        for job_id in ids
    )
    return (
        '<html><head><link rel="canonical" href="'
        + listing_url(page)
        + '"></head><body><h1>300 việc làm</h1>'
        + anchors
        + '<div class="pagination"><li class="active"><a role="button">'
        + str(page)
        + '</a></li><li class="next-page"><a role="button">Next</a></li></div></body></html>'
    )


def test_page6_resume_only_fetches_new_listing_and_details(
    tmp_path: Path, read_source_fixture
) -> None:
    calls: Counter[str] = Counter()
    detail_html = read_source_fixture("careerviet", "detail_full.html")

    def respond(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls[url] += 1
        if url == "https://careerviet.vn/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        for page in range(1, 7):
            if url == listing_url(page):
                return httpx.Response(200, text=listing_html(page))
        if "/vi/tim-viec-lam/test.35C" in url:
            return httpx.Response(200, text=detail_html)
        raise AssertionError(f"Unexpected request: {url}")

    common = dict(
        source="careerviet",
        start_url=START_URL,
        output_dir=tmp_path,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        fetcher="http",
        save_html=True,
        require_complete_content=True,
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        pilot = CrawlConfig(
            **common,
            mode="pilot",
            max_pages=5,
            max_details=250,
            authorization_reference="PILOT-TEST",
        )
        with HttpFetcher(pilot, client=client, sleep=lambda _seconds: None) as fetcher:
            first = CrawlEngine(pilot, CareerVietCrawler(), fetcher).run()
        assert first.records_written == 250

        root = next(tmp_path.glob("careerviet/snapshot_date=*/batch_id=*"))
        validate_page6_transition(root, first)
        raw_path = root / "html" / "listing-001.html.gz"
        original = raw_path.read_bytes()
        raw_path.write_bytes(b"damaged gzip")
        with pytest.raises(StorageError):
            validate_page6_transition(root, first)
        raw_path.write_bytes(original)

        page6 = CrawlConfig(
            **common,
            mode="page6-check",
            max_pages=6,
            max_details=300,
            resume=True,
            resume_batch_id=first.batch_id,
            authorization_reference="PAGE6-TEST",
        )
        with HttpFetcher(page6, client=client, sleep=lambda _seconds: None) as fetcher:
            result = CrawlEngine(page6, CareerVietCrawler(), fetcher).run()

    assert result.status == "completed"
    assert result.mode == "page6-check"
    assert result.authorization_references == ["PILOT-TEST", "PAGE6-TEST"]
    assert result.listing_pages_requested == 6
    assert result.listing_pages_unique == 6
    assert result.new_job_ids_per_page == [50] * 5 + [49]
    assert result.unique_ids_discovered == 299
    assert result.detail_requested == result.detail_succeeded == result.records_written == 299
    assert result.detail_failed == 0
    assert result.cross_page_overlaps == result.duplicates_skipped == 1
    assert all(calls[listing_url(page)] == 1 for page in range(1, 7))
    assert calls[listing_url(7)] == 0
    assert all(
        calls[f"https://careerviet.vn/vi/tim-viec-lam/test.35C{job_id:05X}.html"] == 1
        for job_id in range(1, 300)
    )
    assert calls["https://careerviet.vn/vi/tim-viec-lam/test.35C0012C.html"] == 0


def test_cached_page6_recovery_is_idempotent_and_resume_fetches_only_new_details(
    tmp_path: Path, read_source_fixture
) -> None:
    import sqlite3

    from job_crawler.storage.incremental import IncrementalState
    from job_crawler.storage.jsonl import BatchStorage
    from job_crawler.storage.manifest import ManifestWriter
    from job_crawler.storage.page6_recovery import recover_page6_from_saved_html
    from job_crawler.utils.time import utc_now

    calls: Counter[str] = Counter()
    detail_html = read_source_fixture("careerviet", "detail_full.html")

    def respond(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls[url] += 1
        if url == "https://careerviet.vn/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if url in {listing_url(page) for page in range(1, 6)}:
            page_number = next(page for page in range(1, 6) if url == listing_url(page))
            return httpx.Response(200, text=listing_html(page_number))
        if "/vi/tim-viec-lam/test.35C" in url:
            return httpx.Response(200, text=detail_html)
        raise AssertionError(f"Unexpected network request: {url}")

    common = dict(
        source="careerviet",
        start_url=START_URL,
        output_dir=tmp_path,
        delay_min_seconds=0,
        delay_max_seconds=0,
        max_retries=0,
        user_agent=USER_AGENT,
        fetcher="http",
        save_html=True,
        require_complete_content=True,
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        pilot = CrawlConfig(
            **common,
            mode="pilot",
            max_pages=5,
            max_details=250,
            authorization_reference="PILOT-TEST",
        )
        with HttpFetcher(pilot, client=client, sleep=lambda _seconds: None) as fetcher:
            manifest = CrawlEngine(pilot, CareerVietCrawler(), fetcher).run()
        root = next(tmp_path.glob("careerviet/snapshot_date=*/batch_id=*"))
        jobs_before = (root / "jobs.jsonl").read_bytes()
        detail_html_before = (root / "html/35C00001.html.gz").read_bytes()
        cached_html = listing_html(6)
        storage = BatchStorage.resume(root)
        storage.save_page_html("listing-006", cached_html)
        page = CareerVietCrawler().parse_listing(cached_html, listing_url(6))
        assert storage.checkpoint.next_listing() == listing_url(6)
        assert storage.checkpoint.add_fingerprint(page.fingerprint)
        incremental = IncrementalState(tmp_path / "careerviet/incremental_state.sqlite3")
        for job in page.jobs[:41]:
            assert storage.checkpoint.enqueue_detail(job)
            incremental.observe_discovery(
                job.source_name,
                job.source_job_id,
                seen_at=utc_now(),
                batch_id=manifest.batch_id,
            )
        incremental.close()
        storage.checkpoint.finish_listing(listing_url(6))
        storage.close()
        manifest.mode = "page6-check"
        manifest.status = "stopped"
        manifest.termination_reason = "duplicate_job_id"
        manifest.pagination_termination_reason = "duplicate_job_id"
        manifest.listing_pages_requested = 6
        manifest.listing_pages_succeeded = 6
        manifest.listing_pages_unique = 6
        manifest.urls_discovered = 300
        manifest.listing_page_fingerprints.append(page.fingerprint)
        manifest.new_job_ids_per_page.append(41)
        manifest.unique_ids_discovered = 291
        manifest.duplicates_skipped = 1
        manifest.incremental_new_ids = 291
        manifest.incremental_existing_ids = 1
        ManifestWriter(root / "manifest.json").write(manifest)

        assert recover_page6_from_saved_html(root) == 8
        assert recover_page6_from_saved_html(root) == 0
        assert (root / "jobs.jsonl").read_bytes() == jobs_before
        assert (root / "html/35C00001.html.gz").read_bytes() == detail_html_before
        with sqlite3.connect(root / "checkpoint.sqlite3") as db:
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert (
                db.execute("SELECT count(*) FROM detail_queue WHERE status='pending'").fetchone()[0]
                == 49
            )

        page6 = CrawlConfig(
            **common,
            mode="page6-check",
            max_pages=6,
            max_details=300,
            resume=True,
            resume_batch_id=manifest.batch_id,
            authorization_reference="PAGE6-TEST",
        )
        with HttpFetcher(page6, client=client, sleep=lambda _seconds: None) as fetcher:
            result = CrawlEngine(page6, CareerVietCrawler(), fetcher).run()

    assert result.status == "completed"
    assert result.records_written == result.detail_succeeded == 299
    assert result.detail_requested == 299
    assert result.cross_page_overlaps == result.duplicates_skipped == 1
    assert calls[listing_url(6)] == calls[listing_url(7)] == 0
    assert all(
        calls[f"https://careerviet.vn/vi/tim-viec-lam/test.35C{job_id:05X}.html"] == 1
        for job_id in range(1, 300)
    )
