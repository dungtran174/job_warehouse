"""Single-threaded HTTP with response evidence saved before all access checks."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from selectolax.parser import HTMLParser

from job_crawler.fetchers.base import FetchError, FetchResponse
from job_crawler.fetchers.http import HttpFetcher, _looks_like_challenge
from job_crawler.parsers.careerlink import job_url


def is_challenge(html: str) -> bool:
    # Only the observed dormant login widget is excluded. Never execute it.
    # Any visible challenge, other widget, or Cloudflare marker still stops access.
    tree = HTMLParser(html)
    title = tree.css_first("title")
    if title and "just a moment" in title.text().casefold():
        return True
    for node in tree.css("#loginModal form#jobseeker_login_form #captcha_container"):
        if not node.text(strip=True) and not node.css("iframe,script,input"):
            node.decompose()
    for node in tree.css("script"):
        script = node.text()
        if (
            "var loadCaptcha = function" in script
            and "submitInvisibleRecaptchaJobSeekerLoginForm" in script
            and "$('#loginModal').on('shown.bs.modal'" in script
        ):
            node.decompose()
    return _looks_like_challenge(tree.html or html)


class CareerLinkHttpFetcher(HttpFetcher):
    def configure_run(self, batch_root: Path, batch_id: str) -> None:
        self.evidence_root = batch_root / "http"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.batch_id = batch_id

    def get(self, url: str) -> FetchResponse:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "www.careerlink.vn":
            raise FetchError("CareerLink host scope violation", url=url, attempt=1, blocked=True)
        if not hasattr(self, "evidence_root"):
            raise RuntimeError("configure_run required before HTTP capture")
        self._rate_limit()
        started = self._monotonic()
        requested_at = datetime.now(UTC)
        try:
            response = self._client.get(url, follow_redirects=False)
        except httpx.RequestError as exc:
            self._last_request_at = self._monotonic()
            raise FetchError(f"Network error: {type(exc).__name__}", url=url, attempt=1) from exc
        self._last_request_at = self._monotonic()
        token = requested_at.strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8]
        status = response.status_code
        content_type = response.headers.get("content-type", "")
        is_html = "html" in content_type.casefold() or response.text.lstrip().startswith("<")
        challenge = is_challenge(response.text)
        blocked = status in {401, 403, 429} or challenge
        # Keep errors/challenges inspectable; omit only successful response bodies.
        keep_body = self.config.save_html or status != 200 or blocked
        body_path = self.evidence_root / f"{token}.html.gz" if keep_body else None
        if body_path is not None:
            body_path.write_bytes(gzip.compress(response.content))
        canonical_url = None
        canonical_job_id = None
        if is_html:
            canonical = HTMLParser(response.text).css_first('link[rel="canonical"][href]')
            if canonical is not None:
                canonical_url = canonical.attributes.get("href")
                identity = job_url(canonical_url) if canonical_url else None
                canonical_job_id = identity[0] if identity else None
        requested_identity = job_url(url)
        final_identity = job_url(str(response.url))
        metadata_path = self.evidence_root / f"{token}.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "evidence_schema_version": "2",
                    "batch_id": self.batch_id,
                    "requested_at": requested_at.isoformat(),
                    "requested_url": url,
                    "final_url": str(response.url),
                    "http_status": status,
                    "content_type": content_type,
                    "requested_job_id": requested_identity[0] if requested_identity else None,
                    "final_job_id": final_identity[0] if final_identity else None,
                    "canonical_url": canonical_url,
                    "canonical_job_id": canonical_job_id,
                    "challenge_detected": challenge,
                    "body_bytes": len(response.content),
                    "body_path": body_path.name if body_path is not None else None,
                    "body_sha256": hashlib.sha256(response.content).hexdigest(),
                    "retry_after": response.headers.get("Retry-After"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if blocked:
            self.state.challenge_detected = challenge
        if status != 200 or blocked:
            raise FetchError(
                f"CareerLink HTTP {status}" + (" challenge detected" if challenge else ""),
                url=str(response.url),
                attempt=1,
                status_code=status,
                blocked=blocked,
                artifact_paths=tuple(str(path) for path in (body_path, metadata_path) if path),
            )
        return FetchResponse(
            url=str(response.url),
            text=response.text,
            status_code=status,
            headers=dict(response.headers),
            attempt=1,
            duration_seconds=self._last_request_at - started,
            fetcher="http",
        )
