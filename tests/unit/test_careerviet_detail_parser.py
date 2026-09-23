from datetime import UTC, date, datetime

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.careerviet_detail import parse_detail


def discovered(job_id: str = "35C00001") -> DiscoveredJob:
    url = f"https://careerviet.vn/vi/tim-viec-lam/viec-lam-mau.{job_id}.html"
    return DiscoveredJob(
        source_name="careerviet",
        source_job_id=job_id,
        source_url=url,
        canonical_url=url,
        listing_url="https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html",
    )


def parse_fixture(html: str, job_id: str = "35C00001"):
    return parse_detail(
        html,
        discovered(job_id),
        crawled_at=datetime(2026, 9, 22, 10, tzinfo=UTC),
        snapshot_date=date(2026, 9, 22),
        batch_id="test-batch",
        source_reported_total=1234,
        raw_html_path=None,
        schema_version="1.0.0",
        parser_version="careerviet-1.1.0",
    )


def test_detail_extracts_required_and_structured_fields(read_source_fixture) -> None:
    record = parse_fixture(read_source_fixture("careerviet", "detail_full.html"))

    assert record.source_name == "careerviet"
    assert record.job_title == "Kỹ sư dữ liệu"
    assert record.company_name == "Công ty Dữ liệu Mẫu"
    assert record.company_id == "35A00001"
    assert record.job_description == "Xây dựng pipeline dữ liệu. Giám sát chất lượng."
    assert record.candidate_requirements == "Thành thạo Python và SQL."
    assert record.salary_raw == "20000000 - 30000000 VND MONTH"
    assert record.location_raw == "Hồ Chí Minh, VN"
    assert record.detailed_work_address == "123 Đường Mẫu, Quận 1"
    assert record.experience_raw == "Kinh nghiệm 2 năm"
    assert record.application_deadline == date(2026, 10, 20)
    assert record.education_level == "Đại học"
    assert record.job_type == "FULL_TIME"
    assert record.benefits == ["Bảo hiểm", "Đào tạo"]
    assert record.content_hash


def test_optional_fields_are_nullable_and_hash_is_stable(read_source_fixture) -> None:
    html = read_source_fixture("careerviet", "detail_missing_optional.html")
    first = parse_fixture(html, "35C00002")
    second = parse_fixture(html, "35C00002")

    assert first.salary_raw is None
    assert first.location_raw is None
    assert first.company_size is None
    assert first.application_method is None
    assert first.content_hash == second.content_hash


def test_content_hash_changes_when_job_content_changes(read_source_fixture) -> None:
    html = read_source_fixture("careerviet", "detail_full.html")
    original = parse_fixture(html)
    changed = parse_fixture(html.replace("Xây dựng pipeline dữ liệu.", "Thiết kế kho dữ liệu."))
    assert original.content_hash != changed.content_hash
