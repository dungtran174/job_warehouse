from pathlib import Path

import pytest

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.auto import AutoFetcher
from job_crawler.fetchers.base import FetchError, FetcherState, FetchResponse
from job_crawler.fetchers.factory import create_fetcher
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.playwright import PlaywrightFetcher


class FakeFetcher:
    def __init__(self, name: str, responses: list[FetchResponse | Exception]) -> None:
        self.state = FetcherState(requested=name, active=name)
        self.responses = responses
        self.calls = 0
        self.closed = False

    def configure_run(self, _batch_root: Path, _batch_id: str) -> None:
        return None

    def get(self, _url: str) -> FetchResponse:
        self.calls += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def fallback(self, _reason: str) -> bool:
        return False

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def response(fetcher: str) -> FetchResponse:
    return FetchResponse(
        url="https://www.topcv.vn/jobs",
        text="<html></html>",
        status_code=200,
        headers={},
        attempt=1,
        duration_seconds=0.1,
        fetcher=fetcher,
    )


def config(fetcher: str = "auto") -> CrawlConfig:
    return CrawlConfig(
        fetcher=fetcher,  # type: ignore[arg-type]
        authorization_reference="APPROVAL",
        user_agent="crawler (contact=data@example.org)",
    )


def test_auto_stops_on_http_403_without_browser_fallback() -> None:
    http = FakeFetcher(
        "http",
        [
            FetchError(
                "blocked",
                url="https://www.topcv.vn/jobs",
                attempt=1,
                status_code=403,
                blocked=True,
            )
        ],
    )
    browser = FakeFetcher("playwright", [response("playwright")])
    fetcher = AutoFetcher(config(), http_fetcher=http, playwright_factory=lambda _cfg: browser)
    with pytest.raises(FetchError, match="blocked"):
        fetcher.get("https://www.topcv.vn/jobs")
    assert not fetcher.state.fallback_used
    assert http.calls == 1
    assert browser.calls == 0
    fetcher.close()
    assert http.closed and not browser.closed


def test_auto_can_render_after_successful_http_listing() -> None:
    http = FakeFetcher("http", [response("http")])
    browser = FakeFetcher("playwright", [response("playwright")])
    fetcher = AutoFetcher(config(), http_fetcher=http, playwright_factory=lambda _cfg: browser)
    assert fetcher.get("https://www.topcv.vn/jobs").fetcher == "http"
    assert fetcher.fallback("empty_listing")
    assert fetcher.get("https://www.topcv.vn/jobs").fetcher == "playwright"
    assert fetcher.state.fallback_used
    assert not fetcher.fallback("again")
    assert (http.calls, browser.calls) == (1, 1)
    fetcher.close()
    assert http.closed and browser.closed


def test_factory_selects_requested_fetcher() -> None:
    http = create_fetcher(config("http"))
    browser = create_fetcher(config("playwright"))
    auto = create_fetcher(config("auto"))
    assert isinstance(http, HttpFetcher)
    assert isinstance(browser, PlaywrightFetcher)
    assert isinstance(auto, AutoFetcher)
    http.close()
    browser.close()
    auto.close()
