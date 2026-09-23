import json
from datetime import UTC, datetime

import pytest

from job_crawler.feasibility import (
    MAX_DETAIL_ATTEMPTS,
    PROBE_FIELDS,
    SOURCES,
    ProbeReport,
    discover_details,
    extract_source_job_id,
    feasibility_score,
    field_coverage,
    missing_required,
    pagination_detected,
    parse_probe_detail,
    run_probe,
)


@pytest.mark.parametrize(
    "source,url,expected",
    [
        ("careerviet", "https://careerviet.vn/vi/tim-viec-lam/data.35BC1F62.html", "35BC1F62"),
        ("jobsgo", "https://jobsgo.vn/viec-lam/data-engineer-21026511182.html", "21026511182"),
        ("vieclam24h", "https://vieclam24h.vn/viec-lam/data-engineer-123456.html", "123456"),
        ("vietnamworks", "https://www.vietnamworks.com/viec-lam/data-engineer-123456-jv", "123456"),
    ],
)
def test_source_job_id_patterns(source: str, url: str, expected: str) -> None:
    assert extract_source_job_id(SOURCES[source], url) == expected


def test_discovery_is_canonical_deduplicated_and_limited() -> None:
    html = """
    <a href="/viec-lam/data-engineer-21026511182.html?utm_source=x">one</a>
    <a href="/viec-lam/data-engineer-21026511182.html?ref=y">duplicate</a>
    <a href="https://evil.example/viec-lam/bad-21026511183.html">offsite</a>
    """
    assert discover_details(html, "https://jobsgo.vn/viec-lam.html", SOURCES["jobsgo"]) == [
        ("21026511182", "https://jobsgo.vn/viec-lam/data-engineer-21026511182.html")
    ]


def test_generic_detail_parser_and_coverage() -> None:
    posting = {
        "@type": "JobPosting",
        "title": "Data Engineer",
        "description": (
            "<h2>Mô tả công việc</h2><p>Xây pipeline.</p>"
            "<h2>Yêu cầu ứng viên</h2><p>Biết SQL.</p>"
            "<h2>Quyền lợi</h2><p>Bảo hiểm</p>"
        ),
        "validThrough": "2026-10-10",
        "employmentType": "FULL_TIME",
        "hiringOrganization": {"name": "Công ty Mẫu"},
        "jobLocation": {"address": {"addressLocality": "Hà Nội"}},
    }
    html = (
        '<html><head><script type="application/ld+json">'
        f"{json.dumps(posting, ensure_ascii=False)}"
        "</script></head><body><h1>Data Engineer</h1></body></html>"
    )
    record = parse_probe_detail(
        html,
        source_name="jobsgo",
        source_job_id="21026511182",
        canonical_url="https://jobsgo.vn/viec-lam/data-21026511182.html",
        crawled_at=datetime(2026, 9, 22, tzinfo=UTC),
    )
    assert missing_required(record) == []
    assert record.job_description == "Xây pipeline."
    assert record.candidate_requirements == "Biết SQL."
    assert record.benefits == ["Bảo hiểm"]
    assert field_coverage([record])["company_name"] == 100.0
    assert len(record.content_hash) == 64


def test_pagination_and_score() -> None:
    assert pagination_detected('<a rel="next" href="?page=2">next</a>', "https://jobsgo.vn")
    assert pagination_detected(
        '<div class="pagination"><a role="button">1</a><a role="button">2</a></div>',
        "https://careerviet.vn",
    )
    report = ProbeReport(
        source="jobsgo",
        listing_url="https://jobsgo.vn/viec-lam.html",
        started_at="now",
        listing_pages_succeeded=1,
        unique_job_ids=3,
        detail_successes=MAX_DETAIL_ATTEMPTS,
        pagination_detected=True,
        incremental_possible=True,
        field_coverage={name: 100.0 for name in PROBE_FIELDS},
    )
    assert feasibility_score(report) == 100.0


@pytest.mark.parametrize("pages,details", [(2, 3), (1, 0), (1, 4)])
def test_probe_hard_limits_fail_before_network(pages: int, details: int, tmp_path) -> None:
    with pytest.raises(ValueError):
        run_probe(
            "jobsgo",
            output_dir=tmp_path,
            max_listing_pages=pages,
            max_details=details,
        )
