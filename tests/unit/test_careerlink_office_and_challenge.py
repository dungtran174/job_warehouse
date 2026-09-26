from datetime import UTC, datetime

from job_crawler.fetchers.careerlink import is_challenge
from job_crawler.models import DiscoveredJob
from job_crawler.parsers.careerlink import parse_detail


def test_office_only_location_comes_from_detail_not_title():
    url = "https://www.careerlink.vn/tim-viec-lam/test/3621196"
    html = f'''<link rel="canonical" href="{url}"><h1 id="job-title">Job title</h1>
    <div id="job-offices">280 Nguyễn Xiển - 280 Nguyễn Xiển, Quận Thanh Xuân, Hà Nội</div>'''
    job = DiscoveredJob(
        source_name="careerlink",
        source_job_id="3621196",
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
    assert record.location_raw == "280 Nguyễn Xiển - 280 Nguyễn Xiển, Quận Thanh Xuân, Hà Nội"
    assert record.candidate_requirements is None


def test_real_http_200_challenge_shape_still_stops():
    # Reduced from the actual stopped response; no tokens/site keys are retained.
    html = """<title>Tìm Việc Làm | CareerLink.vn</title>
    <h1>Xác nhận bạn không phải robot</h1>
    <form id="recaptcha_confirm_form" action="/recaptcha">
    <div class="h-captcha"></div><button disabled>OK</button></form>"""
    assert is_challenge(html)
