from datetime import UTC, datetime

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.careerlink import parse_detail


def test_repeated_location_blocks_are_all_preserved():
    # Reduced from HTTP detail 3633921; the source repeats the same HTML id.
    url = "https://www.careerlink.vn/tim-viec-lam/chuyen-vien-qc-nganh-may/3633921"
    html = f'''<link rel="canonical" href="{url}"><h1 id="job-title">Chuyên Viên QC Ngành May</h1>
    <div id="job-location">Nghệ An</div><div id="job-location">Quảng Trị</div>
    <div id="job-location">Đà Nẵng</div>'''
    job = DiscoveredJob(
        source_name="careerlink",
        source_job_id="3633921",
        source_url=url,
        canonical_url=url,
        listing_url="https://www.careerlink.vn/vieclam/list",
    )
    now = datetime.now(UTC)
    record = parse_detail(
        html,
        job,
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
    )
    assert record.location_raw == "Nghệ An Quảng Trị Đà Nẵng"
    assert record.parser_version == "careerlink-1.0.2"
