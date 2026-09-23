from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from job_crawler.models import DiscoveredJob, ListingPage
from job_crawler.utils.hash import stable_hash
from job_crawler.utils.url import canonicalize_url, extract_careerviet_job_id


def _source_total(tree: HTMLParser) -> int | None:
    for heading in tree.css("h1, h2"):
        text = heading.text(separator=" ", strip=True)
        match = re.search(r"([\d.,]+)\s+việc\s+làm", text, re.IGNORECASE)
        if match:
            digits = re.sub(r"\D", "", match.group(1))
            if digits:
                return int(digits)
    return None


CAREERVIET_ALL_JOBS_PATH = re.compile(
    r"^(?P<prefix>/viec-lam/tat-ca-viec-lam)(?:-trang-(?P<page>\d+))?-vi\.html$",
    re.IGNORECASE,
)


def _next_url(tree: HTMLParser, listing_url: str) -> str | None:
    for selector in ("a[rel='next']", ".pagination a.next"):
        node = tree.css_first(selector)
        if node and (href := node.attributes.get("href")):
            return canonicalize_url(href, listing_url)

    next_item = tree.css_first(".pagination .next-page")
    if next_item is None:
        return None
    classes = set((next_item.attributes.get("class") or "").split())
    if "disabled" in classes:
        return None

    active = tree.css_first(".pagination li.active")
    active_text = active.text(strip=True) if active else ""
    if not active_text.isdigit():
        return None

    canonical = tree.css_first("link[rel='canonical']")
    current_url = canonical.attributes.get("href") if canonical else listing_url
    parts = urlsplit(urljoin(listing_url, current_url or listing_url))
    match = CAREERVIET_ALL_JOBS_PATH.fullmatch(parts.path)
    if match is None:
        return None
    current_page = int(active_text)
    url_page = int(match.group("page") or "1")
    if current_page != url_page:
        return None
    next_path = f"{match.group('prefix')}-trang-{current_page + 1}-vi.html"
    return canonicalize_url(urlunsplit((parts.scheme, parts.netloc, next_path, "", "")))


def parse_listing(html: str, listing_url: str) -> ListingPage:
    tree = HTMLParser(html)
    candidates: list[str] = []
    for node in tree.css("a.job_link[href], .job-item a[href*='/tim-viec-lam/']"):
        if href := node.attributes.get("href"):
            candidates.append(href)

    jobs: list[DiscoveredJob] = []
    seen: set[str] = set()
    for candidate in candidates:
        source_url = urljoin(listing_url, candidate)
        job_id = extract_careerviet_job_id(source_url)
        if job_id is None or job_id in seen:
            continue
        seen.add(job_id)
        jobs.append(
            DiscoveredJob(
                source_name="careerviet",
                source_job_id=job_id,
                source_url=source_url,
                canonical_url=canonicalize_url(source_url),
                listing_url=listing_url,
            )
        )

    return ListingPage(
        jobs=jobs,
        next_url=_next_url(tree, listing_url),
        source_reported_total=_source_total(tree),
        fingerprint=stable_hash({"job_ids": sorted(seen)}),
    )
