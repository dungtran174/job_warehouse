from __future__ import annotations

from datetime import date, datetime

from job_crawler.models import DiscoveredJob, JobRecord, ListingPage
from job_crawler.parsers.topcv_detail import parse_detail
from job_crawler.parsers.topcv_listing import parse_listing


class TopCVCrawler:
    source_name = "topcv"
    schema_version = "1.0.0"
    parser_version = "topcv-1.1.0"

    def parse_listing(self, html: str, listing_url: str) -> ListingPage:
        return parse_listing(html, listing_url)

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
    ) -> JobRecord:
        return parse_detail(
            html,
            discovered,
            crawled_at=crawled_at,
            snapshot_date=snapshot_date,
            batch_id=batch_id,
            source_reported_total=source_reported_total,
            raw_html_path=raw_html_path,
            schema_version=self.schema_version,
            parser_version=self.parser_version,
        )
