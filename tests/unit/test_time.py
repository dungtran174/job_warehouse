from datetime import UTC, datetime

from job_crawler.utils.time import estimate_relative_posted, parse_source_date


def test_relative_vietnamese_time_is_estimated() -> None:
    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    estimated, precision = estimate_relative_posted("4 ngày trước", now)
    assert estimated == datetime(2026, 9, 18, 12, tzinfo=UTC)
    assert precision == "estimated_day"


def test_parse_source_date() -> None:
    assert str(parse_source_date("30/09/2026")) == "2026-09-30"
    assert parse_source_date("Không giới hạn") is None
