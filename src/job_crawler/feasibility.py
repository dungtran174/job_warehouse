from __future__ import annotations

import argparse
import gzip
import json
import re
import time
import unicodedata
import urllib.robotparser
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict
from selectolax.parser import HTMLParser

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.base import FetchError, FetchResponse
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.playwright import PlaywrightFetcher
from job_crawler.utils.hash import job_content_hash

MAX_LISTING_PAGES = 1
MAX_DISCOVERED_DETAILS = 10
MAX_DETAIL_ATTEMPTS = 3
PROBE_FIELDS = (
    "source_name",
    "source_job_id",
    "canonical_url",
    "job_title",
    "company_name",
    "salary_raw",
    "location_raw",
    "detailed_work_address",
    "experience_raw",
    "application_deadline",
    "job_level",
    "education_level",
    "vacancies",
    "work_model",
    "job_type",
    "category_tags",
    "specialization_tags",
    "job_description",
    "candidate_requirements",
    "benefits",
    "working_time",
    "application_method",
    "company_size",
    "company_address",
    "company_industry",
)
REQUIRED_DETAIL_FIELDS = (
    "source_job_id",
    "canonical_url",
    "job_title",
    "company_name",
    "job_description",
    "candidate_requirements",
    "crawled_at",
    "content_hash",
)


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    listing_url: str
    allowed_hosts: tuple[str, ...]
    detail_path_markers: tuple[str, ...]
    id_patterns: tuple[str, ...]
    pagination_notes: str


SOURCES: dict[str, SourceDefinition] = {
    "careerviet": SourceDefinition(
        name="careerviet",
        listing_url="https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html",
        allowed_hosts=("careerviet.vn", "www.careerviet.vn"),
        detail_path_markers=("/tim-viec-lam/",),
        id_patterns=(r"\.([0-9A-Fa-f]{6,})\.html$", r"-([0-9A-Fa-f]{6,})\.html$"),
        pagination_notes="Expected numbered listing pages or page query; verify from live HTML.",
    ),
    "jobsgo": SourceDefinition(
        name="jobsgo",
        listing_url="https://jobsgo.vn/viec-lam.html",
        allowed_hosts=("jobsgo.vn", "www.jobsgo.vn"),
        detail_path_markers=("/viec-lam/",),
        id_patterns=(r"-(\d{8,})\.html$",),
        pagination_notes="Expected listing page query and stable numeric ID in detail URL.",
    ),
    "vieclam24h": SourceDefinition(
        name="vieclam24h",
        listing_url="https://vieclam24h.vn/tim-kiem-viec-lam-nhanh",
        allowed_hosts=("vieclam24h.vn", "www.vieclam24h.vn"),
        detail_path_markers=("/viec-lam/",),
        id_patterns=(r"-(\d{5,})\.html$", r"/(\d{5,})\.html$"),
        pagination_notes="Expected numbered public result pages; verify final listing URL live.",
    ),
    "vietnamworks": SourceDefinition(
        name="vietnamworks",
        listing_url="https://www.vietnamworks.com/tim-viec-lam/tim-tat-ca-viec-lam",
        allowed_hosts=("vietnamworks.com", "www.vietnamworks.com"),
        detail_path_markers=("-jv", "-jd"),
        id_patterns=(r"-(\d+)-(?:jv|jd)$",),
        pagination_notes="Expected public search pagination and a stable job identifier.",
    ),
}


class ProbeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_job_id: str
    canonical_url: str
    job_title: str | None = None
    company_name: str | None = None
    salary_raw: str | None = None
    location_raw: str | None = None
    detailed_work_address: str | None = None
    experience_raw: str | None = None
    application_deadline: str | None = None
    job_level: str | None = None
    education_level: str | None = None
    vacancies: int | None = None
    work_model: str | None = None
    job_type: str | None = None
    category_tags: list[str] = []
    specialization_tags: list[str] = []
    job_description: str | None = None
    candidate_requirements: str | None = None
    benefits: list[str] = []
    working_time: str | None = None
    application_method: str | None = None
    company_size: str | None = None
    company_address: str | None = None
    company_industry: str | None = None
    crawled_at: datetime
    content_hash: str


@dataclass(slots=True)
class ProbeReport:
    source: str
    listing_url: str
    started_at: str
    access_basis: str = "source_reference"
    finished_at: str | None = None
    duration_seconds: float | None = None
    status: str = "running"
    robots_url: str | None = None
    robots_status: int | None = None
    robots_allowed: bool | None = None
    http_status_listing: int | None = None
    fetcher_requested: str = "auto"
    fetcher_actual: str | None = None
    final_url: str | None = None
    challenge_detected: bool = False
    challenge_type: str | None = None
    listing_pages_requested: int = 0
    listing_pages_succeeded: int = 0
    detail_urls_discovered: int = 0
    unique_job_ids: int = 0
    detail_attempts: int = 0
    detail_successes: int = 0
    detail_failures: int = 0
    valid_records: int = 0
    field_coverage: dict[str, float] = field(default_factory=dict)
    pagination_detected: bool = False
    incremental_possible: bool = False
    score: float = 0.0
    feasible: bool = False
    stop_reason: str | None = None
    notes: list[str] = field(default_factory=list)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        if isinstance(value, (dict, list)):
            return None
        value = str(value)
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def _plain_html(value: Any) -> str | None:
    if not isinstance(value, str):
        return _clean(value)
    return _clean(HTMLParser(value).text(separator="\n", strip=True))


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").replace("đ", "d")


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


def _canonical_detail_url(url: str, base_url: str) -> str:
    parts = urlsplit(urljoin(base_url, url))
    hostname = (parts.hostname or "").casefold()
    netloc = hostname
    if parts.port and parts.port not in {80, 443}:
        netloc = f"{hostname}:{parts.port}"
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold() or "https", netloc, path, "", ""))


def extract_source_job_id(source: SourceDefinition, url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").casefold() not in source.allowed_hosts:
        return None
    if not any(marker in parts.path.casefold() for marker in source.detail_path_markers):
        return None
    for pattern in source.id_patterns:
        if match := re.search(pattern, parts.path, flags=re.IGNORECASE):
            return match.group(1)
    return None


def discover_details(
    html: str, base_url: str, source: SourceDefinition, *, limit: int = MAX_DISCOVERED_DETAILS
) -> list[tuple[str, str]]:
    tree = HTMLParser(html)
    candidates: list[str] = []
    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if href:
            candidates.append(href)
    for node in tree.css("script[type='application/ld+json']"):
        try:
            payload = json.loads(node.text(strip=True))
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _objects(payload):
            for key in ("url", "sameAs"):
                if isinstance(item.get(key), str):
                    candidates.append(item[key])

    found: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        canonical = _canonical_detail_url(candidate, base_url)
        job_id = extract_source_job_id(source, canonical)
        if job_id is None or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        found.append((job_id, canonical))
        if len(found) >= min(limit, MAX_DISCOVERED_DETAILS):
            break
    return found


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "job_description": ("mo ta cong viec", "job description", "description"),
    "candidate_requirements": (
        "yeu cau cong viec",
        "yeu cau ung vien",
        "job requirements",
        "requirements",
        "qualifications",
    ),
    "benefits": ("quyen loi", "phuc loi", "benefits", "what we offer"),
    "working_time": ("thoi gian lam viec", "working time", "working hours"),
    "application_method": ("cach thuc ung tuyen", "how to apply", "application method"),
}
ALL_SECTION_HEADINGS = tuple(alias for aliases in SECTION_ALIASES.values() for alias in aliases)


def _section_text(text: str, name: str) -> str | None:
    lines = [_clean(line) for line in text.splitlines()]
    clean_lines = [line for line in lines if line]
    start: int | None = None
    for index, line in enumerate(clean_lines):
        normalized = _normalized(line).strip(":")
        if any(
            alias == normalized or normalized.startswith(f"{alias}:")
            for alias in SECTION_ALIASES[name]
        ):
            start = index + 1
            break
    if start is None:
        return None
    selected: list[str] = []
    for line in clean_lines[start:]:
        normalized = _normalized(line).strip(":")
        if any(
            alias == normalized or normalized.startswith(f"{alias}:")
            for alias in ALL_SECTION_HEADINGS
        ):
            break
        selected.append(line)
        if sum(map(len, selected)) >= 5000:
            break
    return _clean("\n".join(selected))


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        if isinstance(item, Mapping):
            item = item.get("name") or item.get("value")
        for part in re.split(r"[;|\n]", str(item)) if item is not None else []:
            if (cleaned := _plain_html(part)) and cleaned not in result:
                result.append(cleaned)
    return result


def _structured_text(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key in ("description", "alternateName", "name", "value"):
            if text := _clean(value.get(key)):
                return text
        if value.get("monthsOfExperience") is not None:
            return f"{value['monthsOfExperience']} months"
        return None
    if isinstance(value, list):
        values = [text for item in value if (text := _structured_text(item))]
        return ", ".join(dict.fromkeys(values)) or None
    return _clean(value)


def _salary(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean(value)
    if not isinstance(value, Mapping):
        return None
    nested = value.get("value", value)
    if not isinstance(nested, Mapping):
        return None
    minimum = nested.get("minValue")
    maximum = nested.get("maxValue")
    unit = nested.get("unitText") or ""
    currency = value.get("currency") or ""
    values = [part for part in (minimum, maximum) if part is not None]
    return _clean(" - ".join(map(str, values)) + f" {currency} {unit}") if values else None


def _location(value: Any) -> str | None:
    locations = value if isinstance(value, list) else [value]
    result: list[str] = []
    for location in locations:
        if not isinstance(location, Mapping):
            continue
        address = location.get("address", location)
        if not isinstance(address, Mapping):
            continue
        parts = [
            _clean(address.get(key))
            for key in ("streetAddress", "addressLocality", "addressRegion", "addressCountry")
        ]
        if (text := ", ".join(part for part in parts if part)) and text not in result:
            result.append(text)
    return "; ".join(result) or None


def _first_text(tree: HTMLParser, selectors: Sequence[str]) -> str | None:
    for selector in selectors:
        if (node := tree.css_first(selector)) and (
            value := _clean(node.text(separator=" ", strip=True))
        ):
            return value
    return None


def _integer(value: Any) -> int | None:
    text = _clean(value)
    if not text or not (match := re.search(r"\d+", text.replace(".", ""))):
        return None
    return int(match.group())


def parse_probe_detail(
    html: str,
    *,
    source_name: str,
    source_job_id: str,
    canonical_url: str,
    crawled_at: datetime | None = None,
) -> ProbeRecord:
    tree = HTMLParser(html)
    posting = _job_posting(tree)
    organization = posting.get("hiringOrganization")
    company = organization if isinstance(organization, Mapping) else {}
    page_text = tree.text(separator="\n", strip=True)
    description_html = posting.get("description")
    description_text = _plain_html(description_html)
    description_sections = (
        HTMLParser(description_html).text(separator="\n", strip=True)
        if isinstance(description_html, str)
        else ""
    )

    title = _clean(posting.get("title")) or _first_text(tree, ("main h1", "h1"))
    company_name = _clean(company.get("name")) or _first_text(
        tree,
        (
            "[data-testid*='company']",
            "[class*='company-name']",
            "[class*='company_name']",
        ),
    )
    job_description = _section_text(description_sections, "job_description") or description_text
    candidate_requirements = (
        _plain_html(posting.get("qualifications"))
        or _section_text(description_sections, "candidate_requirements")
        or _section_text(page_text, "candidate_requirements")
    )
    benefits_text = (
        _plain_html(posting.get("jobBenefits"))
        or _section_text(description_sections, "benefits")
        or _section_text(page_text, "benefits")
    )
    payload: dict[str, Any] = {
        "source_name": source_name,
        "source_job_id": source_job_id,
        "canonical_url": canonical_url,
        "job_title": title,
        "company_name": company_name,
        "salary_raw": _salary(posting.get("baseSalary")),
        "location_raw": _location(posting.get("jobLocation")),
        "detailed_work_address": _first_text(
            tree, ("[data-field='work-address']", "[class*='work-address']")
        ),
        "experience_raw": _structured_text(posting.get("experienceRequirements")),
        "application_deadline": _clean(posting.get("validThrough")),
        "job_level": _structured_text(posting.get("experienceLevel")),
        "education_level": _structured_text(posting.get("educationRequirements")),
        "vacancies": _integer(posting.get("totalJobOpenings")),
        "work_model": _structured_text(posting.get("jobLocationType")),
        "job_type": _structured_text(posting.get("employmentType")),
        "category_tags": _string_list(posting.get("industry")),
        "specialization_tags": _string_list(posting.get("occupationalCategory")),
        "job_description": job_description,
        "candidate_requirements": candidate_requirements,
        "benefits": _string_list(benefits_text),
        "working_time": _section_text(page_text, "working_time"),
        "application_method": _section_text(page_text, "application_method"),
        "company_size": _first_text(
            tree, ("[data-field='company-size']", "[class*='company-size']")
        ),
        "company_address": _clean(company.get("address"))
        or _first_text(tree, ("[data-field='company-address']", "[class*='company-address']")),
        "company_industry": _first_text(
            tree, ("[data-field='company-industry']", "[class*='company-industry']")
        ),
        "crawled_at": crawled_at or datetime.now(UTC),
    }
    payload["content_hash"] = job_content_hash(payload)
    return ProbeRecord.model_validate(payload)


def missing_required(record: ProbeRecord) -> list[str]:
    return [field for field in REQUIRED_DETAIL_FIELDS if not getattr(record, field)]


def field_coverage(records: Sequence[ProbeRecord]) -> dict[str, float]:
    if not records:
        return {name: 0.0 for name in PROBE_FIELDS}
    return {
        name: round(
            100
            * sum(getattr(record, name) not in (None, "", []) for record in records)
            / len(records),
            2,
        )
        for name in PROBE_FIELDS
    }


def feasibility_score(report: ProbeReport) -> float:
    listing = 30.0 if report.listing_pages_succeeded and report.unique_job_ids else 0.0
    details = 30.0 * min(report.detail_successes / MAX_DETAIL_ATTEMPTS, 1.0)
    completeness = 25.0 * (
        sum(report.field_coverage.values()) / (100 * len(PROBE_FIELDS))
        if report.field_coverage
        else 0.0
    )
    pagination = 10.0 if report.pagination_detected else 0.0
    stable_ids = 5.0 if report.incremental_possible and report.unique_job_ids else 0.0
    return round(listing + details + completeness + pagination + stable_ids, 2)


def pagination_detected(html: str, base_url: str) -> bool:
    tree = HTMLParser(html)
    if tree.css_first("link[rel='next'], a[rel='next']"):
        return True
    pagination = tree.css_first(".pagination, [class*='pagination']")
    if pagination and (
        pagination.css_first(".next-page, [class*='next']") or len(pagination.css("a, button")) >= 2
    ):
        return True
    for node in tree.css("a[href]"):
        href = urljoin(base_url, node.attributes.get("href") or "")
        if re.search(r"(?:[?&](?:page|p)=\d+|/page[-/]?\d+)", href, re.IGNORECASE):
            return True
    return False


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.replace(path)


def _append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")))
        handle.write("\n")


def _save_html(root: Path, name: str, html: str) -> str:
    destination = root / "html" / f"{name}.html.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destination, "wt", encoding="utf-8") as handle:
        handle.write(html)
    return str(destination.relative_to(root))


def _error(
    root: Path,
    *,
    stage: str,
    url: str,
    message: str,
    status: int | None = None,
    job_id: str | None = None,
    challenge_type: str | None = None,
) -> None:
    _append_jsonl(
        root / "errors.jsonl",
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "stage": stage,
            "url": url,
            "job_id": job_id,
            "http_status": status,
            "challenge_type": challenge_type,
            "message": message,
        },
    )


def _probe_config(
    *,
    source_name: str,
    authorization_reference: str | None,
    project_owner_public_test: bool,
    fetcher: Literal["http", "playwright", "auto"],
    headed: bool,
    save_html: bool,
    save_screenshot_on_error: bool,
) -> CrawlConfig:
    return CrawlConfig(
        source=source_name,
        fetcher=fetcher,
        authorization_reference=authorization_reference,
        project_owner_public_test=project_owner_public_test,
        user_agent="job-warehouse-feasibility/0.1 (public-research)",
        delay_min_seconds=1.5,
        delay_max_seconds=3.0,
        max_retries=0,
        headed=headed,
        save_html=save_html,
        save_screenshot_on_error=save_screenshot_on_error,
    )


def run_probe(
    source_name: str,
    *,
    authorization_reference: str | None = None,
    project_owner_public_test: bool = False,
    output_dir: Path = Path("data/diagnostics/source_feasibility"),
    max_listing_pages: int = MAX_LISTING_PAGES,
    max_details: int = MAX_DETAIL_ATTEMPTS,
    fetcher_mode: Literal["http", "playwright", "auto"] = "auto",
    headed: bool = False,
    save_html: bool = False,
    save_screenshot_on_error: bool = False,
) -> tuple[ProbeReport, Path]:
    if source_name not in SOURCES:
        raise ValueError(f"Unsupported source: {source_name}")
    if max_listing_pages != MAX_LISTING_PAGES:
        raise ValueError("Feasibility probe is locked to exactly one listing page.")
    if not 1 <= max_details <= MAX_DETAIL_ATTEMPTS:
        raise ValueError("Feasibility probe permits between one and three details.")
    if project_owner_public_test and authorization_reference is not None:
        raise ValueError("Choose one access basis, not both.")
    if not project_owner_public_test and (
        not authorization_reference or not authorization_reference.strip()
    ):
        raise ValueError(
            "Choose an access basis: a genuine source --authorization-reference or "
            "--project-owner-public-test for a bounded public probe."
        )
    if project_owner_public_test and fetcher_mode == "playwright":
        raise ValueError("Project-owner public probe must start with HTTP or auto.")

    source = SOURCES[source_name]
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ")
    root = output_dir / source.name / run_id
    (root / "html").mkdir(parents=True)
    (root / "screenshots").mkdir(parents=True)
    (root / "sample_records.jsonl").touch()
    (root / "errors.jsonl").touch()
    report = ProbeReport(
        source=source.name,
        listing_url=source.listing_url,
        started_at=started.isoformat(),
        access_basis="project_owner_public_test"
        if project_owner_public_test
        else "source_reference",
        fetcher_requested=fetcher_mode,
        listing_pages_requested=1,
    )
    config = _probe_config(
        source_name=source_name,
        authorization_reference=authorization_reference.strip()
        if authorization_reference
        else None,
        project_owner_public_test=project_owner_public_test,
        fetcher=fetcher_mode,
        headed=headed,
        save_html=save_html,
        save_screenshot_on_error=save_screenshot_on_error,
    )
    http = HttpFetcher(config)
    browser: PlaywrightFetcher | None = None
    records: list[ProbeRecord] = []
    started_monotonic = time.monotonic()

    def finish(status: str, reason: str) -> tuple[ProbeReport, Path]:
        finished = datetime.now(UTC)
        report.status = status
        report.stop_reason = reason
        report.finished_at = finished.isoformat()
        report.duration_seconds = round(time.monotonic() - started_monotonic, 3)
        report.field_coverage = field_coverage(records)
        report.valid_records = len(records)
        report.feasible = (
            report.unique_job_ids >= 1
            and report.detail_successes >= 2
            and report.valid_records >= 2
            and report.pagination_detected
            and not report.challenge_detected
        )
        report.score = feasibility_score(report)
        _write_json(root / "report.json", asdict(report))
        return report, root

    try:
        robots_url = urlunsplit(
            (
                urlsplit(source.listing_url).scheme,
                urlsplit(source.listing_url).netloc,
                "/robots.txt",
                "",
                "",
            )
        )
        report.robots_url = robots_url
        try:
            robots_response = http.get(robots_url)
            report.robots_status = robots_response.status_code
        except FetchError as exc:
            report.robots_status = exc.status_code
            _error(
                root,
                stage="robots",
                url=exc.url,
                message=str(exc),
                status=exc.status_code,
            )
            return finish("stopped", "robots_unavailable")
        robots = urllib.robotparser.RobotFileParser()
        robots.set_url(robots_url)
        robots.parse(robots_response.text.splitlines())
        report.robots_allowed = robots.can_fetch(config.user_agent, source.listing_url)
        if not report.robots_allowed:
            return finish("stopped", "robots_denied")

        listing_response: FetchResponse | None = None
        details: list[tuple[str, str]] = []
        if fetcher_mode in {"http", "auto"}:
            try:
                listing_response = http.get(source.listing_url)
                report.http_status_listing = listing_response.status_code
                report.fetcher_actual = "http"
                details = discover_details(listing_response.text, listing_response.url, source)
            except FetchError as exc:
                report.http_status_listing = exc.status_code
                _error(
                    root,
                    stage="listing_http",
                    url=exc.url,
                    message=str(exc),
                    status=exc.status_code,
                )
                return finish("stopped", "access_blocked" if exc.blocked else "listing_http_failed")

        should_use_browser = fetcher_mode == "playwright" or (
            fetcher_mode == "auto" and not details
        )
        if should_use_browser:
            if report.http_status_listing == 200 and not details:
                report.notes.append("HTTP HTML contained no recognized public detail URLs.")
            browser = PlaywrightFetcher(config)
            browser.configure_run(root, run_id)
            try:
                listing_response = browser.get(source.listing_url)
            except FetchError as exc:
                report.fetcher_actual = "playwright"
                report.challenge_detected = exc.blocked
                report.challenge_type = exc.challenge_type
                _error(
                    root,
                    stage="listing_browser",
                    url=exc.url,
                    message=f"{exc}; artifacts={list(exc.artifact_paths)}",
                    status=exc.status_code,
                    challenge_type=exc.challenge_type,
                )
                reason = "access_blocked" if exc.blocked else "listing_browser_failed"
                return finish("stopped", reason)
            report.fetcher_actual = "playwright"
            details = discover_details(listing_response.text, listing_response.url, source)

        if listing_response is None:
            return finish("failed", "listing_not_attempted")
        report.final_url = listing_response.url
        if save_html:
            _save_html(root, "listing-001", listing_response.text)
        report.pagination_detected = pagination_detected(
            listing_response.text, listing_response.url
        )
        report.detail_urls_discovered = len(details)
        report.unique_job_ids = len({job_id for job_id, _ in details})
        report.incremental_possible = report.unique_job_ids > 0
        report.notes.append(source.pagination_notes)
        if not details:
            _error(
                root,
                stage="listing_parse",
                url=listing_response.url,
                message="No recognized stable job ID/detail URL found.",
                status=listing_response.status_code,
            )
            return finish("failed", "no_detail_urls")
        report.listing_pages_succeeded = 1

        active_fetcher: HttpFetcher | PlaywrightFetcher
        if report.fetcher_actual == "playwright":
            if browser is None:
                raise AssertionError("browser fetcher missing")
            active_fetcher = browser
        else:
            active_fetcher = http

        for job_id, detail_url in details[:max_details]:
            if not robots.can_fetch(config.user_agent, detail_url):
                _error(
                    root,
                    stage="detail_robots",
                    url=detail_url,
                    job_id=job_id,
                    message="robots.txt does not permit this detail URL.",
                )
                return finish("stopped", "detail_robots_denied")
            report.detail_attempts += 1
            try:
                response = active_fetcher.get(detail_url)
            except FetchError as exc:
                report.detail_failures += 1
                report.challenge_detected = exc.blocked
                report.challenge_type = exc.challenge_type
                _error(
                    root,
                    stage="detail",
                    url=exc.url,
                    job_id=job_id,
                    message=f"{exc}; artifacts={list(exc.artifact_paths)}",
                    status=exc.status_code,
                    challenge_type=exc.challenge_type,
                )
                if exc.blocked:
                    return finish("stopped", "access_blocked")
                continue
            if save_html:
                _save_html(root, f"detail-{job_id}", response.text)
            record = parse_probe_detail(
                response.text,
                source_name=source.name,
                source_job_id=job_id,
                canonical_url=detail_url,
            )
            if missing := missing_required(record):
                report.detail_failures += 1
                _error(
                    root,
                    stage="detail_validation",
                    url=detail_url,
                    job_id=job_id,
                    message=f"Missing feasibility-required fields: {', '.join(missing)}",
                    status=response.status_code,
                )
                continue
            records.append(record)
            report.detail_successes += 1
            _append_jsonl(root / "sample_records.jsonl", record.model_dump(mode="json"))

        status = "completed" if report.detail_failures == 0 else "completed_with_errors"
        return finish(status, "probe_limit_reached")
    finally:
        http.close()
        if browser is not None:
            browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded public job-source feasibility probe")
    parser.add_argument("--source", choices=tuple(SOURCES), required=True)
    parser.add_argument("--max-listing-pages", type=int, default=1)
    parser.add_argument("--max-details", type=int, default=3)
    parser.add_argument("--fetcher", choices=("http", "playwright", "auto"), default="auto")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--save-html", action="store_true")
    parser.add_argument("--save-screenshot-on-error", action="store_true")
    parser.add_argument(
        "--authorization-reference",
        help="Non-secret reference to genuine written source authorization, if available.",
    )
    parser.add_argument(
        "--project-owner-public-test",
        action="store_true",
        help="Owner-directed public probe only; not source authorization.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/diagnostics/source_feasibility")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, root = run_probe(
            args.source,
            output_dir=args.output_dir,
            authorization_reference=args.authorization_reference,
            project_owner_public_test=args.project_owner_public_test,
            max_listing_pages=args.max_listing_pages,
            max_details=args.max_details,
            fetcher_mode=args.fetcher,
            headed=args.headed,
            save_html=args.save_html,
            save_screenshot_on_error=args.save_screenshot_on_error,
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2
    print(json.dumps({"output": str(root), **asdict(report)}, ensure_ascii=False, indent=2))
    return 0 if report.status in {"completed", "completed_with_errors"} else 2
