import json
from dataclasses import replace
from pathlib import Path

import httpx
import respx
from selectolax.parser import HTMLParser

from job_crawler.config import CrawlConfig
from job_crawler.crawlers.careerlink import CareerLinkCrawler
from job_crawler.engine import CrawlEngine
from job_crawler.fetchers.careerlink import CareerLinkHttpFetcher


@respx.mock
def test_explicit_later_resume_counts_attempts_keeps_prefix_and_no_duplicate(tmp_path):
    # Mock-only: a later healthy response, not a live retry after hCaptcha.
    start = "https://www.careerlink.vn/vieclam/tim-kiem-viec-lam"
    root = Path(__file__).parents[1] / "fixtures/careerlink"
    htmls = [(root / f"detail_{i}.html").read_text() for i in (1, 2, 3)]
    urls = [HTMLParser(h).css_first('link[rel="canonical"]').attributes["href"] for h in htmls]
    respx.get("https://www.careerlink.vn/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    listing = (
        '<ul class="list-group">'
        + "".join(f'<li class="job-item"><a class="job-link" href="{u}">job</a></li>' for u in urls)
        + "</ul>"
    )
    listing_route = respx.get(start).mock(return_value=httpx.Response(200, text=listing))
    routes = [
        respx.get(u).mock(
            return_value=httpx.Response(200, text=h, headers={"Content-Type": "text/html"})
        )
        for u, h in zip(urls, htmls, strict=True)
    ]
    routes[1].mock(
        return_value=httpx.Response(
            200, text='<div class="h-captcha"></div>', headers={"Content-Type": "text/html"}
        )
    )
    config = CrawlConfig(
        source="careerlink",
        mode="bounded",
        start_url=start,
        output_dir=tmp_path,
        project_owner_public_test=True,
        user_agent="offline-test",
        max_pages=1,
        max_details=3,
        fetcher="http",
        save_html=True,
        require_complete_content=True,
        delay_min_seconds=10,
        delay_max_seconds=15,
        max_retries=0,
    )
    with CareerLinkHttpFetcher(config, sleep=lambda _: None) as fetcher:
        first = CrawlEngine(config, CareerLinkCrawler(), fetcher).run()
    assert first.detail_requested == 2 and first.records_written == 1
    batch = next(tmp_path.glob("careerlink/snapshot_date=*/batch_id=*"))
    before = (batch / "jobs.jsonl").read_bytes()
    routes[1].mock(
        return_value=httpx.Response(200, text=htmls[1], headers={"Content-Type": "text/html"})
    )
    resumed = replace(
        config, resume=True, resume_batch_id=first.batch_id, max_details=first.detail_requested + 1
    )
    with CareerLinkHttpFetcher(resumed, sleep=lambda _: None) as fetcher:
        second = CrawlEngine(resumed, CareerLinkCrawler(), fetcher).run()
    after = (batch / "jobs.jsonl").read_bytes()
    rows = [json.loads(line) for line in after.splitlines()]
    assert after.startswith(before)
    assert second.detail_requested == 3 and second.records_written == 2
    assert len({r["source_job_id"] for r in rows}) == 2
    assert listing_route.call_count == routes[0].call_count == 1
    assert routes[2].call_count == 0
