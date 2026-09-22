from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.base import FetchError, FetcherState, FetchResponse

RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
BLOCKED_STATUSES = {401, 403}
CHALLENGE_MARKERS = (
    "captcha",
    "cf-chl-",
    "cloudflare ray id",
    "verify you are human",
    "access denied",
)


def _retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return max(0.0, (target - current).total_seconds())


def _looks_like_challenge(text: str) -> bool:
    sample = text[:200_000].casefold()
    return any(marker in sample for marker in CHALLENGE_MARKERS)


class HttpFetcher:
    def __init__(
        self,
        config: CrawlConfig,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": config.user_agent, "Accept": "text/html,*/*;q=0.8"},
        )
        self._owns_client = client is None
        self._sleep = sleep
        self._monotonic = monotonic
        self._rng = rng or random.Random()
        self._last_request_at: float | None = None
        self.state = FetcherState(requested="http", active="http")

    def configure_run(self, _batch_root: Path, _batch_id: str) -> None:
        return None

    def fallback(self, _reason: str) -> bool:
        return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> HttpFetcher:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        delay = self._rng.uniform(self.config.delay_min_seconds, self.config.delay_max_seconds)
        elapsed = self._monotonic() - self._last_request_at
        if elapsed < delay:
            self._sleep(delay - elapsed)

    def get(self, url: str) -> FetchResponse:
        last_error: FetchError | None = None
        for attempt in range(1, self.config.max_retries + 2):
            self._rate_limit()
            request_started = self._monotonic()
            try:
                response = self._client.get(url)
                request_finished = self._monotonic()
                self._last_request_at = request_finished
            except httpx.RequestError as exc:
                self._last_request_at = self._monotonic()
                last_error = FetchError(
                    f"Temporary network error: {type(exc).__name__}",
                    url=url,
                    attempt=attempt,
                    retryable=True,
                )
                if attempt <= self.config.max_retries:
                    self._sleep(2 ** (attempt - 1) + self._rng.uniform(0, 0.5))
                    continue
                raise last_error from exc

            status = response.status_code
            if status in BLOCKED_STATUSES:
                raise FetchError(
                    f"Access stopped by HTTP {status}",
                    url=str(response.url),
                    attempt=attempt,
                    status_code=status,
                    blocked=True,
                )
            if status in RETRYABLE_STATUSES:
                last_error = FetchError(
                    f"Temporary HTTP {status}",
                    url=str(response.url),
                    attempt=attempt,
                    status_code=status,
                    retryable=True,
                    blocked=status == 429,
                )
                if attempt <= self.config.max_retries:
                    retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                    delay = retry_after
                    if delay is None:
                        delay = 2 ** (attempt - 1) + self._rng.uniform(0, 0.5)
                    self._sleep(delay)
                    continue
                raise last_error
            if status < 200 or status >= 400:
                raise FetchError(
                    f"HTTP {status}",
                    url=str(response.url),
                    attempt=attempt,
                    status_code=status,
                )
            content_type = response.headers.get("Content-Type", "").casefold()
            if "html" in content_type and _looks_like_challenge(response.text):
                raise FetchError(
                    "Anti-bot challenge detected; stopping without bypass",
                    url=str(response.url),
                    attempt=attempt,
                    status_code=status,
                    blocked=True,
                )
            return FetchResponse(
                url=str(response.url),
                text=response.text,
                status_code=status,
                headers=dict(response.headers),
                attempt=attempt,
                duration_seconds=max(0.0, request_finished - request_started),
                fetcher="http",
            )
        if last_error is not None:  # pragma: no cover - loop always returns or raises
            raise last_error
        raise AssertionError("unreachable")
