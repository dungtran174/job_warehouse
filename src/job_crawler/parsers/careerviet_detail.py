from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from selectolax.parser import HTMLParser, Node

from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.utils.hash import job_content_hash
from job_crawler.utils.time import parse_source_date
from job_crawler.utils.url import canonicalize_url


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def _plain_html(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean(HTMLParser(value).text(separator="\n", strip=True))
    return _clean(value)


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace(
        "đ", "d"
    )


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
        if node and (text := _clean(node.text(separator=" ", strip=True))):
            return text
    return None


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "benefits": ("phuc loi", "quyen loi", "benefits"),
    "job_description": ("mo ta cong viec", "job description"),
    "candidate_requirements": ("yeu cau cong viec", "yeu cau ung vien", "requirements"),
    "work_address": ("dia diem lam viec", "noi lam viec", "work location"),
}


def _section(tree: HTMLParser, name: str) -> Node | None:
    aliases = SECTION_ALIASES[name]
    for row in tree.css(".detail-row"):
        heading = row.css_first(".detail-title, h2, h3, h4")
        if not heading:
            continue
        normalized = _normalized(heading.text(separator=" ", strip=True)).strip(":")
        if normalized in aliases:
            return row
    return None


def _section_text(tree: HTMLParser, name: str) -> str | None:
    row = _section(tree, name)
    if row is None:
        return None
    content = row.css_first(".content_fck, .detail-content")
    text = _clean((content or row).text(separator="\n", strip=True))
    if content is None and text:
        heading = row.css_first(".detail-title, h2, h3, h4")
        heading_text = _clean(heading.text(separator=" ", strip=True)) if heading else None
        if heading_text and text.startswith(heading_text):
            return _clean(text[len(heading_text) :])
    return text


def _section_list(tree: HTMLParser, name: str) -> list[str]:
    row = _section(tree, name)
    if row is None:
        return []
    content = row.css_first(".content_fck, .detail-content") or row
    items = [_clean(item.text(separator=" ", strip=True)) for item in content.css("li")]
    clean_items = [item for item in items if item]
    if clean_items:
        return list(dict.fromkeys(clean_items))
    text = _section_text(tree, name)
    if not text:
        return []
    return list(
        dict.fromkeys(item for part in re.split(r"[,;|\n]", text) if (item := _clean(part)))
    )


def _labeled_value(tree: HTMLParser, *labels: str) -> str | None:
    wanted = {_normalized(label).rstrip(":") for label in labels}
    for item in tree.css("li"):
        label_node = item.css_first("strong")
        value_node = item.css_first("p")
        if not label_node or not value_node:
            continue
        label = _normalized(label_node.text(separator=" ", strip=True)).rstrip(":")
        if label in wanted:
            return _clean(value_node.text(separator=" ", strip=True))
    return None


def _other_info(tree: HTMLParser, *labels: str) -> str | None:
    wanted = {_normalized(label).rstrip(":") for label in labels}
    row = None
    for candidate in tree.css(".detail-row"):
        heading = candidate.css_first(".detail-title, h2, h3")
        if heading and _normalized(heading.text(strip=True)) == "thong tin khac":
            row = candidate
            break
    if row is None:
        return None
    for item in row.css("li"):
        text = item.text(separator=" ", strip=True)
        normalized = _normalized(text)
        for label in wanted:
            if normalized.startswith(label):
                return _clean(re.sub(r"^[^:]+:\s*", "", text))
    return None


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        if item is None:
            continue
        if isinstance(item, Mapping):
            item = item.get("name") or item.get("description") or item.get("value")
        for part in re.split(r"[,;|\n]", str(item)):
            if (text := _plain_html(part)) and text not in result:
                result.append(text.strip('"'))
    return result


def _structured_text(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key in ("description", "alternateName", "name", "value"):
            if text := _clean(value.get(key)):
                return text
        if value.get("monthsOfExperience") is not None:
            return f"{value['monthsOfExperience']} tháng"
        return None
    if isinstance(value, list):
        values = [text for item in value if (text := _structured_text(item))]
        return ", ".join(dict.fromkeys(values)) or None
    text = _clean(value)
    return text.strip('"') if text else None


def _salary(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean(value)
    if not isinstance(value, Mapping):
        return None
    nested = value.get("value", value)
    if not isinstance(nested, Mapping):
        return None
    if nested.get("value") is not None:
        return _clean(nested["value"])
    minimum = nested.get("minValue")
    maximum = nested.get("maxValue")
    if minimum is None and maximum is None:
        return None
    amount = " - ".join(str(item) for item in (minimum, maximum) if item is not None)
    return _clean(f"{amount} {value.get('currency', '')} {nested.get('unitText', '')}")


def _address(posting: Mapping[str, Any]) -> Mapping[str, Any]:
    location = posting.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else {}
    if not isinstance(location, Mapping):
        return {}
    address = location.get("address", location)
    return address if isinstance(address, Mapping) else {}


def _location(address: Mapping[str, Any]) -> str | None:
    values: list[str] = []
    for key in ("addressLocality", "addressRegion", "addressCountry"):
        if (value := _clean(address.get(key))) and value not in values:
            values.append(value)
    return ", ".join(values) or None


def _company_link(
    tree: HTMLParser, posting: Mapping[str, Any], base_url: str
) -> tuple[str | None, str | None]:
    organization = posting.get("hiringOrganization")
    company = organization if isinstance(organization, Mapping) else {}
    node = tree.css_first("a.job-company-name")
    href = node.attributes.get("href") if node else None
    raw_url = href or company.get("url")
    if not isinstance(raw_url, str) or not raw_url:
        return None, None
    url = canonicalize_url(raw_url, base_url)
    match = re.search(r"\.([0-9a-f]{8,})\.html$", url, re.IGNORECASE)
    return url, match.group(1).upper() if match else None


def _posted(value: str | None) -> tuple[datetime | None, str]:
    if not value:
        return None, "unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = parse_source_date(value)
        if parsed_date is None:
            return None, "unknown"
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC), "exact_day"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed, "exact_day"


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
    organization = posting.get("hiringOrganization")
    company = organization if isinstance(organization, Mapping) else {}
    address = _address(posting)
    company_url, company_id = _company_link(tree, posting, discovered.source_url)
    posted_raw = _clean(posting.get("datePosted")) or _labeled_value(
        tree, "Ngày cập nhật", "Ngày đăng"
    )
    posted_at, posted_precision = _posted(posted_raw)
    deadline_raw = _clean(posting.get("validThrough")) or _labeled_value(
        tree, "Hết hạn nộp", "Hạn nộp"
    )
    vacancies_raw = _structured_text(posting.get("totalJobOpenings")) or _other_info(
        tree, "Số lượng tuyển"
    )
    job_description = _section_text(tree, "job_description") or _plain_html(
        posting.get("description")
    )
    candidate_requirements = _section_text(tree, "candidate_requirements") or _plain_html(
        posting.get("qualifications")
    )
    benefits = _section_list(tree, "benefits") or _string_list(posting.get("jobBenefits"))
    payload: dict[str, Any] = {
        "source_name": "careerviet",
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
        "job_title": _clean(posting.get("title"))
        or _first_text(tree, ("main h1.title", "h1.title", "main h1", "h1")),
        "salary_raw": _salary(posting.get("baseSalary"))
        or _labeled_value(tree, "Lương")
        or _other_info(tree, "Lương"),
        "location_raw": _location(address),
        "detailed_work_address": _clean(address.get("streetAddress"))
        or _section_text(tree, "work_address"),
        "experience_raw": _structured_text(posting.get("experienceRequirements"))
        or _labeled_value(tree, "Kinh nghiệm"),
        "application_deadline_raw": deadline_raw,
        "application_deadline": parse_source_date(deadline_raw),
        "job_level": _structured_text(posting.get("experienceLevel"))
        or _labeled_value(tree, "Cấp bậc"),
        "education_level": _structured_text(posting.get("educationRequirements"))
        or _other_info(tree, "Bằng cấp", "Học vấn"),
        "vacancies_raw": vacancies_raw,
        "vacancies": _integer(vacancies_raw),
        "work_model": _structured_text(posting.get("jobLocationType")),
        "job_type": _structured_text(posting.get("employmentType"))
        or _labeled_value(tree, "Hình thức"),
        "profession_tags": _string_list(posting.get("occupationalCategory")),
        "category_tags": _string_list(posting.get("industry")),
        "specialization_tags": _string_list(posting.get("occupationalCategory")),
        "requirement_tags": _string_list(posting.get("skills")),
        "job_description": job_description,
        "candidate_requirements": candidate_requirements,
        "income_text": _other_info(tree, "Lương"),
        "benefits": benefits,
        "working_time": _clean(posting.get("workHours")) or _other_info(tree, "Thời gian làm việc"),
        "application_method": None,
        "company_name": _clean(company.get("name")) or _first_text(tree, ("a.job-company-name",)),
        "company_id": company_id,
        "company_url": company_url,
        "company_size": None,
        "company_address": _clean(company.get("address")),
        "company_industry": _clean(company.get("industry")),
        "posted_at_raw": posted_raw,
        "posted_at_estimated": posted_at,
        "posted_date_precision": posted_precision,
    }
    payload["content_hash"] = job_content_hash(payload)
    return JobRecord.model_validate(payload)


def _integer(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value.replace(".", "").replace(",", ""))
    return int(match.group()) if match else None
