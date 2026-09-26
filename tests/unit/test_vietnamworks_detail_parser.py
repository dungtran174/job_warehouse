import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from job_crawler.models import DiscoveredJob
from job_crawler.parsers.vietnamworks_detail import job_id_from_url, parse_detail

ROOT = Path(__file__).parents[1] / "fixtures" / "vietnamworks"
EXPECTED = json.loads((ROOT / "detail_expected.json").read_text())


def record(job_id="2109839", html=None, suffix="jd"):
    url = EXPECTED[job_id]["url"][:-2] + suffix
    return parse_detail(
        html if html is not None else (ROOT / f"detail_{job_id}.html").read_text(),
        DiscoveredJob(
            source_name="vietnamworks",
            source_job_id=job_id,
            source_url=url,
            canonical_url=url,
            listing_url="https://www.vietnamworks.com/tim-viec-lam",
        ),
        crawled_at=datetime(2026, 9, 26, tzinfo=UTC),
        snapshot_date=date(2026, 9, 26),
        batch_id="offline",
        source_reported_total=None,
        raw_html_path=None,
        schema_version="1.0.0",
        parser_version="vietnamworks-1.0.0",
    )


@pytest.mark.parametrize("job_id", list(EXPECTED))
@pytest.mark.parametrize("suffix", ["jd", "jv"])
def test_saved_details_match_independent_complete_dom_audit(job_id, suffix):
    actual = record(job_id, suffix=suffix)
    assert actual.source_name == "vietnamworks"
    assert actual.source_job_id == job_id
    for field in ("job_title", "company_name", "salary_raw", "location_raw"):
        assert getattr(actual, field) == EXPECTED[job_id][field]
    for field in ("job_description", "candidate_requirements"):
        assert (
            hashlib.sha256(getattr(actual, field).encode()).hexdigest()
            == EXPECTED[job_id][field + "_sha256"]
        )
    assert len(actual.content_hash) == 64
    assert actual.education_level is None
    assert record(job_id, suffix=suffix).content_hash == actual.content_hash


def test_listing_or_wrong_id_is_not_a_detail():
    with pytest.raises(ValueError, match="Matching detail"):
        record(html=(ROOT / "listing_jd_excerpt.html").read_text())
    with pytest.raises(ValueError, match="Matching detail"):
        record("2107184", html=(ROOT / "detail_2109839.html").read_text())


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/test-2109839-jd",
        "https://www.vietnamworks.com/test-2109839-jd/related",
        "https://www.vietnamworks.com/test-2109839-jv-extra",
    ],
)
def test_invalid_urls(url):
    assert job_id_from_url(url) is None


def test_missing_required_is_rejected_and_optional_remains_null():
    payload = {
        "jobId": 2109839,
        "jobTitle": "Title",
        "companyName": "Company",
        "jobDescription": "Full description",
        "jobRequirement": "Full requirement",
    }
    html = (
        "<script>self.__next_f.push("
        + json.dumps([1, "0:" + json.dumps(payload) + "\n"])
        + ")</script>"
    )
    actual = record(html=html)
    assert actual.salary_raw is None
    assert actual.location_raw is None
    assert actual.posted_at_raw is None
    with pytest.raises(ValueError, match="missing title"):
        record(html=html.replace("Full requirement", ""))
