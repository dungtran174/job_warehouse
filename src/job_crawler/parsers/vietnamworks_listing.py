from __future__ import annotations

import json
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from job_crawler.models import DiscoveredJob, ListingPage
from job_crawler.parsers.vietnamworks_detail import job_id_from_url
from job_crawler.utils.hash import stable_hash


def parse_listing(html: str, listing_url: str) -> ListingPage:
    tree = HTMLParser(html)
    jobs: dict[str, DiscoveredJob] = {}
    # Never accept featured/recommended cards outside the primary search results.
    for anchor in tree.css(".block-job-list .search_list a[href]"):
        source_url = urljoin(listing_url, anchor.attributes.get("href") or "")
        job_id = job_id_from_url(source_url)
        if job_id is None or job_id in jobs:
            continue
        parts = urlsplit(source_url)
        canonical = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        jobs[job_id] = DiscoveredJob(
            source_name="vietnamworks",
            source_job_id=job_id,
            source_url=source_url,
            canonical_url=canonical,
            listing_url=listing_url,
        )
    next_url = None
    if jobs:
        active = tree.css_first(".pagination .active")
        if active is None or not active.text(strip=True).isdigit():
            raise ValueError("Primary results found but pagination cannot be verified")
        page = int(active.text(strip=True))
        parts = urlsplit(listing_url)
        if parts.path not in {"/tim-viec-lam/tim-tat-ca-viec-lam", "/viec-lam"}:
            raise ValueError("Unverified search pagination route")
        requested = int(parse_qs(parts.query).get("page", ["1"])[0])
        if requested != page:
            raise ValueError("Requested page differs from active pagination page")
        for button in tree.css(".pagination button"):
            if (
                button.text(strip=True) in {str(page + 1), ">"}
                and "disabled" not in button.attributes
            ):
                parent = button.parent
                if parent and "disabled" not in (parent.attributes.get("class") or ""):
                    # Observed by clicking page 2 in the public UI, not guessed API parameters.
                    next_url = f"https://www.vietnamworks.com/viec-lam?page={page + 1}"
                    break
    total = None
    node = tree.css_first("script#__NEXT_DATA__")
    if node:
        try:
            value = json.loads(node.text())["props"]["pageProps"]["seoSearch"]["jobCounts"]
            if isinstance(value, int):
                total = value
        except (ValueError, KeyError, TypeError):
            pass
    return ListingPage(
        jobs=list(jobs.values()),
        next_url=next_url,
        source_reported_total=total,
        fingerprint=stable_hash({"job_ids": sorted(jobs)}),
    )
