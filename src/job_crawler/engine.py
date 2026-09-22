from __future__ import annotations

import json
import logging
import urllib.robotparser
from collections.abc import Callable
from datetime import date, datetime
from urllib.parse import urlsplit

from pydantic import ValidationError

from job_crawler.config import CrawlConfig
from job_crawler.crawlers.base import SourceCrawler
from job_crawler.fetchers.base import Fetcher, FetchError
from job_crawler.models import CrawlError, RunManifest
from job_crawler.storage.jsonl import (
    BatchStorage,
    StorageError,
    batch_paths,
    find_latest_resumable,
    make_batch_id,
)
from job_crawler.utils.time import local_snapshot_date, utc_now
from job_crawler.utils.url import topcv_robots_url

LOGGER = logging.getLogger(__name__)
MISSING_FIELD_NAMES = (
    "salary_raw",
    "location_raw",
    "detailed_work_address",
    "experience_raw",
    "application_deadline_raw",
    "job_level",
    "education_level",
    "vacancies_raw",
    "work_model",
    "job_type",
    "profession_tags",
    "category_tags",
    "specialization_tags",
    "requirement_tags",
    "job_description",
    "candidate_requirements",
    "income_text",
    "benefits",
    "working_time",
    "application_method",
    "company_name",
    "company_id",
    "company_url",
    "company_size",
    "company_address",
    "company_industry",
    "posted_at_raw",
)


def log_event(event: str, **context: object) -> None:
    LOGGER.info(json.dumps({"event": event, **context}, ensure_ascii=False, default=str))


class CrawlEngine:
    def __init__(
        self,
        config: CrawlConfig,
        crawler: SourceCrawler,
        fetcher: Fetcher,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.config = config
        self.crawler = crawler
        self.fetcher = fetcher
        self.clock = clock

    def _new_storage(self, started_at: datetime) -> tuple[BatchStorage, RunManifest, date]:
        snapshot = local_snapshot_date(started_at, self.config.timezone)
        batch_id = make_batch_id(started_at)
        paths = batch_paths(
            self.config.output_dir, self.crawler.source_name, snapshot.isoformat(), batch_id
        )
        storage = BatchStorage(paths, create=True)
        manifest = RunManifest(
            source=self.crawler.source_name,
            batch_id=batch_id,
            mode=self.config.mode,
            start_url=self.config.start_url,
            started_at=started_at,
            status="running",
            authorization_reference=self.config.authorization_reference or "",
            delay_min_seconds=self.config.delay_min_seconds,
            delay_max_seconds=self.config.delay_max_seconds,
            max_retries=self.config.max_retries,
            schema_version=self.crawler.schema_version,
            parser_version=self.crawler.parser_version,
            fetcher_requested=self.config.fetcher,
            fetcher_used=self.fetcher.state.active,
            browser_headless=self.fetcher.state.headless,
        )
        storage.write_manifest(manifest)
        return storage, manifest, snapshot

    def _resume_storage(self) -> tuple[BatchStorage, RunManifest, date]:
        root = find_latest_resumable(self.config.output_dir, self.crawler.source_name)
        if root is None:
            raise StorageError("No resumable batch was found.")
        storage = BatchStorage.resume(root)
        manifest = storage.read_manifest()
        if manifest.mode != self.config.mode:
            storage.close()
            raise StorageError("Resume mode does not match the existing batch.")
        if manifest.start_url != self.config.start_url:
            storage.close()
            raise StorageError("Resume start URL does not match the existing batch.")
        if (
            manifest.schema_version != self.crawler.schema_version
            or manifest.parser_version != self.crawler.parser_version
        ):
            storage.close()
            raise StorageError("Refusing resume with a different schema/parser version.")
        snapshot = date.fromisoformat(root.parent.name.removeprefix("snapshot_date="))
        manifest.status = "running"
        manifest.finished_at = None
        manifest.authorization_reference = self.config.authorization_reference or ""
        manifest.fetcher_requested = self.config.fetcher
        manifest.fetcher_used = self.fetcher.state.active
        manifest.browser_headless = self.fetcher.state.headless
        storage.write_manifest(manifest)
        return storage, manifest, snapshot

    def _error(
        self,
        *,
        url: str,
        stage: str,
        error_type: str,
        message: str,
        attempt: int = 1,
        job_id: str | None = None,
        status: int | None = None,
        retryable: bool = False,
    ) -> CrawlError:
        return CrawlError(
            url=url,
            job_id=job_id,
            stage=stage,
            error_type=error_type,
            http_status=status,
            message=message,
            attempt=attempt,
            timestamp=self.clock(),
            retryable=retryable,
        )

    @staticmethod
    def _same_host(left: str, right: str) -> bool:
        return (urlsplit(left).hostname or "").casefold() == (
            urlsplit(right).hostname or ""
        ).casefold()

    def run(self) -> RunManifest:
        self.config.validate()
        started_at = self.clock()
        storage, manifest, snapshot = (
            self._resume_storage() if self.config.resume else self._new_storage(started_at)
        )
        self.fetcher.configure_run(storage.paths.root, manifest.batch_id)
        stopped = False
        listing_reason = "no_next_page"
        try:
            robots_url = topcv_robots_url(self.config.start_url)
            try:
                robots_response = self.fetcher.get(robots_url)
            except FetchError as exc:
                storage.append_error(
                    self._error(
                        url=exc.url,
                        stage="robots",
                        error_type=type(exc).__name__,
                        message=str(exc),
                        attempt=exc.attempt,
                        status=exc.status_code,
                        retryable=exc.retryable,
                    )
                )
                manifest.status = "stopped"
                manifest.termination_reason = "robots_unavailable"
                manifest.finished_at = self.clock()
                storage.write_manifest(manifest)
                return manifest
            log_event(
                "response",
                batch_id=manifest.batch_id,
                mode=manifest.mode,
                stage="robots",
                url=robots_response.url,
                status=robots_response.status_code,
                attempt=robots_response.attempt,
                duration_seconds=robots_response.duration_seconds,
            )

            robots = urllib.robotparser.RobotFileParser()
            robots.set_url(robots_url)
            robots.parse(robots_response.text.splitlines())
            if not robots.can_fetch(self.config.user_agent, self.config.start_url):
                manifest.status = "stopped"
                manifest.termination_reason = "robots_denied"
                manifest.finished_at = self.clock()
                storage.write_manifest(manifest)
                return manifest

            storage.checkpoint.enqueue_listing(self.config.start_url)
            while self.config.max_pages is None or (
                manifest.listing_pages_requested < self.config.max_pages
            ):
                listing_url = storage.checkpoint.next_listing()
                if listing_url is None:
                    listing_reason = "no_next_page"
                    break
                if not self._same_host(listing_url, self.config.start_url):
                    storage.checkpoint.finish_listing(listing_url, "failed")
                    listing_reason = "cross_host_listing_url"
                    stopped = True
                    break
                if not robots.can_fetch(self.config.user_agent, listing_url):
                    storage.checkpoint.finish_listing(listing_url, "failed")
                    listing_reason = "robots_denied"
                    stopped = True
                    break
                manifest.listing_pages_requested += 1
                storage.write_manifest(manifest)
                log_event(
                    "request",
                    batch_id=manifest.batch_id,
                    mode=manifest.mode,
                    stage="listing",
                    page=manifest.listing_pages_requested,
                    url=listing_url,
                )
                try:
                    response = self.fetcher.get(listing_url)
                except FetchError as exc:
                    storage.checkpoint.finish_listing(listing_url, "failed")
                    storage.append_error(
                        self._error(
                            url=exc.url,
                            stage="listing",
                            error_type=type(exc).__name__,
                            message=str(exc),
                            attempt=exc.attempt,
                            status=exc.status_code,
                            retryable=exc.retryable,
                        )
                    )
                    listing_reason = "access_blocked" if exc.blocked else "listing_fetch_failed"
                    stopped = exc.blocked
                    manifest.challenge_detected = self.fetcher.state.challenge_detected
                    break
                manifest.fetcher_used = response.fetcher
                manifest.http_fallback_to_playwright = self.fetcher.state.fallback_used
                manifest.browser_headless = self.fetcher.state.headless
                log_event(
                    "response",
                    batch_id=manifest.batch_id,
                    mode=manifest.mode,
                    stage="listing",
                    page=manifest.listing_pages_requested,
                    url=response.url,
                    status=response.status_code,
                    attempt=response.attempt,
                    duration_seconds=response.duration_seconds,
                )
                try:
                    page = self.crawler.parse_listing(response.text, response.url)
                except Exception as exc:
                    storage.checkpoint.finish_listing(listing_url, "failed")
                    storage.append_error(
                        self._error(
                            url=response.url,
                            stage="listing_parse",
                            error_type=type(exc).__name__,
                            message=str(exc),
                            attempt=response.attempt,
                        )
                    )
                    listing_reason = "listing_parse_failed"
                    break

                if not page.jobs and self.fetcher.fallback("empty_listing"):
                    manifest.fetcher_used = self.fetcher.state.active
                    manifest.http_fallback_to_playwright = True
                    manifest.browser_headless = self.fetcher.state.headless
                    storage.write_manifest(manifest)
                    log_event(
                        "fetcher_fallback",
                        batch_id=manifest.batch_id,
                        mode=manifest.mode,
                        stage="listing",
                        reason="empty_listing",
                        url=listing_url,
                    )
                    try:
                        response = self.fetcher.get(listing_url)
                        page = self.crawler.parse_listing(response.text, response.url)
                    except FetchError as exc:
                        storage.checkpoint.finish_listing(listing_url, "failed")
                        manifest.challenge_detected = self.fetcher.state.challenge_detected
                        storage.append_error(
                            self._error(
                                url=exc.url,
                                stage="listing_browser_fallback",
                                error_type=type(exc).__name__,
                                message=f"{exc}; artifacts={list(exc.artifact_paths)}",
                                attempt=exc.attempt,
                                status=exc.status_code,
                                retryable=exc.retryable,
                            )
                        )
                        listing_reason = (
                            "browser_challenge" if exc.blocked else "listing_fetch_failed"
                        )
                        stopped = exc.blocked
                        break
                    except Exception as exc:
                        storage.checkpoint.finish_listing(listing_url, "failed")
                        storage.append_error(
                            self._error(
                                url=listing_url,
                                stage="listing_browser_parse",
                                error_type=type(exc).__name__,
                                message=str(exc),
                            )
                        )
                        listing_reason = "listing_parse_failed"
                        break

                if self.config.save_html:
                    storage.save_page_html(
                        f"listing-{manifest.listing_pages_requested:03d}", response.text
                    )
                if not page.jobs:
                    storage.checkpoint.finish_listing(listing_url, "failed")
                    storage.append_error(
                        self._error(
                            url=response.url,
                            stage="listing_parse",
                            error_type="NoJobsFound",
                            message="Rendered listing contained no valid TopCV detail URL/job ID",
                            attempt=response.attempt,
                        )
                    )
                    listing_reason = "no_jobs_found"
                    break

                manifest.listing_pages_succeeded += 1
                manifest.urls_discovered += len(page.jobs)
                if manifest.source_reported_total is None:
                    manifest.source_reported_total = page.source_reported_total
                if not storage.checkpoint.add_fingerprint(page.fingerprint):
                    storage.checkpoint.finish_listing(listing_url)
                    listing_reason = "repeated_page_fingerprint"
                    break
                new_ids = 0
                for job in page.jobs:
                    if storage.checkpoint.enqueue_detail(job):
                        new_ids += 1
                    else:
                        manifest.duplicates_skipped += 1
                manifest.unique_ids_discovered = storage.checkpoint.count_details()
                storage.checkpoint.finish_listing(listing_url)
                storage.write_manifest(manifest)
                if new_ids == 0:
                    listing_reason = "no_new_ids"
                    break
                if page.next_url is None:
                    listing_reason = "no_next_page"
                    break
                if not storage.checkpoint.enqueue_listing(page.next_url):
                    listing_reason = "listing_url_loop"
                    break
            else:
                listing_reason = "max_pages"

            detail_reason: str | None = listing_reason if stopped else None
            while not stopped and (
                self.config.max_details is None
                or manifest.detail_requested < self.config.max_details
            ):
                pending_job = storage.checkpoint.next_detail()
                if pending_job is None:
                    break
                job = pending_job
                if storage.checkpoint.is_completed(job.source_job_id):
                    storage.checkpoint.finish_detail(job.source_job_id, "completed")
                    manifest.duplicates_skipped += 1
                    continue
                if not robots.can_fetch(self.config.user_agent, job.canonical_url):
                    storage.checkpoint.finish_detail(job.source_job_id, "failed")
                    detail_reason = "robots_denied"
                    stopped = True
                    break
                manifest.detail_requested += 1
                storage.write_manifest(manifest)
                log_event(
                    "request",
                    batch_id=manifest.batch_id,
                    mode=manifest.mode,
                    stage="detail",
                    job_id=job.source_job_id,
                    url=job.canonical_url,
                )
                try:
                    response = self.fetcher.get(job.canonical_url)
                except FetchError as exc:
                    storage.checkpoint.finish_detail(job.source_job_id, "failed")
                    manifest.detail_failed += 1
                    storage.append_error(
                        self._error(
                            url=exc.url,
                            job_id=job.source_job_id,
                            stage="detail",
                            error_type=type(exc).__name__,
                            message=str(exc),
                            attempt=exc.attempt,
                            status=exc.status_code,
                            retryable=exc.retryable,
                        )
                    )
                    if exc.blocked:
                        manifest.challenge_detected = self.fetcher.state.challenge_detected
                        detail_reason = (
                            "browser_challenge" if exc.challenge_type else "access_blocked"
                        )
                        stopped = True
                        break
                    continue
                log_event(
                    "response",
                    batch_id=manifest.batch_id,
                    mode=manifest.mode,
                    stage="detail",
                    job_id=job.source_job_id,
                    url=response.url,
                    status=response.status_code,
                    attempt=response.attempt,
                    duration_seconds=response.duration_seconds,
                )
                manifest.fetcher_used = response.fetcher
                manifest.http_fallback_to_playwright = self.fetcher.state.fallback_used
                manifest.browser_headless = self.fetcher.state.headless

                raw_html_path = (
                    storage.save_html(job.source_job_id, response.text)
                    if self.config.save_html
                    else None
                )
                try:
                    record = self.crawler.parse_detail(
                        response.text,
                        job,
                        crawled_at=self.clock(),
                        snapshot_date=snapshot,
                        batch_id=manifest.batch_id,
                        source_reported_total=manifest.source_reported_total,
                        raw_html_path=raw_html_path,
                    )
                except ValidationError as exc:
                    storage.checkpoint.finish_detail(job.source_job_id, "failed")
                    manifest.detail_failed += 1
                    manifest.records_missing_required += 1
                    storage.append_error(
                        self._error(
                            url=response.url,
                            job_id=job.source_job_id,
                            stage="validation",
                            error_type=type(exc).__name__,
                            message=str(exc),
                            attempt=response.attempt,
                        )
                    )
                    continue
                except Exception as exc:
                    storage.checkpoint.finish_detail(job.source_job_id, "failed")
                    manifest.detail_failed += 1
                    storage.append_error(
                        self._error(
                            url=response.url,
                            job_id=job.source_job_id,
                            stage="detail_parse",
                            error_type=type(exc).__name__,
                            message=str(exc),
                            attempt=response.attempt,
                        )
                    )
                    continue

                for field_name in MISSING_FIELD_NAMES:
                    value = getattr(record, field_name)
                    if value is None or value == [] or value == "":
                        manifest.missing_fields[field_name] = (
                            manifest.missing_fields.get(field_name, 0) + 1
                        )

                if storage.append_job(record):
                    manifest.records_written += 1
                else:
                    manifest.duplicates_skipped += 1
                storage.checkpoint.mark_completed(job.source_job_id)
                manifest.detail_succeeded += 1
                storage.write_manifest(manifest)

            if storage.checkpoint.has_pending_details() and detail_reason is None:
                detail_reason = "max_details"
            manifest.termination_reason = detail_reason or listing_reason
            manifest.fetcher_used = self.fetcher.state.active
            manifest.http_fallback_to_playwright = self.fetcher.state.fallback_used
            manifest.browser_headless = self.fetcher.state.headless
            manifest.challenge_detected = self.fetcher.state.challenge_detected
            manifest.status = (
                "stopped"
                if stopped
                else "completed_with_errors"
                if manifest.detail_failed
                or manifest.listing_pages_requested != manifest.listing_pages_succeeded
                else "completed"
            )
            manifest.finished_at = self.clock()
            storage.write_manifest(manifest)
            log_event(
                "batch_finished",
                batch_id=manifest.batch_id,
                status=manifest.status,
                reason=manifest.termination_reason,
                records=manifest.records_written,
            )
            return manifest
        except Exception as exc:
            manifest.status = "failed"
            manifest.termination_reason = "unexpected_error"
            manifest.finished_at = self.clock()
            storage.append_error(
                self._error(
                    url=self.config.start_url,
                    stage="engine",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            storage.write_manifest(manifest)
            raise
        finally:
            storage.close()
