from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StableModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscoveredJob(StableModel):
    source_name: str = "topcv"
    source_job_id: str
    source_url: str
    canonical_url: str
    listing_url: str


class ListingPage(StableModel):
    jobs: list[DiscoveredJob] = Field(default_factory=list)
    next_url: str | None = None
    source_reported_total: int | None = None
    fingerprint: str


class JobRecord(StableModel):
    source_name: str
    source_job_id: str
    source_url: str
    canonical_url: str
    listing_url: str
    source_reported_total: int | None = None
    crawled_at: datetime
    snapshot_date: date
    batch_id: str
    schema_version: str
    parser_version: str
    raw_html_path: str | None = None
    content_hash: str

    job_title: str
    salary_raw: str | None = None
    location_raw: str | None = None
    detailed_work_address: str | None = None
    experience_raw: str | None = None
    application_deadline_raw: str | None = None
    application_deadline: date | None = None
    job_level: str | None = None
    education_level: str | None = None
    vacancies_raw: str | None = None
    vacancies: int | None = None
    work_model: str | None = None
    job_type: str | None = None
    profession_tags: list[str] = Field(default_factory=list)
    category_tags: list[str] = Field(default_factory=list)
    specialization_tags: list[str] = Field(default_factory=list)
    requirement_tags: list[str] = Field(default_factory=list)

    job_description: str | None = None
    candidate_requirements: str | None = None
    income_text: str | None = None
    benefits: list[str] = Field(default_factory=list)
    working_time: str | None = None
    application_method: str | None = None

    company_name: str | None = None
    company_id: str | None = None
    company_url: str | None = None
    company_size: str | None = None
    company_address: str | None = None
    company_industry: str | None = None

    posted_at_raw: str | None = None
    posted_at_estimated: datetime | None = None
    posted_date_precision: Literal["estimated_hour", "estimated_day", "exact_day", "unknown"] = (
        "unknown"
    )

    @field_validator("crawled_at", "posted_at_estimated")
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class CrawlError(StableModel):
    url: str
    job_id: str | None = None
    stage: str
    error_type: str
    http_status: int | None = None
    message: str
    attempt: int
    timestamp: datetime
    retryable: bool


class RunManifest(StableModel):
    source: str
    batch_id: str
    mode: str
    start_url: str
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "completed", "completed_with_errors", "stopped", "failed"]
    authorization_reference: str
    authorization_references: list[str] = Field(default_factory=list)
    source_reported_total: int | None = None
    listing_pages_requested: int = 0
    listing_pages_succeeded: int = 0
    listing_pages_unique: int = 0
    listing_page_fingerprints: list[str] = Field(default_factory=list)
    duplicate_listing_pages: int = 0
    new_job_ids_per_page: list[int] = Field(default_factory=list)
    pagination_termination_reason: str | None = None
    urls_discovered: int = 0
    unique_ids_discovered: int = 0
    detail_requested: int = 0
    detail_succeeded: int = 0
    detail_failed: int = 0
    duplicates_skipped: int = 0
    records_written: int = 0
    records_missing_required: int = 0
    delay_min_seconds: float
    delay_max_seconds: float
    max_retries: int
    schema_version: str
    parser_version: str
    termination_reason: str | None = None
    fetcher_requested: Literal["auto", "http", "playwright"] = "http"
    fetcher_used: str = "http"
    http_fallback_to_playwright: bool = False
    browser_headless: bool | None = None
    challenge_detected: bool = False
    missing_fields: dict[str, int] = Field(default_factory=dict)
    incremental_new_ids: int = 0
    incremental_existing_ids: int = 0
    content_hash_new: int = 0
    content_hash_unchanged: int = 0
    content_hash_changed: int = 0
