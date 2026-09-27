"""Parse only main results and the job's own server-rendered detail sections."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser, Node

from job_crawler.models import DiscoveredJob, JobRecord, ListingPage
from job_crawler.utils.hash import job_content_hash, stable_hash

HOST = "timviec365.vn"
START = f"https://{HOST}/viec-lam"
MAIN_RESULTS = ".boxContentListNew .boxShowListNew > .item_vl"


def job_url(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    match = re.fullmatch(r"/[^/]+-p(\d+)\.html", parts.path)
    if parts.scheme != "https" or parts.netloc != HOST or not match:
        return None
    return match[1], urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def listing_url_allowed(url: str) -> bool:
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    return (
        parts.scheme == "https"
        and parts.netloc == HOST
        and parts.path == "/viec-lam"
        and not parts.fragment
        and (
            not parts.query
            or (
                set(query) == {"page"}
                and len(query["page"]) == 1
                and re.fullmatch(r"[1-9]\d*", query["page"][0]) is not None
            )
        )
    )


def _text(node: Node | None) -> str | None:
    if node is None:
        return None
    return re.sub(r"\s+", " ", node.text(separator=" ", strip=True)).strip() or None


def parse_listing(html: str, listing_url: str) -> ListingPage:
    if not listing_url_allowed(listing_url):
        raise ValueError("Unexpected Timviec365 listing URL")
    tree = HTMLParser(html)
    jobs: dict[str, DiscoveredJob] = {}
    for card in tree.css(MAIN_RESULTS):
        # Advertisements outside the results and pinned cards are not discovery evidence.
        if card.attributes.get("data-newghim", "0") != "0":
            continue
        anchor = card.css_first("h2.box_title_new a.title_new[href]")
        found = job_url(urljoin(listing_url, anchor.attributes["href"])) if anchor else None
        if not found:
            continue
        job_id, canonical = found
        if card.attributes.get("data-newid") != job_id:
            raise ValueError("Timviec365 listing ID mismatch")
        jobs.setdefault(
            job_id,
            DiscoveredJob(
                source_name="timviec365",
                source_job_id=job_id,
                source_url=canonical,
                canonical_url=canonical,
                listing_url=listing_url,
            ),
        )
    # Both arrows use pagi_pre on page >= 2. Select the forward arrow, not the first.
    arrows = [n for n in tree.css(".pagination .pagi_pre a[href]") if n.text(strip=True) == ">"]
    if len(arrows) > 1:
        raise ValueError("Ambiguous Timviec365 next-page arrows")
    next_node = arrows[0] if arrows else None
    next_url = urljoin(listing_url, next_node.attributes["href"]) if next_node else None
    if next_url:
        current = int(parse_qs(urlsplit(listing_url).query).get("page", ["1"])[0])
        if not listing_url_allowed(next_url):
            raise ValueError("Unexpected Timviec365 pagination URL")
        upcoming = int(parse_qs(urlsplit(next_url).query).get("page", ["1"])[0])
        if upcoming != current + 1:
            raise ValueError("Non-sequential Timviec365 pagination")
    return ListingPage(
        jobs=list(jobs.values()), next_url=next_url, fingerprint=stable_hash({"ids": sorted(jobs)})
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
    parser_version: str = "timviec365-1.0.0",
) -> JobRecord:
    tree = HTMLParser(html)
    canonical = tree.css_first('link[rel="canonical"]')
    identity = job_url(canonical.attributes.get("href") or "") if canonical else None
    title_node = tree.css_first(".boxDetailInfo h1.titleNew[data-id]")
    title = _text(title_node)
    if (
        identity is None
        or identity[0] != discovered.source_job_id
        or title_node is None
        or title_node.attributes["data-id"] != identity[0]
        or not title
    ):
        raise ValueError("Timviec365 detail ID/title missing or mismatched")
    sections: dict[str, Node] = {}
    for item in tree.css(".itemInfoSpecific"):
        heading = _text(item.css_first("h2.titleInfoSpecific"))
        body = item.css_first(".boxMainInfoSpecific")
        if heading and body is not None:
            if heading in sections:
                raise ValueError("Ambiguous duplicate Timviec365 detail section")
            sections[heading] = body
    facts: dict[str, str | None] = {}
    for item in tree.css(".boxDetailInfo .itemDetailInfo_center"):
        label = _text(item.css_first(".titleContentSalary"))
        if label:
            facts[label] = _text(item.css_first(".valContentSalary"))
    for item in tree.css(".itemYauCauKhac"):
        label = _text(item.css_first(".titleYauCauKhac"))
        if label:
            facts.setdefault(label, _text(item.css_first(".valYauCauKhac")))
    address = sections.get("Địa điểm làm việc")
    requirements = sections.get("Yêu cầu")
    company = tree.css_first(".boxTitleNameNtd a.linkNtd")
    company_url = urljoin(identity[1], company.attributes.get("href") or "") if company else None
    record = JobRecord(
        source_name="timviec365",
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
        company_name=_text(company),
        company_url=company_url,
        job_description=_text(sections.get("Mô tả công việc")),
        candidate_requirements=_text(requirements),
        requirement_tags=[text for n in requirements.css(".itemYeuCau") if (text := _text(n))]
        if requirements
        else [],
        salary_raw=facts.get("Mức lương"),
        location_raw=facts.get("Địa điểm"),
        detailed_work_address=_text(address.css_first(".valDetailAddr")) if address else None,
        experience_raw=facts.get("Kinh nghiệm"),
        education_level=facts.get("Bằng cấp"),
        job_level=facts.get("Chức vụ"),
        vacancies_raw=facts.get("Số lượng cần tuyển"),
        job_type=facts.get("Hình thức làm việc"),
        application_deadline_raw=facts.get("Hạn nộp"),
        benefits=[text] if (text := _text(sections.get("Quyền lợi"))) else [],
        working_time=_text(sections.get("Thời gian làm việc")),
        # The observed timeUpdate field says "Cập nhật", not "Ngày đăng".
        # Do not invent a posting date or populate it from the listing.
        posted_at_raw=None,
    )
    record.content_hash = job_content_hash(record.model_dump())
    return record
