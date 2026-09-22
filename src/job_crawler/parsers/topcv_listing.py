from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from job_crawler.models import DiscoveredJob, ListingPage
from job_crawler.utils.hash import stable_hash
from job_crawler.utils.url import canonicalize_url, extract_topcv_job_id


def _json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_objects(child)


def _json_ld_urls(tree: HTMLParser) -> Iterable[str]:
    for node in tree.css("script[type='application/ld+json']"):
        raw = node.text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _json_objects(payload):
            item_type = item.get("@type")
            item_types = item_type if isinstance(item_type, list) else [item_type]
            if any(value in {"JobPosting", "ListItem"} for value in item_types):
                url = item.get("url")
                if isinstance(url, str):
                    yield url
                nested = item.get("item")
                if isinstance(nested, dict) and isinstance(nested.get("url"), str):
                    yield nested["url"]


def _source_total(tree: HTMLParser) -> int | None:
    for selector, attribute in (
        ("[data-total-jobs]", "data-total-jobs"),
        ("[data-total]", "data-total"),
    ):
        node = tree.css_first(selector)
        if node:
            raw = node.attributes.get(attribute) or ""
            digits = re.sub(r"\D", "", raw)
            if digits:
                return int(digits)
    heading = tree.css_first("#search-job-heading") or tree.css_first(".search-job-heading")
    if heading:
        match = re.search(r"([\d.,]+)\s+việc\s+làm", heading.text(separator=" ", strip=True))
        if match:
            digits = re.sub(r"\D", "", match.group(1))
            if digits:
                return int(digits)
    text = tree.body.text(separator=" ", strip=True) if tree.body else tree.text(strip=True)
    for match in re.finditer(r"([\d.,]+)\s+(?:việc\s+làm|jobs?)", text, re.IGNORECASE):
        digits = re.sub(r"\D", "", match.group(1))
        if digits:
            return int(digits)
    return None


def _next_url(tree: HTMLParser, listing_url: str) -> str | None:
    for selector in (
        "a[rel='next']",
        "a[data-testid='pagination-next']",
        "a.pagination-next",
        ".pagination a.next",
    ):
        node = tree.css_first(selector)
        if node:
            href = node.attributes.get("href") or node.attributes.get("data-href")
            if href:
                return canonicalize_url(href, listing_url)
    return None


def parse_listing(html: str, listing_url: str) -> ListingPage:
    tree = HTMLParser(html)
    candidates: list[str] = list(_json_ld_urls(tree))
    root = (
        tree.css_first("[data-testid='job-listing']")
        or tree.css_first("#job-listing")
        or tree.css_first(".job-list-search-result")
        or tree.css_first("main")
    )
    if root:
        for node in root.css("a[href*='/viec-lam/']"):
            href = node.attributes.get("href")
            if href:
                candidates.append(href)

    jobs: list[DiscoveredJob] = []
    seen: set[str] = set()
    for candidate in candidates:
        source_url = urljoin(listing_url, candidate)
        job_id = extract_topcv_job_id(source_url)
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)
        jobs.append(
            DiscoveredJob(
                source_job_id=job_id,
                source_url=source_url,
                canonical_url=canonicalize_url(source_url),
                listing_url=listing_url,
            )
        )

    fingerprint = stable_hash({"job_ids": sorted(seen)})
    return ListingPage(
        jobs=jobs,
        next_url=_next_url(tree, listing_url),
        source_reported_total=_source_total(tree),
        fingerprint=fingerprint,
    )
