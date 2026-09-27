"""Strict HTTP sample: save evidence first, never follow redirects or retry blocks."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from job_crawler.fetchers.base import FetchError, FetchResponse
from job_crawler.fetchers.http import CHALLENGE_MARKERS, HttpFetcher
from job_crawler.parsers.timviec365 import HOST, job_url, listing_url_allowed

ROBOTS = f"https://{HOST}/robots.txt"


def robots_denies(text: str, url: str) -> bool:
    """Conservative extra guard: any matching Disallow stops this source sample.

    This deliberately does not override a Disallow using an Allow or another
    user-agent group. It may over-restrict future rules; it cannot open a denied
    path due to urllib.robotparser's first-match/wildcard limitations.
    """
    parts = urlsplit(url)
    target = parts.path + ("?" + parts.query if parts.query else "")
    for line in text.splitlines():
        key, separator, value = line.split("#", 1)[0].partition(":")
        rule = value.strip()
        if not separator or key.strip().casefold() != "disallow" or not rule:
            continue
        anchor = rule.endswith("$")
        pattern = re.escape(rule[:-1] if anchor else rule).replace(r"\*", ".*")
        if re.match(pattern + ("$" if anchor else ""), target):
            return True
    return False


class Timviec365HttpFetcher(HttpFetcher):
    def configure_run(self, batch_root: Path, _batch_id: str) -> None:
        self.evidence_root = batch_root / "http"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.robots_text: str | None = None
        self.stopped = False

    def get(self, url: str) -> FetchResponse:
        if not hasattr(self, "evidence_root"):
            raise RuntimeError("configure_run required before HTTP capture")
        if self.stopped:
            raise FetchError("Timviec365 already stopped", url=url, attempt=1, blocked=True)
        parts = urlsplit(url)
        in_scope = (
            url == ROBOTS
            or listing_url_allowed(url)
            or (job_url(url) is not None and not parts.query and not parts.fragment)
        )
        if not in_scope or (
            url != ROBOTS and (self.robots_text is None or robots_denies(self.robots_text, url))
        ):
            self.stopped = True
            raise FetchError("Timviec365 scope/robots denied", url=url, attempt=1, blocked=True)
        self._rate_limit()
        started = self._monotonic()
        requested_at = datetime.now(UTC)
        try:
            response = self._client.get(url, follow_redirects=False)
        except httpx.RequestError as exc:
            self.stopped = True
            self._last_request_at = self._monotonic()
            raise FetchError(
                f"Network error: {type(exc).__name__}", url=url, attempt=1, blocked=True
            ) from exc
        self._last_request_at = self._monotonic()
        token = requested_at.strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8]
        body_path = self.evidence_root / f"{token}.body.gz"
        body_path.write_bytes(gzip.compress(response.content))
        meta_path = self.evidence_root / f"{token}.json"
        challenge = any(
            marker in response.text.casefold()
            for marker in (
                *CHALLENGE_MARKERS,
                "just a moment",
                "challenge-platform",
            )
        )
        meta_path.write_text(
            json.dumps(
                {
                    "requested_at": requested_at.isoformat(),
                    "received_at": datetime.now(UTC).isoformat(),
                    "requested_url": url,
                    "final_url": str(response.url),
                    "http_status": response.status_code,
                    "body_path": body_path.name,
                    "body_sha256": hashlib.sha256(response.content).hexdigest(),
                    "retry_after": response.headers.get("Retry-After"),
                    "challenge_detected": challenge,
                    "redirects_followed": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if response.status_code != 200 or challenge:
            self.stopped = True
            self.state.challenge_detected = challenge
            raise FetchError(
                f"Timviec365 stopped: HTTP {response.status_code}; challenge={challenge}",
                url=str(response.url),
                attempt=1,
                status_code=response.status_code,
                blocked=True,
                artifact_paths=(str(body_path), str(meta_path)),
            )
        if url == ROBOTS:
            self.robots_text = response.text
        return FetchResponse(
            url=str(response.url),
            text=response.text,
            status_code=response.status_code,
            headers=dict(response.headers),
            attempt=1,
            duration_seconds=self._last_request_at - started,
            fetcher="http",
        )
