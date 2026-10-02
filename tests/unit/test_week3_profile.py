import gzip
import runpy
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from job_crawler.models import JobRecord

MODULE = runpy.run_path(str(Path(__file__).parents[2] / "scripts/profile_week3_inputs.py"))


def test_missing_distinguishes_null_absent_blank_empty_array_from_zero():
    profile = MODULE["field_profile"](
        [
            {},
            {"x": None},
            {"x": " "},
            {"x": []},
            {"x": 0},
            {"x": False},
            {"x": ["a"]},
        ]
    )["x"]
    assert profile["missing_count"] == 4
    assert profile["missing"] == {
        "absent": 1,
        "null": 1,
        "blank_string": 1,
        "empty_array": 1,
        "present": 3,
    }
    assert profile["types"]["integer"] == profile["types"]["boolean"] == 1
    assert profile["array_element_types"] == {"string": 1}


def test_salary_shapes_do_not_infer_a_fixed_salary_from_bare_number():
    classify = MODULE["salary_shape"]
    assert classify("20000000") == "bare_number_ambiguous_bound"
    assert classify("7.1 triệu - 11.6 triệu") == "range_million_decimal"
    assert classify("600 - 1600 USD MONTH") == "range_USD_MONTH"
    assert classify("Cạnh tranh") == "Cạnh tranh"
    assert classify(None) == "null"


@pytest.mark.parametrize("include_html_record", [False, True])
def test_metadata_only_profile_does_not_claim_dom_verification(tmp_path, include_html_record):
    record = JobRecord(
        source_name="careerlink",
        source_job_id="1",
        source_url="https://www.careerlink.vn/tim-viec-lam/job/1",
        canonical_url="https://www.careerlink.vn/tim-viec-lam/job/1",
        listing_url="https://www.careerlink.vn/vieclam/list",
        crawled_at=datetime(2026, 9, 30, tzinfo=UTC),
        snapshot_date=date(2026, 9, 26),
        batch_id="offline-test",
        schema_version="1.0.0",
        parser_version="careerlink-1.0.2",
        content_hash="unused-in-profiler",
        job_title="Test job",
        company_name="Test company",
        job_description="Full description",
        candidate_requirements="Full requirements",
        posted_at_raw="29-09-2026",
    )
    records = [record]
    if include_html_record:
        html = (
            '<div id="section-job-description"><div class="rich-text-content">'
            "Full description</div></div>"
            '<div id="section-job-skills"><div class="rich-text-content">'
            "Full requirements</div></div>"
        )
        (tmp_path / "2.html.gz").write_bytes(gzip.compress(html.encode()))
        records.append(
            record.model_copy(update={"source_job_id": "2", "raw_html_path": "2.html.gz"})
        )
    raw = "\n".join(r.model_dump_json() for r in records) + "\n"
    (tmp_path / "jobs.jsonl").write_text(raw)
    result = MODULE["profile"](tmp_path)
    assert (tmp_path / "jobs.jsonl").read_text() == raw
    assert result["html_records_unavailable"] == 1
    assert result["html_records_available"] == int(include_html_record)
    assert result["records"] == 1 + int(include_html_record)
    for field in ("job_description", "candidate_requirements"):
        evidence = result["html_evidence"][0]["sections"][field]
        assert evidence["full_dom_match"] is None
        assert evidence["full_source_match"] is None
        assert evidence["value_source"] == "unavailable"
        stats = result["text_statistics"][field]
        assert stats["full_source_match_count"] == int(include_html_record)
        assert stats["full_dom_match_count"] == int(include_html_record)
        assert stats["value_sources"]["unavailable"] == 1
