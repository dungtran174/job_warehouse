from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from job_crawler.models import DiscoveredJob, JobRecord, ListingPage


class SourceCrawler(Protocol):
    source_name: str
    schema_version: str
    parser_version: str

    def parse_listing(self, html: str, listing_url: str) -> ListingPage: ...

    def parse_detail(
        self,
        html: str,
        discovered: DiscoveredJob,
        *,
        crawled_at: datetime,
        snapshot_date: date,
        batch_id: str,
        source_reported_total: int | None,
        raw_html_path: str | None,
    ) -> JobRecord: ...
