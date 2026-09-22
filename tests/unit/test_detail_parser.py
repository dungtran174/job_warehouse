from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.topcv_detail import parse_detail


def discovered() -> DiscoveredJob:
    return DiscoveredJob(
        source_job_id="1001",
        source_url="https://www.topcv.vn/viec-lam/data-engineer/1001.html?ref=x",
        canonical_url="https://www.topcv.vn/viec-lam/data-engineer/1001.html",
        listing_url="https://www.topcv.vn/jobs",
    )


def parse(html: str):
    return parse_detail(
        html,
        discovered(),
        crawled_at=datetime(2026, 9, 22, 5, tzinfo=UTC),
        snapshot_date=date(2026, 9, 22),
        batch_id="batch-test",
        source_reported_total=1234,
        raw_html_path=None,
        schema_version="1.0.0",
        parser_version="topcv-1.0.0",
    )


def test_detail_parser_prefers_json_ld_and_preserves_sections(read_fixture) -> None:
    record = parse(read_fixture("detail_full.html"))
    assert record.job_title == "Kỹ sư dữ liệu"
    assert record.company_name == "Công ty Ví dụ"
    assert record.salary_raw == "15000000 - 25000000 VND MONTH"
    assert record.location_raw == "Quận 1, Hồ Chí Minh, VN"
    assert record.vacancies == 3
    assert record.application_deadline == date(2026, 9, 30)
    assert record.benefits == ["Bảo hiểm", "Đào tạo"]
    assert record.requirement_tags == ["Python", "SQL"]
    assert record.posted_date_precision == "exact_day"
    assert len(record.content_hash) == 64


def test_detail_missing_optional_fields_is_valid(read_fixture) -> None:
    record = parse(read_fixture("detail_missing_optional.html"))
    assert record.job_title == "Nhân viên kiểm thử"
    assert record.salary_raw is None
    assert record.company_name is None
    assert record.benefits == []


def test_detail_parser_supports_rendered_topcv_structure(read_fixture) -> None:
    record = parse(read_fixture("detail_rendered.html"))
    assert record.job_description == "Xây dựng kho dữ liệu."
    assert record.candidate_requirements == "Thành thạo SQL."
    assert record.detailed_work_address == "Quận 1"
    assert record.working_time == "Thứ Hai - Thứ Sáu"
    assert record.experience_raw == "12 tháng"
    assert record.job_level == "Nhân viên"
    assert record.education_level == "Đại học"
    assert record.vacancies == 2
    assert record.work_model == "Onsite"
    assert record.requirement_tags == ["SQL"]
    assert record.specialization_tags == ["Data Engineer"]
    assert record.category_tags == ["IT", "Dữ liệu"]
    assert record.benefits == ["Bảo hiểm", "SQL"]
    assert record.company_id == "456"
    assert record.company_url.endswith("/cong-ty/cong-ty-mau/456.html")
    assert record.company_size == "100 nhân viên"
    assert record.company_address == "Hà Nội"
    assert record.company_industry == "Phần mềm"


def test_detail_missing_required_title_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse("<html><main><p>No title</p></main></html>")
