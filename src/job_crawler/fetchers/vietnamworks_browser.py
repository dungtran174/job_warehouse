"""Owner-selected ordinary browser; evidence first, no fallback or block retry."""

from __future__ import annotations

import gzip
import hashlib
import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from selectolax.parser import HTMLParser

from job_crawler.fetchers.base import FetchError, FetchResponse
from job_crawler.fetchers.playwright import PlaywrightFetcher, classify_browser_page
from job_crawler.fetchers.timviec365 import robots_denies
from job_crawler.parsers.vietnamworks_detail import job_id_from_url

ROBOTS = "https://www.vietnamworks.com/robots.txt"
LISTING_PATHS = {"/viec-lam", "/tim-viec-lam/tim-tat-ca-viec-lam"}
DETAIL_READY_SCRIPT = """() => {
    const labels = new Set(['mô tả công việc', 'yêu cầu công việc',
                            'job description', 'job requirements']);
    const headings = [...document.querySelectorAll('h2')].filter(
        h => labels.has(h.textContent.trim().toLowerCase()));
    return headings.length >= 2 && headings.every(h => {
        const siblings = [...h.parentElement.children];
        const content = siblings.filter(n => n.tagName === 'DIV').at(-1);
        return content && content.innerText.trim().length > 0;
    });
}"""


def in_scope(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.hostname == "www.vietnamworks.com"
        and (url == ROBOTS or parts.path in LISTING_PATHS or job_id_from_url(url) is not None)
    )


class VietnamWorksBrowserFetcher(PlaywrightFetcher):
    def configure_run(self, root: Path, batch_id: str) -> None:
        super().configure_run(root, batch_id)
        self.evidence_root = root / "http"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.robots_text: str | None = None
        self.stopped = False
        self.stop_blocked = False
        self._guard_installed = False

    def _allowed(self, url: str) -> bool:
        if not in_scope(url):
            return False
        if url == ROBOTS:
            return True
        if self.robots_text is None or robots_denies(self.robots_text, url):
            return False
        robot = RobotFileParser()
        robot.parse(self.robots_text.splitlines())
        return robot.can_fetch(self.config.user_agent, url)

    def _guard(self, route: Any) -> None:
        request = route.request
        if self.stopped or (
            request.is_navigation_request()
            and request.frame == request.frame.page.main_frame
            and not self._allowed(request.url)
        ):
            route.abort()
            return
        route.continue_()

    def _prepare_main(self, page: Any) -> None:
        page.locator(".block-job-list .search_list a[href]").first.wait_for(timeout=15000)
        page.locator(".pagination").scroll_into_view_if_needed(timeout=10000)
        previous = -1
        stable = 0
        for _ in range(10):
            if self.stopped:
                return
            page.wait_for_timeout(500)
            count = page.locator(".block-job-list .search_list").count()
            stable = stable + 1 if count == previous else 0
            previous = count
            if stable >= 3:
                return
        raise ValueError("Main results did not stabilize within bounded render")

    def get(self, url: str) -> FetchResponse:
        if not hasattr(self, "evidence_root"):
            raise RuntimeError("configure_run required before browser capture")
        if self.stopped:
            raise FetchError(
                "VietnamWorks browser already stopped",
                url=url,
                attempt=1,
                blocked=self.stop_blocked,
                terminal=True,
            )
        if not self._allowed(url):
            self.stopped = True
            self.stop_blocked = True
            raise FetchError(
                "VietnamWorks scope/robots denied", url=url, attempt=1, blocked=True, terminal=True
            )
        self._ensure_started()
        if not self._guard_installed:
            self._context.route("**/*", self._guard)
            self._guard_installed = True
        self._rate_limit()
        page = self._context.new_page()
        started = self._monotonic()
        token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8]
        body_path = self.evidence_root / f"{token}.body.gz"
        html_path = self.evidence_root / f"{token}.html.gz"
        meta_path = self.evidence_root / f"{token}.json"
        meta: dict[str, Any] = {
            "requested_at": datetime.now(UTC).isoformat(),
            "requested_url": url,
            "fetcher": "playwright",
            "headless": False,
            "retry_count": 0,
            "delay_min_seconds": self.config.delay_min_seconds,
            "delay_max_seconds": self.config.delay_max_seconds,
        }
        response = None
        main_responses: list[Any] = []
        source_denials: list[dict[str, Any]] = []
        public_search_responses: list[dict[str, Any]] = []
        body = b""
        html = ""
        status = None
        title = ""
        headers: dict[str, str] = {}

        def persist() -> None:
            meta.update(
                final_url=page.url,
                http_status=status,
                body_path=body_path.name if body_path.exists() else None,
                html_path=html_path.name if html_path.exists() else None,
                source_denials=source_denials,
                public_search_responses=public_search_responses,
            )
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        def observe(r: Any) -> None:
            host = urlsplit(r.url).hostname or ""
            resource = r.request.resource_type
            if resource == "document" and r.request.frame == page.main_frame:
                main_responses.append(r)
            if (
                (host == "vietnamworks.com" or host.endswith(".vietnamworks.com"))
                and r.status in {401, 403, 429}
                and resource in {"document", "xhr", "fetch"}
            ):
                source_denials.append({"url": r.url, "status": r.status})
                self.stopped = self.stop_blocked = True
            if r.url == "https://ms.vietnamworks.com/job-search/v1.0/search":
                public_search_responses.append(
                    {"url": r.url, "status": r.status, "method": r.request.method}
                )

        def challenge_type() -> str | None:
            found = classify_browser_page(title, page.url, "", html)
            if found is None and HTMLParser(html).css_first(
                '.h-captcha, iframe[src*="hcaptcha.com"], iframe[src*="challenges.cloudflare.com"]'
            ):
                return "captcha"
            return found

        page.on("response", observe)
        try:
            response = page.goto(
                url, wait_until="domcontentloaded", timeout=self.config.timeout_seconds * 1000
            )
            status = int(response.status) if response else None
            headers = dict(response.headers) if response else {}
            meta["phase"] = "HTTP received before DOM"
            persist()
            if response:
                body = response.body()
                body_path.write_bytes(gzip.compress(body))
                meta["body_sha256"] = hashlib.sha256(body).hexdigest()
                persist()
            html = page.content()
            title = page.title()
            challenge = (
                classify_browser_page(
                    title, page.url, page.locator("body").inner_text(timeout=3000), html
                )
                or challenge_type()
            )
            if not self.stopped and status == 200 and challenge is None and url != ROBOTS:
                if urlsplit(page.url).path in LISTING_PATHS:
                    self._prepare_main(page)
                else:
                    page.locator("h1").first.wait_for(timeout=15000)
                    page.locator("h2").first.wait_for(timeout=15000)
                    # Headings may precede hydration of the actual full sections.
                    # Wait in the same page, without another navigation/request retry.
                    page.wait_for_function(DETAIL_READY_SCRIPT, timeout=15000)
                if not self.stopped:
                    page.wait_for_timeout(self.config.browser_wait_ms)
                html = page.content()
                title = page.title()
                visible = page.locator("body").inner_text(timeout=3000)
                challenge = (
                    classify_browser_page(title, page.url, visible, html) or challenge_type()
                )
            blocked = status in {401, 403, 429} or challenge is not None or bool(source_denials)
            html_path.write_bytes(gzip.compress(html.encode()))
            meta.update(
                html_sha256=hashlib.sha256(html.encode()).hexdigest(),
                page_title=title,
                challenge_type=challenge,
                blocked=blocked,
                main_document_responses=[
                    {"url": r.url, "status": r.status} for r in main_responses
                ],
                received_at=datetime.now(UTC).isoformat(),
                retry_after=headers.get("retry-after"),
            )
            persist()
            if blocked or status != 200:
                self.stopped = True
                self.stop_blocked = blocked
                self.state.challenge_detected = challenge is not None
                raise FetchError(
                    f"VietnamWorks browser stopped: HTTP {status}; challenge={challenge}",
                    url=page.url,
                    attempt=1,
                    status_code=status,
                    blocked=blocked,
                    terminal=True,
                    challenge_type=challenge,
                )
            if url == ROBOTS:
                if "html" in headers.get("content-type", ""):
                    raise ValueError("Robots permission unknown: HTML rather than rules")
                self.robots_text = body.decode("utf-8-sig")
                text = self.robots_text
            else:
                text = html
            return FetchResponse(
                url=page.url,
                text=text,
                status_code=200,
                headers=headers,
                attempt=1,
                duration_seconds=self._monotonic() - started,
                fetcher="playwright",
                page_title=title,
            )
        except (PlaywrightError, FetchError, ValueError) as exc:
            self.stopped = True
            capture_errors = []
            if response is None and main_responses:
                response = main_responses[-1]
                status = int(response.status)
            if response is not None and not body_path.exists():
                try:
                    body = response.body()
                    body_path.write_bytes(gzip.compress(body))
                    meta["body_sha256"] = hashlib.sha256(body).hexdigest()
                except PlaywrightError as capture_exc:
                    capture_errors.append(str(capture_exc))
            if not html:
                try:
                    html = page.content()
                except PlaywrightError as capture_exc:
                    capture_errors.append(str(capture_exc))
            if html:
                html_path.write_bytes(gzip.compress(html.encode()))
            if not html and body:
                html = body.decode(errors="replace")
            challenge = challenge_type()
            blocked = status in {401, 403, 429} or challenge is not None or bool(source_denials)
            self.stop_blocked = blocked
            self.state.challenge_detected = challenge is not None
            meta.update(
                error=type(exc).__name__,
                original_error=str(exc),
                capture_errors=capture_errors,
                blocked=blocked,
                challenge_type=challenge,
                received_at=datetime.now(UTC).isoformat(),
            )
            persist()
            raise FetchError(
                f"VietnamWorks browser stopped: {type(exc).__name__}: {exc}",
                url=page.url or url,
                attempt=1,
                status_code=status,
                blocked=blocked,
                terminal=True,
                challenge_type=challenge,
                artifact_paths=tuple(
                    str(p) for p in (body_path, html_path, meta_path) if p.exists()
                ),
            ) from exc
        finally:
            if self.config.save_screenshot_on_error and self.stopped:
                with suppress(PlaywrightError):
                    screenshot = self.evidence_root / f"{token}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    meta["screenshot_path"] = screenshot.name
                    persist()
            self._last_request_at = self._monotonic()
            with suppress(PlaywrightError):
                page.close()
