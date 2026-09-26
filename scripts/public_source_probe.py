"""Evidence capture for explicitly scoped, sequential public-source assessments.

Not a crawler or authorization gate. Callers must review policy/robots first.
Never retries, executes JavaScript, follows cross-origin redirects, or logs cookies.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from selectolax.parser import HTMLParser

USER_AGENT = "job-warehouse-crawler/0.1 (public academic research; single-threaded)"


def capture(root: Path, label: str, url: str, *, delay: float = 4) -> tuple[str, dict]:
    root.mkdir(parents=True, exist_ok=True)
    if (root / f"{label}.json").exists():
        raise ValueError("Evidence already exists; use a new label, do not overwrite")
    time.sleep(delay)
    metadata = {
        "requested_at": datetime.now(UTC).isoformat(),
        "url": url,
        "user_agent": USER_AGENT,
        "redirects": [],
    }
    current = url
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
            for hop in range(6):
                response = client.get(current)
                body = root / f"{label}.hop-{hop}.body.gz"
                body.write_bytes(gzip.compress(response.content))
                metadata.update(
                    status=response.status_code,
                    final_url=str(response.url),
                    body_path=str(body),
                    sha256=hashlib.sha256(response.content).hexdigest(),
                )
                tree = HTMLParser(response.text)
                title = tree.css_first("title")
                heading = title.text().lower() if title else ""
                blocked = (
                    response.status_code in (401, 403, 429)
                    or any(
                        marker in heading
                        for marker in ("just a moment", "access denied", "captcha", "verify you")
                    )
                    or "cf-chl-" in response.text.lower()
                )
                metadata["blocked"] = blocked
                # Persist before deciding whether redirects/content can be followed.
                (root / f"{label}.json").write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2)
                )
                if blocked:
                    raise RuntimeError(f"STOP source: status/challenge at {current}")
                if response.is_redirect:
                    target = urljoin(current, response.headers.get("location", ""))
                    if urlsplit(target).netloc != urlsplit(url).netloc:
                        raise RuntimeError("Cross-origin redirect requires separate policy review")
                    metadata["redirects"].append(
                        {"url": current, "status": response.status_code, "body_path": str(body)}
                    )
                    current = target
                    time.sleep(delay)
                    continue
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}: {current}")
                for node in tree.css("script,style"):
                    node.decompose()
                text = "\n".join(
                    line.strip() for line in tree.text(separator="\n").splitlines() if line.strip()
                )
                (root / f"{label}.txt").write_text(text)
                return response.text, metadata
            raise RuntimeError("Too many redirects")
    except (httpx.HTTPError, RuntimeError) as exc:
        metadata["error"] = str(exc)
        (root / f"{label}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        raise
