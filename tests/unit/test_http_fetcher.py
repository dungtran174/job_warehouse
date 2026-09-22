import httpx
import respx

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.http import FetchError, HttpFetcher


def fetcher_config(**overrides) -> CrawlConfig:
    values = {
        "authorization_reference": "APPROVAL-1",
        "user_agent": "crawler/1.0 (contact=data@example.org)",
        "delay_min_seconds": 0,
        "delay_max_seconds": 0,
        "max_retries": 1,
    }
    values.update(overrides)
    return CrawlConfig(**values)


@respx.mock
def test_retry_after_is_honored() -> None:
    route = respx.get("https://example.org/page").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, text="ok", headers={"Content-Type": "text/plain"}),
        ]
    )
    sleeps: list[float] = []
    with HttpFetcher(fetcher_config(), sleep=sleeps.append) as fetcher:
        response = fetcher.get("https://example.org/page")
    assert response.text == "ok"
    assert response.attempt == 2
    assert route.call_count == 2
    assert sleeps == [0.0]


@respx.mock
def test_challenge_stops_without_retry() -> None:
    route = respx.get("https://example.org/page").mock(
        return_value=httpx.Response(
            200,
            text="<html><title>Verify you are human</title></html>",
            headers={"Content-Type": "text/html"},
        )
    )
    with HttpFetcher(fetcher_config(max_retries=3), sleep=lambda _seconds: None) as fetcher:
        try:
            fetcher.get("https://example.org/page")
        except FetchError as exc:
            assert exc.blocked
        else:  # pragma: no cover
            raise AssertionError("challenge must stop the fetch")
    assert route.call_count == 1
