from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.base import FetchError, FetcherState, FetchResponse
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.playwright import PlaywrightFetcher, classify_browser_page
from job_crawler.parsers.vietnamworks_listing import parse_listing


class VietnamWorksListingBrowser(PlaywrightFetcher):
    def _prepare_page(self, page: Any) -> None:
        challenge = classify_browser_page(
            page.title(), page.url, page.locator("body").inner_text(timeout=3000), page.content()
        )
        if challenge:
            self.state.challenge_detected = True
            raise FetchError(
                "Listing render stopped at challenge",
                url=page.url,
                attempt=1,
                blocked=True,
                challenge_type=challenge,
            )
        page.locator(".block-job-list .search_list a[href]").first.wait_for(timeout=10000)
        page.locator(".pagination").scroll_into_view_if_needed(timeout=10000)
        # Search cards are lazy rendered. Scrolling to pagination loads the full page.
        previous = -1
        stable = 0
        for _ in range(10):
            page.wait_for_timeout(500)
            count = page.locator(".block-job-list .search_list").count()
            stable = stable + 1 if count == previous else 0
            previous = count
            if stable >= 3:
                return
        raise ValueError("Primary listing did not stabilize after bounded render")


class VietnamWorksFetcher:
    """HTTP on every URL; standard browser only for an accessible JS listing."""

    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.http = HttpFetcher(config)
        self.browser = VietnamWorksListingBrowser(config)
        self.state = FetcherState(requested="auto", active="http")

    def configure_run(self, root: Path, batch_id: str) -> None:
        self.http.configure_run(root, batch_id)
        self.browser.configure_run(root, batch_id)

    def fallback(self, _reason: str) -> bool:
        return False

    def get(self, url: str) -> FetchResponse:
        try:
            response = self.http.get(url)
            path = urlsplit(url).path
            is_listing = path in {"/viec-lam", "/tim-viec-lam/tim-tat-ca-viec-lam"}
            if is_listing and not parse_listing(response.text, response.url).jobs:
                self.state.fallback_used = True
                self.state.headless = not self.config.headed
                self.state.active = "playwright"
                response = self.browser.get(url)
            self.state.active = response.fetcher
            return response
        except FetchError as exc:
            self.state.challenge_detected = exc.blocked
            raise

    def close(self) -> None:
        self.http.close()
        self.browser.close()

    def __enter__(self) -> VietnamWorksFetcher:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
