from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.base import Fetcher, FetchError, FetcherState, FetchResponse
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.playwright import PlaywrightFetcher


class AutoFetcher:
    def __init__(
        self,
        config: CrawlConfig,
        *,
        http_fetcher: Fetcher | None = None,
        playwright_factory: Callable[[CrawlConfig], Fetcher] = PlaywrightFetcher,
    ) -> None:
        self.config = config
        self._http = http_fetcher or HttpFetcher(config)
        self._playwright_factory = playwright_factory
        self._playwright: Fetcher | None = None
        self._active: Fetcher = self._http
        self._batch_root: Path | None = None
        self._batch_id: str | None = None
        self.state = FetcherState(requested="auto", active="http")

    def configure_run(self, batch_root: Path, batch_id: str) -> None:
        self._batch_root = batch_root
        self._batch_id = batch_id
        self._http.configure_run(batch_root, batch_id)

    def fallback(self, _reason: str) -> bool:
        if self.state.fallback_used:
            return False
        self._playwright = self._playwright_factory(self.config)
        if self._batch_root is not None and self._batch_id is not None:
            self._playwright.configure_run(self._batch_root, self._batch_id)
        self._active = self._playwright
        self.state.active = "playwright"
        self.state.fallback_used = True
        self.state.headless = not self.config.headed
        return True

    def get(self, url: str) -> FetchResponse:
        try:
            response = self._active.get(url)
        except FetchError:
            if self._active.state.challenge_detected:
                self.state.challenge_detected = True
            raise
        self.state.active = response.fetcher
        if self._active.state.challenge_detected:
            self.state.challenge_detected = True
        return response

    def close(self) -> None:
        self._http.close()
        if self._playwright is not None:
            self._playwright.close()

    def __enter__(self) -> AutoFetcher:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
