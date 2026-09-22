from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from selectolax.parser import HTMLParser, Node

from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.utils.hash import job_content_hash
from job_crawler.utils.time import estimate_relative_posted, parse_source_date
from job_crawler.utils.url import canonicalize_url


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def _plain_html(value: Any) -> str | None:
    if not isinstance(value, str):
        return _clean(value)
    return _clean(HTMLParser(value).text(separator="\n", strip=True))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else re.split(r"[,;|\n]", str(value))
    result: list[str] = []
    for item in values:
        cleaned = _plain_html(item)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _job_posting(tree: HTMLParser) -> dict[str, Any]:
    for node in tree.css("script[type='application/ld+json']"):
        try:
            payload = json.loads(node.text(strip=True))
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _objects(payload):
            item_type = item.get("@type")
            if item_type == "JobPosting" or (
                isinstance(item_type, list) and "JobPosting" in item_type
            ):
                return item
    return {}


def _first_text(tree: HTMLParser, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        node = tree.css_first(selector)
        if node:
            value = _clean(node.text(separator=" ", strip=True))
            if value:
                return value
    return None


def _field_text(tree: HTMLParser, name: str, fallbacks: tuple[str, ...] = ()) -> str | None:
    selectors = (f"[data-field='{name}']", f"[data-testid='{name}']", *fallbacks)
    return _first_text(tree, selectors)


def _normalized_heading(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in value if unicodedata.category(char) != "Mn").replace("đ", "d")


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "job_description": ("mo ta cong viec", "job description"),
    "candidate_requirements": ("yeu cau ung vien", "yeu cau cong viec", "requirements"),
    "income_text": ("thu nhap", "income"),
    "benefits": ("quyen loi", "benefits"),
    "work_address": ("dia diem lam viec", "work address"),
    "working_time": ("thoi gian lam viec", "working time"),
    "application_method": ("cach thuc ung tuyen", "application method"),
}


def _section_node(tree: HTMLParser, name: str) -> Node | None:
    direct = tree.css_first(f"[data-section='{name}']")
    if direct:
        return direct
    aliases = SECTION_ALIASES[name]
    for heading in tree.css("h2, h3, h4, strong"):
        text = _normalized_heading(heading.text(separator=" ", strip=True))
        if any(alias in text for alias in aliases):
            node: Node | None = heading
            while node is not None:
                classes = set((node.attributes.get("class") or "").split())
                if classes.intersection(
                    {
                        "box-job-information-detail-item",
                        "box-job-information-address-and-time-list__item",
                    }
                ):
                    return node
                node = node.parent
            return heading.parent
    return None


def _section_text(tree: HTMLParser, name: str) -> str | None:
    node = _section_node(tree, name)
    if not node:
        return None
    content = node.css_first(
        ".box-job-information-detail-item__text, "
        ".box-job-information-address-and-time-list__item--content"
    )
    text = (content or node).text(separator="\n", strip=True)
    normalized = _normalized_heading(text)
    for alias in SECTION_ALIASES[name]:
        if normalized.startswith(alias):
            first_break = text.find("\n")
            if first_break >= 0:
                text = text[first_break + 1 :]
            break
    return _clean(text)


def _section_list(tree: HTMLParser, name: str) -> list[str]:
    node = _section_node(tree, name)
    if not node:
        return []
    content = node.css_first(
        ".box-job-information-detail-item__text, "
        ".box-job-information-address-and-time-list__item--content"
    )
    items = [
        _clean(item.text(separator=" ", strip=True))
        for item in (content or node).css("li")
        if len(item.css("li")) == 1
    ]
    clean_items = [item for item in items if item]
    if clean_items:
        return list(dict.fromkeys(clean_items))
    text = _section_text(tree, name)
    return _as_list(text)


def _json_salary(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean(value)
    if not isinstance(value, Mapping):
        return None
    nested = value.get("value")
    if isinstance(nested, Mapping):
        minimum = nested.get("minValue")
        maximum = nested.get("maxValue")
        unit = nested.get("unitText") or ""
        currency = value.get("currency") or ""
        values = [part for part in (minimum, maximum) if part is not None]
        if values:
            return _clean(" - ".join(map(str, values)) + f" {currency} {unit}")
    return None


def _json_location(value: Any) -> str | None:
    locations = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for location in locations:
        if not isinstance(location, Mapping):
            continue
        address = location.get("address", location)
        if isinstance(address, Mapping):
            text = ", ".join(
                str(address[key])
                for key in ("streetAddress", "addressLocality", "addressRegion", "addressCountry")
                if address.get(key)
            )
            if text and text not in parts:
                parts.append(text)
    return "; ".join(parts) or None


def _company(posting: Mapping[str, Any]) -> Mapping[str, Any]:
    value = posting.get("hiringOrganization")
    return value if isinstance(value, Mapping) else {}


def _labeled_value(
    tree: HTMLParser,
    *,
    item_selector: str,
    label_selector: str,
    value_selector: str,
    labels: tuple[str, ...],
) -> str | None:
    normalized_labels = {_normalized_heading(label) for label in labels}
    for item in tree.css(item_selector):
        label_node = item.css_first(label_selector)
        value_node = item.css_first(value_selector)
        if not label_node or not value_node:
            continue
        label = _normalized_heading(label_node.text(separator=" ", strip=True)).rstrip(":")
        if label in normalized_labels:
            return _clean(value_node.text(separator=" ", strip=True))
    return None


def _general_info(tree: HTMLParser, *labels: str) -> str | None:
    return _labeled_value(
        tree,
        item_selector=".box-job-information-general-info-list__item",
        label_selector=".box-job-information-general-info-list__item--content-title",
        value_selector=".box-job-information-general-info-list__item--content-desc",
        labels=labels,
    )


def _company_info(tree: HTMLParser, *labels: str) -> str | None:
    return _labeled_value(
        tree,
        item_selector=".box-company-info-detail__list--item",
        label_selector=".box-company-info-detail__list--item-label",
        value_selector=".box-company-info-detail__list--item-value",
        labels=labels,
    )


def _tag_group(tree: HTMLParser, *labels: str) -> list[str]:
    normalized_labels = {_normalized_heading(label) for label in labels}
    for group in tree.css(".job-tags__group"):
        heading = group.css_first(".job-tags__group-name")
        if not heading:
            continue
        label = _normalized_heading(heading.text(separator=" ", strip=True)).rstrip(":")
        if label not in normalized_labels:
            continue
        values = [_clean(node.text(separator=" ", strip=True)) for node in group.css("a.item")]
        return list(dict.fromkeys(value for value in values if value))
    return []


def _category_tags(tree: HTMLParser) -> list[str]:
    container = tree.css_first(".box-job-detail-category .box-category")
    if not container:
        return []
    values = [_clean(node.text(separator=" ", strip=True)) for node in container.css("a")]
    return list(dict.fromkeys(value for value in values if value))


def _company_link(tree: HTMLParser, base_url: str) -> tuple[str | None, str | None]:
    node = tree.css_first(".box-company-info-detail .company-name-label a.name")
    href = node.attributes.get("href") if node else None
    if not href:
        return None, None
    url = canonicalize_url(href, base_url)
    match = re.search(r"/(\d+)\.html$", urlsplit(url).path)
    return url, match.group(1) if match else None


def _json_experience(value: Any) -> str | None:
    if isinstance(value, Mapping):
        months = value.get("monthsOfExperience")
        if months is not None:
            return _clean(f"{months} tháng")
        return None
    return _clean(value)


def _tag_list(tree: HTMLParser, field: str, posting_value: Any = None) -> list[str]:
    node = tree.css_first(f"[data-field='{field}']")
    if node:
        tags = [_clean(tag.text(separator=" ", strip=True)) for tag in node.css(".tag, li, a")]
        clean_tags = [tag for tag in tags if tag]
        if clean_tags:
            return list(dict.fromkeys(clean_tags))
        return _as_list(node.text(separator=",", strip=True))
    return _as_list(posting_value)


def _integer(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"\d+", raw.replace(".", "").replace(",", ""))
    return int(match.group()) if match else None


def parse_detail(
    html: str,
    discovered: DiscoveredJob,
    *,
    crawled_at: datetime,
    snapshot_date: date,
    batch_id: str,
    source_reported_total: int | None,
    raw_html_path: str | None,
    schema_version: str,
    parser_version: str,
) -> JobRecord:
    tree = HTMLParser(html)
    posting = _job_posting(tree)
    company = _company(posting)
    company_page_url, company_page_id = _company_link(tree, discovered.source_url)

    title = _clean(posting.get("title")) or _first_text(
        tree,
        (
            "h1[data-testid='job-title']",
            "h1.box-header-job__title",
            "h1.job-detail__info--title",
            "main h1",
            "h1",
        ),
    )
    salary = _json_salary(posting.get("baseSalary")) or _field_text(
        tree, "salary", (".job-detail__info--section-content-value.salary",)
    )
    location = _json_location(posting.get("jobLocation")) or _field_text(
        tree, "location", (".job-detail__info--section-content-value.location",)
    )
    deadline_raw = _clean(posting.get("validThrough")) or _field_text(
        tree, "application-deadline", (".box-applied-cv .date", ".application-deadline")
    )
    vacancies_raw = _field_text(tree, "vacancies", (".vacancies",)) or _general_info(
        tree, "Số lượng tuyển"
    )
    posted_raw = _clean(posting.get("datePosted")) or _field_text(
        tree, "posted-at", (".posted-at",)
    )
    estimated_posted, precision = estimate_relative_posted(posted_raw, crawled_at)
    if posted_raw and (exact_date := parse_source_date(posted_raw)):
        estimated_posted = datetime.combine(
            exact_date, datetime.min.time(), tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")
        )
        precision = "exact_day"

    benefits = _section_list(tree, "benefits") or _as_list(posting.get("jobBenefits"))
    payload: dict[str, Any] = {
        "source_name": "topcv",
        "source_job_id": discovered.source_job_id,
        "source_url": discovered.source_url,
        "canonical_url": discovered.canonical_url,
        "listing_url": discovered.listing_url,
        "source_reported_total": source_reported_total,
        "crawled_at": crawled_at,
        "snapshot_date": snapshot_date,
        "batch_id": batch_id,
        "schema_version": schema_version,
        "parser_version": parser_version,
        "raw_html_path": raw_html_path,
        "job_title": title,
        "salary_raw": salary,
        "location_raw": location,
        "detailed_work_address": _field_text(tree, "work-address")
        or _section_text(tree, "work_address"),
        "experience_raw": _field_text(tree, "experience")
        or _json_experience(posting.get("experienceRequirements")),
        "application_deadline_raw": deadline_raw,
        "application_deadline": parse_source_date(deadline_raw),
        "job_level": _field_text(tree, "job-level") or _general_info(tree, "Cấp bậc"),
        "education_level": _clean(posting.get("educationRequirements"))
        or _field_text(tree, "education-level")
        or _general_info(tree, "Học vấn"),
        "vacancies_raw": vacancies_raw,
        "vacancies": _integer(vacancies_raw),
        "work_model": _field_text(tree, "work-model") or _general_info(tree, "Hình thức làm việc"),
        "job_type": _clean(posting.get("employmentType"))
        or _field_text(tree, "job-type")
        or _general_info(tree, "Loại hình làm việc"),
        "profession_tags": _tag_list(tree, "profession-tags", posting.get("occupationalCategory")),
        "category_tags": _tag_list(tree, "category-tags") or _category_tags(tree),
        "specialization_tags": _tag_list(tree, "specialization-tags")
        or _tag_group(tree, "Chuyên môn"),
        "requirement_tags": _tag_list(tree, "requirement-tags")
        or _tag_group(tree, "Yêu cầu")
        or _as_list(posting.get("skills")),
        "job_description": _section_text(tree, "job_description")
        or _plain_html(posting.get("description")),
        "candidate_requirements": _section_text(tree, "candidate_requirements")
        or _plain_html(posting.get("qualifications")),
        "income_text": _section_text(tree, "income_text"),
        "benefits": benefits,
        "working_time": _section_text(tree, "working_time"),
        "application_method": _section_text(tree, "application_method"),
        "company_name": _clean(company.get("name"))
        or _field_text(tree, "company-name", (".company-name-label .name",)),
        "company_id": _field_text(tree, "company-id") or company_page_id,
        "company_url": company_page_url
        or (
            canonicalize_url(str(company["sameAs"]), discovered.source_url)
            if company.get("sameAs")
            else None
        ),
        "company_size": _field_text(tree, "company-size") or _company_info(tree, "Quy mô"),
        "company_address": _field_text(tree, "company-address") or _company_info(tree, "Địa điểm"),
        "company_industry": _field_text(tree, "company-industry")
        or _company_info(tree, "Ngành nghề"),
        "posted_at_raw": posted_raw,
        "posted_at_estimated": estimated_posted,
        "posted_date_precision": precision,
    }
    payload["content_hash"] = job_content_hash(payload)
    return JobRecord.model_validate(payload)
