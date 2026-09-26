"""HTTP-only CareerLink parsers; never use listing fields as detail content."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from job_crawler.models import DiscoveredJob, JobRecord, ListingPage
from job_crawler.utils.hash import job_content_hash, stable_hash


def job_url(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    match = re.fullmatch(r"/tim-viec-lam/[^/]+/(\d+)/?", parts.path)
    if parts.scheme != "https" or parts.netloc != "www.careerlink.vn" or not match:
        return None
    return match[1], urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def _text(tree: HTMLParser, selector: str) -> str | None:
    nodes = tree.css(selector)
    text = " ".join(node.text(separator=" ", strip=True) for node in nodes)
    return re.sub(r"\s+", " ", text).strip() or None


def parse_listing(html: str, listing_url: str) -> ListingPage:
    tree = HTMLParser(html)
    jobs: dict[str, DiscoveredJob] = {}
    # Search-result cards only; exclude featured/recommended/company-side cards.
    for node in tree.css("ul.list-group > li.job-item a.job-link[href]"):
        found = job_url(urljoin(listing_url, node.attributes["href"]))
        if found is None:
            continue
        job_id, canonical = found
        jobs.setdefault(
            job_id,
            DiscoveredJob(
                source_name="careerlink",
                source_job_id=job_id,
                source_url=canonical,
                canonical_url=canonical,
                listing_url=listing_url,
            ),
        )
    next_node = tree.css_first(".pagination a[rel=next][href]")
    next_url = urljoin(listing_url, next_node.attributes["href"]) if next_node else None
    if next_url:
        parts = urlsplit(next_url)
        if (
            parts.scheme != "https"
            or parts.netloc != "www.careerlink.vn"
            or parts.path not in {"/vieclam/list", "/vieclam/tim-kiem-viec-lam"}
        ):
            raise ValueError("Unexpected CareerLink pagination URL")
    total_match = re.search(r"([\d.,]+)\s+việc làm", tree.text(separator=" "))
    total = int(re.sub(r"\D", "", total_match[1])) if total_match else None
    return ListingPage(
        jobs=list(jobs.values()),
        next_url=next_url,
        source_reported_total=total,
        fingerprint=stable_hash({"ids": sorted(jobs)}),
    )


def parse_detail(
    html: str,
    discovered: DiscoveredJob,
    *,
    crawled_at: datetime,
    snapshot_date: date,
    batch_id: str,
    source_reported_total: int | None,
    raw_html_path: str | None,
    schema_version: str = "1.0.0",
    parser_version: str = "careerlink-1.0.2",
) -> JobRecord:
    tree = HTMLParser(html)
    canonical_node = tree.css_first('link[rel="canonical"]')
    identity = job_url(canonical_node.attributes.get("href") or "") if canonical_node else None
    if identity is None or identity[0] != discovered.source_job_id:
        raise ValueError("CareerLink detail canonical ID missing or mismatched")
    title = _text(tree, "h1#job-title")
    if not title:
        raise ValueError("CareerLink detail title missing")
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.text())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
            identifier = payload.get("identifier", {})
            if (
                isinstance(identifier, dict)
                and identifier.get("value") is not None
                and str(identifier["value"]) != identity[0]
            ):
                raise ValueError("CareerLink JSON-LD ID disagrees with canonical")
    posted = _text(tree, "#job-date .date-from")
    if posted:
        posted = posted.removeprefix("Ngày đăng tuyển").strip() or None
    record = JobRecord(
        source_name="careerlink",
        source_job_id=identity[0],
        source_url=discovered.source_url,
        canonical_url=identity[1],
        listing_url=discovered.listing_url,
        source_reported_total=source_reported_total,
        crawled_at=crawled_at,
        snapshot_date=snapshot_date,
        batch_id=batch_id,
        schema_version=schema_version,
        parser_version=parser_version,
        raw_html_path=raw_html_path,
        content_hash="",
        job_title=title,
        company_name=_text(tree, ".job-detail-header .org-name"),
        job_description=_text(tree, "#section-job-description .rich-text-content"),
        candidate_requirements=_text(tree, "#section-job-skills .rich-text-content"),
        salary_raw=_text(tree, "#job-salary .text-primary"),
        location_raw=_text(tree, "#job-location") or _text(tree, "#job-offices"),
        detailed_work_address=_text(tree, "#job-offices"),
        posted_at_raw=posted,
    )
    record.content_hash = job_content_hash(record.model_dump())
    return record
