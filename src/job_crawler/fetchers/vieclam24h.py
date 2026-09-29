"""Ordinary browser chosen before access; no HTTP/browser fallback or block retry."""

from __future__ import annotations

import gzip
import hashlib
import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from selectolax.parser import HTMLParser

from job_crawler.fetchers.base import FetchError, FetchResponse
from job_crawler.fetchers.playwright import PlaywrightFetcher, classify_browser_page
from job_crawler.fetchers.timviec365 import robots_denies
from job_crawler.parsers.vieclam24h import HOST, job_url, listing_url_allowed

ROBOTS = f"https://{HOST}/robots.txt"


class Vieclam24hBrowserFetcher(PlaywrightFetcher):
    def configure_run(self, batch_root: Path, batch_id: str) -> None:
        super().configure_run(batch_root, batch_id)
        self.evidence_root = batch_root / "http"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.robots_text: str | None = None
        self.stopped = False
        self._stop_blocked = False
        self._scope_installed = False

    def _guard_navigation(self, route: Any) -> None:
        request = route.request
        if request.is_navigation_request() and request.frame == request.frame.page.main_frame:
            target = request.url
            if target != ROBOTS and not listing_url_allowed(target) and job_url(target) is None:
                route.abort()
                return
            if self.robots_text is not None and robots_denies(self.robots_text, target):
                route.abort()
                return
        route.continue_()

    def get(self, url: str) -> FetchResponse:
        if not hasattr(self, "evidence_root"):
            raise RuntimeError("configure_run required before browser capture")
        if self.stopped:
            raise FetchError(
                "Việc Làm 24h already stopped",
                url=url,
                attempt=1,
                blocked=self._stop_blocked,
                terminal=True,
            )
        valid = url == ROBOTS or listing_url_allowed(url) or job_url(url) is not None
        if not valid or (
            url != ROBOTS and (self.robots_text is None or robots_denies(self.robots_text, url))
        ):
            self.stopped = True
            self._stop_blocked = True
            raise FetchError(
                "Việc Làm 24h scope/robots denied", url=url, attempt=1, blocked=True, terminal=True
            )
        self._ensure_started()
        if not self._scope_installed:
            self._context.route("**/*", self._guard_navigation)
            self._scope_installed = True
        self._rate_limit()
        page = self._context.new_page()
        requested_at = datetime.now(UTC)
        started = self._monotonic()
        response = None
        status = None
        body = b""
        html = ""
        headers: dict[str, str] = {}
        main_responses: list[Any] = []
        source_denials: list[dict[str, object]] = []
        token = requested_at.strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8]
        body_path = self.evidence_root / f"{token}.body.gz"
        html_path = self.evidence_root / f"{token}.html.gz"
        meta_path = self.evidence_root / f"{token}.json"

        def observe(r: Any) -> None:
            host = urlsplit(r.url).hostname or ""
            if (
                r.request.resource_type == "document"
                and host == HOST
                and (getattr(r.request, "frame", None) == getattr(page, "main_frame", None))
            ):
                main_responses.append(r)
            if (
                (host == HOST or host.endswith("." + HOST))
                and int(r.status) in {401, 403, 429}
                and r.request.resource_type in {"document", "xhr", "fetch"}
            ):
                source_denials.append({"url": r.url, "status": int(r.status)})

        page.on("response", observe)
        try:
            response = page.goto(
                url, wait_until="domcontentloaded", timeout=self.config.timeout_seconds * 1000
            )
            status = int(response.status) if response else None
            headers = dict(response.headers) if response else {}
            # Persist the original HTTP response BEFORE DOM reads/waits can fail.
            meta_path.write_text(
                json.dumps(
                    {
                        "requested_at": requested_at.isoformat(),
                        "requested_url": url,
                        "final_url": page.url,
                        "http_status": status,
                        "phase": "http_received_before_dom",
                        "body_path": None,
                        "html_path": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            if response:
                body = response.body()
                body_path.write_bytes(gzip.compress(body))
            if status not in {401, 403, 429} and not source_denials and url != ROBOTS:
                page.wait_for_timeout(self.config.browser_wait_ms)
            html = page.content()
            title = page.title()
            visible = page.locator("body").inner_text(timeout=3000)
            challenge = None
            if url != ROBOTS or "html" in headers.get("content-type", ""):
                challenge = classify_browser_page(title, page.url, visible, html)
                if challenge is None and HTMLParser(html).css_first(
                    '.h-captcha, iframe[src*="hcaptcha.com"]'
                ):
                    challenge = "captcha"
            blocked = status in {401, 403, 429} or challenge is not None or bool(source_denials)
            html_path.write_bytes(gzip.compress(html.encode()))
            metadata: dict[str, object] = {
                "requested_at": requested_at.isoformat(),
                "received_at": datetime.now(UTC).isoformat(),
                "requested_url": url,
                "final_url": page.url,
                "http_status": status,
                "body_path": body_path.name if body_path.exists() else None,
                "body_sha256": hashlib.sha256(body).hexdigest() if body_path.exists() else None,
                "html_path": html_path.name,
                "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
                "page_title": title,
                "challenge_type": challenge,
                "blocked": blocked,
                "source_denials": source_denials,
                "retry_after": headers.get("retry-after"),
                "delay_min_seconds": self.config.delay_min_seconds,
                "delay_max_seconds": self.config.delay_max_seconds,
            }
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
            artifacts: tuple[str, ...] = (str(body_path), str(html_path), str(meta_path))
            if blocked or status != 200:
                self.stopped = True
                self._stop_blocked = blocked
                self.state.challenge_detected = challenge is not None
                error_artifacts = self._save_artifacts(
                    page,
                    page.url,
                    html,
                    kind="blocked" if blocked else "http_error",
                    screenshot=self.config.save_screenshot_on_error,
                )
                raise FetchError(
                    f"Việc Làm 24h stopped: HTTP {status}; challenge={challenge}",
                    url=page.url,
                    attempt=1,
                    status_code=status,
                    blocked=blocked,
                    terminal=True,
                    challenge_type=challenge,
                    artifact_paths=(*artifacts, *error_artifacts),
                )
            if url == ROBOTS:
                text = body.decode(errors="replace")
                if "html" in headers.get("content-type", ""):
                    self.stopped = True
                    raise FetchError(
                        "Robots rules unknown (HTML response)",
                        url=url,
                        attempt=1,
                        terminal=True,
                        artifact_paths=artifacts,
                    )
                self.robots_text = text
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
        except PlaywrightError as exc:
            self.stopped = True
            capture_errors = []
            if response is None and main_responses:
                response = main_responses[-1]
                status = int(response.status)
                headers = dict(response.headers)
            if response is not None and not body_path.exists():
                try:
                    body = response.body()
                    body_path.write_bytes(gzip.compress(body))
                except PlaywrightError as capture_exc:
                    capture_errors.append(str(capture_exc))
            try:
                html = page.content()
                html_path.write_bytes(gzip.compress(html.encode()))
            except PlaywrightError as capture_exc:
                capture_errors.append(str(capture_exc))
            original_html = body.decode(errors="replace")
            challenge = classify_browser_page("", page.url, "", html or original_html)
            if challenge is None and HTMLParser(html or original_html).css_first(
                '.h-captcha, iframe[src*="hcaptcha.com"]'
            ):
                challenge = "captcha"
            blocked = status in {401, 403, 429} or challenge is not None or bool(source_denials)
            self._stop_blocked = blocked
            self.state.challenge_detected = challenge is not None
            metadata = {
                "requested_at": requested_at.isoformat(),
                "received_at": datetime.now(UTC).isoformat(),
                "requested_url": url,
                "final_url": page.url,
                "http_status": status,
                "body_path": body_path.name if body_path.exists() else None,
                "body_sha256": hashlib.sha256(body).hexdigest() if body_path.exists() else None,
                "html_path": html_path.name if html_path.exists() else None,
                "html_sha256": hashlib.sha256(html.encode()).hexdigest()
                if html_path.exists()
                else None,
                "error": type(exc).__name__,
                "original_error": str(exc),
                "capture_errors": capture_errors,
                "challenge_type": challenge,
                "blocked": blocked,
                "source_denials": source_denials,
                "retry_after": headers.get("retry-after"),
                "delay_min_seconds": self.config.delay_min_seconds,
                "delay_max_seconds": self.config.delay_max_seconds,
            }
            # Secondary artifact failures must not mask the original navigation error.
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
            try:
                artifacts = self._save_artifacts(
                    page,
                    page.url,
                    html,
                    kind="browser_error",
                    screenshot=self.config.save_screenshot_on_error,
                )
            except PlaywrightError as capture_exc:
                capture_errors.append(str(capture_exc))
                meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
                artifacts = ()
            captured = tuple(
                str(path) for path in (body_path, html_path, meta_path) if path.exists()
            )
            raise FetchError(
                "Việc Làm 24h browser navigation error",
                url=page.url,
                attempt=1,
                status_code=status,
                blocked=blocked,
                terminal=True,
                challenge_type=challenge,
                artifact_paths=(*captured, *artifacts),
            ) from exc
        finally:
            self._last_request_at = self._monotonic()
            with suppress(PlaywrightError):
                page.close()
