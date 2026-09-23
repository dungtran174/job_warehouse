from __future__ import annotations

import gzip
import json
import logging
import os
import random
import re
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.base import FetchError, FetcherState, FetchResponse

LOGGER = logging.getLogger(__name__)

CAPTCHA_MARKERS = (
    "captcha",
    "verify you are human",
    "xác minh bạn là con người",
    "just a moment",
)
CAPTCHA_HTML_MARKERS = ("cf-chl-", "cf-turnstile", "g-recaptcha")
ACCESS_DENIED_MARKERS = (
    "access denied",
    "request unsuccessful",
    "truy cập bị từ chối",
    "permission denied",
    "sorry, you have been blocked",
    "unable to access",
    "attention required",
)
NETWORK_ERROR_MARKERS = (
    "net::err_",
    "connection closed",
    "connection reset",
    "timed out",
    "timeout",
)


def classify_browser_page(title: str, url: str, visible_text: str, html: str = "") -> str | None:
    visible = f"{title}\n{visible_text[:100_000]}".casefold()
    html_excerpt = html[:100_000].casefold()
    if any(marker in visible for marker in ACCESS_DENIED_MARKERS):
        return "access_denied"
    if any(marker in visible for marker in CAPTCHA_MARKERS) or any(
        marker in html_excerpt for marker in CAPTCHA_HTML_MARKERS
    ):
        return "captcha"
    path = urlsplit(url).path.casefold()
    if path.startswith(("/login", "/dang-nhap")):
        return "login_required"
    return None


def _is_network_error(error: Exception) -> bool:
    message = str(error).casefold()
    return isinstance(error, PlaywrightTimeoutError) or any(
        marker in message for marker in NETWORK_ERROR_MARKERS
    )


def _safe_slug(url: str) -> str:
    name = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or "page"
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", name)[:80]


class PlaywrightFetcher:
    def __init__(
        self,
        config: CrawlConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
        playwright_factory: Callable[[], Any] = sync_playwright,
    ) -> None:
        self.config = config
        self.state = FetcherState(
            requested="playwright", active="playwright", headless=not config.headed
        )
        self._sleep = sleep
        self._monotonic = monotonic
        self._rng = rng or random.Random()
        self._playwright_factory = playwright_factory
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._last_request_at: float | None = None
        self._batch_root: Path | None = None
        self._batch_id: str | None = None
        self._artifact_counter = 0
        self._success_screenshot_saved = False

    def configure_run(self, batch_root: Path, batch_id: str) -> None:
        self._batch_root = batch_root
        self._batch_id = batch_id

    def fallback(self, _reason: str) -> bool:
        return False

    def _ensure_started(self) -> None:
        if self._context is not None:
            return
        self._playwright = self._playwright_factory().start()
        self._browser = self._playwright.chromium.launch(headless=not self.config.headed)
        self._context = self._browser.new_context()

    def close(self) -> None:
        for resource in (self._context, self._browser, self._playwright):
            if resource is None:
                continue
            try:
                if resource is self._playwright:
                    resource.stop()
                else:
                    resource.close()
            except Exception:  # pragma: no cover - cleanup is best effort
                LOGGER.exception("Failed to close Playwright resource")
        self._context = None
        self._browser = None
        self._playwright = None

    def __enter__(self) -> PlaywrightFetcher:
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

    def _artifact_stem(self, url: str, kind: str) -> str:
        self._artifact_counter += 1
        return f"{kind}-{self._artifact_counter:03d}-{_safe_slug(url)}"

    def _save_artifacts(
        self, page: Any, url: str, html: str, *, kind: str, screenshot: bool
    ) -> tuple[str, ...]:
        if self._batch_root is None:
            return ()
        stem = self._artifact_stem(url, kind)
        paths: list[str] = []
        html_dir = self._batch_root / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"{stem}.html.gz"
        temporary = html_dir / f".{stem}.html.gz.tmp"
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            handle.write(html)
        os.replace(temporary, html_path)
        paths.append(str(html_path.relative_to(self._batch_root)))
        if screenshot:
            screenshot_dir = self._batch_root / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = screenshot_dir / f"{stem}.png"
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                paths.append(str(screenshot_path.relative_to(self._batch_root)))
            except Exception:
                LOGGER.exception("Could not save browser screenshot")
        return tuple(paths)

    @staticmethod
    def _accept_cookie_consent(page: Any) -> None:
        for selector in (
            "#onetrust-accept-btn-handler",
            "[data-testid='cookie-accept']",
            "button.cookie-accept",
        ):
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=500):
                    locator.click(timeout=1000)
                    return
            except Exception:
                continue

    def _get_text_resource(self, url: str) -> FetchResponse:
        self._ensure_started()
        self._rate_limit()
        started = self._monotonic()
        response = self._context.request.get(url, timeout=self.config.timeout_seconds * 1000)
        finished = self._monotonic()
        self._last_request_at = finished
        status = int(response.status)
        if status < 200 or status >= 400:
            raise FetchError(
                f"HTTP {status}",
                url=str(response.url),
                attempt=1,
                status_code=status,
                blocked=status in {401, 403},
            )
        return FetchResponse(
            url=str(response.url),
            text=response.text(),
            status_code=status,
            headers=dict(response.headers),
            attempt=1,
            duration_seconds=max(0.0, finished - started),
            fetcher="playwright",
        )

    def get(self, url: str) -> FetchResponse:
        if urlsplit(url).path == "/robots.txt":
            return self._get_text_resource(url)
        self._ensure_started()
        last_error: FetchError | None = None
        for attempt in range(1, self.config.max_retries + 2):
            self._rate_limit()
            page = self._context.new_page()
            started = self._monotonic()
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.config.timeout_seconds * 1000,
                )
                self._accept_cookie_consent(page)
                with suppress(PlaywrightTimeoutError):
                    page.locator(
                        "a[href*='/viec-lam/'], script[type='application/ld+json'], h1"
                    ).first.wait_for(timeout=min(self.config.timeout_seconds * 1000, 8000))
                if self.config.browser_wait_ms:
                    page.wait_for_timeout(self.config.browser_wait_ms)
                for _ in range(2):
                    page.evaluate("window.scrollBy(0, Math.min(window.innerHeight, 900))")
                    page.wait_for_timeout(250)
                html = page.content()
                title = page.title()
                final_url = page.url
                visible_text = page.locator("body").inner_text(timeout=3000)
                status = int(response.status) if response is not None else 0
                headers = dict(response.headers) if response is not None else {}
                finished = self._monotonic()
                self._last_request_at = finished
                challenge = classify_browser_page(title, final_url, visible_text, html)
                if status in {401, 403} and challenge is None:
                    challenge = "access_denied"
                if challenge is not None:
                    self.state.challenge_detected = True
                    artifacts = self._save_artifacts(
                        page,
                        final_url,
                        html,
                        kind=challenge,
                        screenshot=self.config.save_screenshot_on_error,
                    )
                    raise FetchError(
                        f"Browser stopped at {challenge}",
                        url=final_url,
                        attempt=attempt,
                        status_code=status or None,
                        blocked=True,
                        challenge_type=challenge,
                        artifact_paths=artifacts,
                    )
                screenshot_path = None
                if self.config.save_html and not self._success_screenshot_saved:
                    artifacts = self._save_artifacts(
                        page,
                        final_url,
                        html,
                        kind="rendered",
                        screenshot=True,
                    )
                    screenshot_path = next(
                        (path for path in artifacts if path.startswith("screenshots/")), None
                    )
                    self._success_screenshot_saved = screenshot_path is not None
                LOGGER.info(
                    json.dumps(
                        {
                            "event": "browser_page",
                            "batch_id": self._batch_id,
                            "url": final_url,
                            "title": title,
                            "status": status,
                            "attempt": attempt,
                        },
                        ensure_ascii=False,
                    )
                )
                return FetchResponse(
                    url=final_url,
                    text=html,
                    status_code=status,
                    headers=headers,
                    attempt=attempt,
                    duration_seconds=max(0.0, finished - started),
                    fetcher="playwright",
                    page_title=title,
                    screenshot_path=screenshot_path,
                )
            except FetchError:
                raise
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                finished = self._monotonic()
                self._last_request_at = finished
                retryable = _is_network_error(exc)
                last_error = FetchError(
                    f"Playwright navigation error: {type(exc).__name__}",
                    url=page.url or url,
                    attempt=attempt,
                    retryable=retryable,
                )
                if retryable and attempt <= self.config.max_retries:
                    self._sleep(2 ** (attempt - 1) + self._rng.uniform(0, 0.5))
                    continue
                html = ""
                with suppress(Exception):
                    html = page.content()
                artifacts = self._save_artifacts(
                    page,
                    page.url or url,
                    html,
                    kind="browser-error",
                    screenshot=self.config.save_screenshot_on_error,
                )
                last_error.artifact_paths = artifacts
                raise last_error from exc
            finally:
                with suppress(Exception):
                    page.close()
        if last_error is not None:  # pragma: no cover
            raise last_error
        raise AssertionError("unreachable")
