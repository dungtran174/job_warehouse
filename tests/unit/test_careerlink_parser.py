from datetime import UTC, datetime
from pathlib import Path

import pytest

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.careerlink import job_url, parse_detail, parse_listing

FIXTURES = Path(__file__).parents[1] / "fixtures" / "careerlink"


@pytest.mark.parametrize(
    "number,job_id,description_length,requirements_length",
    [
        (1, "3634108", 294, 258),
        (2, "3634019", 748, 234),
        (3, "3628750", 923, 704),
    ],
)
def test_real_detail_sections(number, job_id, description_length, requirements_length):
    html = (FIXTURES / f"detail_{number}.html").read_text()
    job = DiscoveredJob(
        source_name="careerlink",
        source_job_id=job_id,
        source_url="https://www.careerlink.vn/tim-viec-lam/test/" + job_id,
        canonical_url="https://www.careerlink.vn/tim-viec-lam/test/" + job_id,
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
    assert record.source_job_id == job_id
    assert record.company_name and record.job_title
    assert len(record.job_description) == description_length
    assert len(record.candidate_requirements) == requirements_length
    assert record.salary_raw and record.location_raw and record.posted_at_raw == "26-09-2026"
    assert len(record.content_hash) == 64
    job.source_job_id = "9999999"
    with pytest.raises(ValueError, match="ID"):
        parse_detail(
            html,
            job,
            crawled_at=now,
            snapshot_date=now.date(),
            batch_id="offline",
            source_reported_total=None,
            raw_html_path=None,
        )


def test_listing_scope_dedup_and_pagination():
    html = """<ul class="list-group"><li class="job-item">
    <a class="job-link" href="/tim-viec-lam/test/1234567?source=site">A</a>
    <a class="job-link" href="/tim-viec-lam/test/1234567">duplicate</a></li></ul>
    <a class="job-link" href="/tim-viec-lam/featured/9999999">Featured</a>
    <ul class="pagination"><a rel="next" href="/vieclam/list?page=2">2</a></ul>"""
    page = parse_listing(html, "https://www.careerlink.vn/vieclam/list")
    assert [j.source_job_id for j in page.jobs] == ["1234567"]
    assert page.jobs[0].canonical_url.endswith("/1234567")
    assert page.next_url == "https://www.careerlink.vn/vieclam/list?page=2"
    assert not parse_listing("<h1>Loading</h1>", page.next_url).jobs
    assert job_url("https://evil.example/tim-viec-lam/test/1234567") is None
    with pytest.raises(ValueError, match="pagination"):
        parse_listing(
            html.replace("/vieclam/list?page=2", "https://evil.example/"),
            "https://www.careerlink.vn/vieclam/list",
        )


def test_missing_optional_and_content_stay_null():
    url = "https://www.careerlink.vn/tim-viec-lam/test/1234567"
    job = DiscoveredJob(
        source_job_id="1234567",
        source_url=url,
        canonical_url=url,
        listing_url="https://www.careerlink.vn/vieclam/list",
    )
    now = datetime.now(UTC)
    record = parse_detail(
        f'<link rel="canonical" href="{url}"><h1 id="job-title">Title</h1>',
        job,
        crawled_at=now,
        snapshot_date=now.date(),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
    )
    assert record.company_name is None
    assert record.job_description is None and record.candidate_requirements is None
    assert record.salary_raw is None and record.location_raw is None
    assert record.posted_at_raw is None
