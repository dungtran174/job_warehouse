from __future__ import annotations

import json
import re
from contextlib import suppress
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.utils.hash import job_content_hash


def job_id_from_url(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or parts.hostname not in {
        "www.vietnamworks.com",
        "vietnamworks.com",
    }:
        return None
    match = re.search(r"-(\d+)-(?:jv|jd)$", parts.path)
    return match[1] if match else None


def flight_rows(html: str) -> dict[str, Any]:
    """Decode inline React Flight data only; never execute JS or call an API."""
    chunks = []
    for node in HTMLParser(html).css("script"):
        match = re.fullmatch(r"self\.__next_f\.push\((\[1,.*\])\);?", node.text().strip(), re.S)
        if match:
            value = json.loads(match[1])
            if isinstance(value[1], str):
                chunks.append(value[1])
    data = "".join(chunks).encode("utf-8")
    rows: dict[str, Any] = {}
    position = 0
    while position < len(data):
        match_bytes = re.match(rb"([0-9a-f]+):", data[position:])
        if not match_bytes:
            raise ValueError("Unsupported/truncated inline Flight row")
        key = match_bytes[1].decode()
        position += match_bytes.end()
        if data[position : position + 1] == b"T":
            end = data.index(b",", position)
            size = int(data[position + 1 : end], 16)
            position = end + 1
            if position + size > len(data):
                raise ValueError("Truncated Flight text payload")
            rows[key] = data[position : position + size].decode("utf-8")
            position += size
        else:
            end = data.find(b"\n", position)
            if end < 0:
                end = len(data)
            # React module/resource rows are not job data.
            with suppress(ValueError):
                rows[key] = json.loads(data[position:end])
            position = end + 1
    return rows


def detail_payload(html: str, job_id: str) -> dict[str, Any]:
    rows = flight_rows(html)

    def resolve(value: Any, seen: frozenset[str] = frozenset()) -> Any:
        if isinstance(value, str) and re.fullmatch(r"\$[0-9a-f]+", value):
            key = value[1:]
            if key not in rows or key in seen:
                raise ValueError("Missing/cyclic detail data reference")
            return resolve(rows[key], seen | {key})
        if isinstance(value, dict):
            return {k: resolve(v, seen) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v, seen) for v in value]
        return value

    for value in rows.values():
        if (
            isinstance(value, dict)
            and str(value.get("jobId")) == job_id
            and "jobDescription" in value
            and "jobRequirement" in value
        ):
            # Only resolve public job fields used by this parser, not account/contact metadata.
            fields = (
                "jobId",
                "jobTitle",
                "companyName",
                "companyId",
                "jobDescription",
                "jobRequirement",
                "prettySalary",
                "workingLocations",
                "address",
                "onlineOn",
                "expiredOn",
                "jobLevel",
                "companySize",
            )
            return {key: resolve(value[key]) for key in fields if key in value}
    raise ValueError("Matching detail payload missing; listing/related jobs are not details")


def plain(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r"\s+", " ", HTMLParser(value).text(separator=" ", strip=True)).strip() or None


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
    if job_id_from_url(discovered.canonical_url) != discovered.source_job_id:
        raise ValueError("Detail URL/ID mismatch")
    job = detail_payload(html, discovered.source_job_id)
    description = plain(job.get("jobDescription"))
    requirements = plain(job.get("jobRequirement"))
    title = plain(job.get("jobTitle"))
    company = plain(job.get("companyName"))
    if not all((title, company, description, requirements)):
        raise ValueError("Detail missing title/company/description/requirements")
    locations = job.get("workingLocations")
    names = []
    if isinstance(locations, list):
        for item in locations:
            if isinstance(item, dict):
                name = plain(item.get("cityName"))
                if name and name not in names:
                    names.append(name)
    payload: dict[str, Any] = {
        "source_name": "vietnamworks",
        "source_job_id": discovered.source_job_id,
        "source_url": discovered.source_url,
        "canonical_url": discovered.canonical_url,
        "listing_url": discovered.listing_url,
        "crawled_at": crawled_at,
        "snapshot_date": snapshot_date,
        "batch_id": batch_id,
        "schema_version": schema_version,
        "parser_version": parser_version,
        "source_reported_total": source_reported_total,
        "raw_html_path": raw_html_path,
        "job_title": title,
        "company_name": company,
        "company_id": str(job["companyId"]) if job.get("companyId") is not None else None,
        "job_description": description,
        "candidate_requirements": requirements,
        "salary_raw": plain(job.get("prettySalary")),
        "location_raw": ", ".join(names) or None,
        "detailed_work_address": plain(job.get("address")),
        "posted_at_raw": plain(job.get("onlineOn")),
        "application_deadline_raw": plain(job.get("expiredOn")),
        "job_level": plain(job.get("jobLevel")),
        "company_size": plain(job.get("companySize")),
    }
    payload["content_hash"] = job_content_hash(payload)
    return JobRecord.model_validate(payload)
