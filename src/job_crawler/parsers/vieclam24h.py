"""Parse the main search results and full detail DOM, never listing previews."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from selectolax.parser import HTMLParser, Node

from job_crawler.models import DiscoveredJob, JobRecord, ListingPage
from job_crawler.utils.hash import job_content_hash, stable_hash

HOST = "vieclam24h.vn"
START_URL = f"https://{HOST}/tim-kiem-viec-lam-nhanh"


def job_url(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    found = re.search(r"-c\d+p\d+id(\d+)\.html$", parts.path)
    if parts.scheme != "https" or parts.netloc != HOST or not found:
        return None
    return found[1], parts._replace(query="", fragment="").geturl()


def listing_url_allowed(url: str) -> bool:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    return (
        parts.scheme == "https"
        and parts.netloc == HOST
        and parts.path == urlsplit(START_URL).path
        and not parts.fragment
        and (
            not parts.query
            or (
                set(query) == {"page"}
                and len(query["page"]) == 1
                and query["page"][0].isdigit()
                and int(query["page"][0]) > 0
            )
        )
    )


def _text(node: Node | None) -> str | None:
    if node is None:
        return None
    return re.sub(r"\s+", " ", node.text(separator=" ", strip=True)).strip() or None


def _props(tree: HTMLParser) -> dict[str, Any]:
    script = tree.css_first("script#__NEXT_DATA__")
    if script is None:
        raise ValueError("Việc Làm 24h embedded page data missing")
    payload = json.loads(script.text())
    props = payload.get("props") if isinstance(payload, dict) else None
    if not isinstance(props, dict):
        raise ValueError("Việc Làm 24h embedded props invalid")
    return props


def section_node(tree: HTMLParser, heading: str) -> Node | None:
    for node in tree.css("main h2"):
        if _text(node) == heading and node.parent is not None:
            return node.parent.css_first(".text-description") or node.next
    return None


def _label(tree: HTMLParser, label: str) -> str | None:
    for node in tree.css("main div"):
        if _text(node) == label and not any(child.tag == "div" for child in node.iter()):
            return _text(node.next)
    return None


def parse_listing(html: str, listing_url: str) -> ListingPage:
    if not listing_url_allowed(listing_url):
        raise ValueError("Việc Làm 24h listing scope mismatch")
    tree = HTMLParser(html)
    response = _props(tree)["initialProps"]["pageProps"]["jobsResponse"]
    items = response["items"]
    expected = {str(item["id"]) for item in items}
    jobs: dict[str, DiscoveredJob] = {}
    for node in tree.css('main a[data-job-id][data-ojb^="0201_"][href]'):
        found = job_url(urljoin(listing_url, node.attributes["href"]))
        if found is None or found[0] != node.attributes["data-job-id"]:
            raise ValueError("Việc Làm 24h main card URL/ID mismatch")
        if found[0] not in expected:
            raise ValueError("Việc Làm 24h card not in main jobsResponse")
        jobs.setdefault(
            found[0],
            DiscoveredJob(
                source_name="vieclam24h",
                source_job_id=found[0],
                source_url=found[1],
                canonical_url=found[1],
                listing_url=listing_url,
            ),
        )
    if set(jobs) != expected or not jobs:
        raise ValueError("Việc Làm 24h main DOM results missing/incomplete")
    current = int(response["current"])
    query_page = int(parse_qs(urlsplit(listing_url).query).get("page", ["1"])[0])
    if current != query_page:
        raise ValueError("Việc Làm 24h requested/result page mismatch")
    next_url = None
    if current < int(response["total_pages"]):
        wanted = f"{START_URL}?page={current + 1}"
        for node in tree.css("main a[href]"):
            if urljoin(listing_url, node.attributes["href"]) == wanted:
                next_url = wanted
                break
        if next_url is None:
            raise ValueError("Việc Làm 24h next page has no public DOM link")
    return ListingPage(
        jobs=list(jobs.values()),
        next_url=next_url,
        source_reported_total=int(response["total_items"]),
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
    parser_version: str = "vieclam24h-1.0.0",
) -> JobRecord:
    tree = HTMLParser(html)
    canonical = tree.css_first('link[rel="canonical"]')
    identity = job_url(canonical.attributes.get("href") or "") if canonical else None
    if identity is None or identity[0] != discovered.source_job_id:
        raise ValueError("Việc Làm 24h canonical job ID missing/mismatched")
    detail = _props(tree)["initialState"]["api"]["jobDetailHiddenContact"]["data"]
    if str(detail.get("id")) != identity[0]:
        raise ValueError("Việc Làm 24h embedded detail ID disagrees with URL")
    title = _text(tree.css_first("main h1"))
    embedded_title = detail.get("title")
    if (
        not title
        or not isinstance(embedded_title, str)
        or title != re.sub(r"\s+", " ", embedded_title).strip()
    ):
        raise ValueError("Việc Làm 24h detail title missing/mismatched")
    posting: dict[str, Any] = {}
    for script in tree.css('script[type="application/ld+json"]'):
        payload = json.loads(script.text())
        if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
            posting = payload
            break
    organization = posting.get("hiringOrganization", {})
    company = organization.get("name") if isinstance(organization, dict) else None
    company_url = organization.get("sameAs") if isinstance(organization, dict) else None
    if company_url and urlsplit(company_url).netloc != HOST:
        company_url = None
    description = _text(section_node(tree, "Mô tả công việc"))
    requirements = _text(section_node(tree, "Yêu cầu công việc"))
    # Compare whole DOM text with the actual job-content fields from THIS detail.
    # resume_requirement_html is application paperwork, NOT candidate requirements.
    for value, field in (
        (description, "description_html"),
        (requirements, "other_requirement_html"),
    ):
        if value and detail.get(field):
            expected = _text(HTMLParser(detail[field]).root)
            if expected != value:
                raise ValueError(f"Việc Làm 24h full content mismatch: {field}")
    benefit = _text(section_node(tree, "Quyền lợi"))
    address = _text(section_node(tree, "Địa điểm làm việc"))
    vacancies = _label(tree, "Số lượng tuyển")
    posted = _label(tree, "Ngày đăng") or posting.get("datePosted")
    record = JobRecord(
        source_name="vieclam24h",
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
        company_name=company,
        company_id=str(detail["employer_id"]) if detail.get("employer_id") else None,
        company_url=company_url,
        job_description=description,
        candidate_requirements=requirements,
        salary_raw=_label(tree, "Mức lương"),
        location_raw=_label(tree, "Khu vực tuyển"),
        detailed_work_address=address,
        benefits=[benefit] if benefit else [],
        experience_raw=_label(tree, "Yêu cầu kinh nghiệm"),
        education_level=_label(tree, "Yêu cầu bằng cấp"),
        job_level=_label(tree, "Cấp bậc"),
        job_type=_label(tree, "Hình thức làm việc"),
        vacancies_raw=vacancies,
        vacancies=int(vacancies) if vacancies and vacancies.isdigit() else None,
        application_deadline_raw=posting.get("validThrough"),
        posted_at_raw=posted,
    )
    record.content_hash = job_content_hash(record.model_dump())
    return record
