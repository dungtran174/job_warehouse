from datetime import UTC, datetime

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.timviec365 import START, parse_detail


def test_labeled_optional_fields_remain_raw():
    url = "https://timviec365.vn/test-p123.html"
    html = f'<link rel="canonical" href="{url}">'
    html += '<div class="boxDetailInfo"><h1 class="titleNew" data-id="123">Title</h1></div>'
    for label, value in (
        ("Bằng cấp", "Đại học trở lên"),
        ("Chức vụ", "Nhân viên"),
        ("Số lượng cần tuyển", "2 người"),
        ("Hình thức làm việc", "Toàn thời gian cố định"),
        ("Cập nhật", "26/09/2026"),
    ):
        html += (
            f'<div class="itemYauCauKhac"><p class="titleYauCauKhac">{label}</p>'
            f'<p class="valYauCauKhac">{value}</p></div>'
        )
    now = datetime.now(UTC)
    job = DiscoveredJob(
        source_name="timviec365",
        source_job_id="123",
        source_url=url,
        canonical_url=url,
        listing_url=START,
    )
    row = parse_detail(
        html,
        job,
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
    )
    assert row.education_level == "Đại học trở lên"
    assert row.job_level == "Nhân viên"
    assert row.vacancies_raw == "2 người"
    assert row.job_type == "Toàn thời gian cố định"
    assert row.posted_at_raw is None
