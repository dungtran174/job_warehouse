"""Synthetic frozen inputs exercise validation without real data or PostgreSQL."""

import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from silver_database_fixtures import frozen_runs, job, reseal, write_json

from job_warehouse.cli import main
from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.database.preflight import preflight, validate_job
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS


def test_frozen_preflight_preserves_values_and_stable_fingerprint(tmp_path):
    source, skills = frozen_runs(tmp_path)
    original = pq.read_table(source / "jobs_analysis.parquet").to_pylist()
    result = preflight(source, skills, allow_unpinned_fixture=True)
    assert result.report["counts"] == {
        "jobs": 2,
        "skill_pairs": 1,
        "jobs_with_skills": 1,
        "jobs_without_skills": 1,
        "industry_labels": 1,
    }
    assert (
        result.report["input_fingerprint"]
        == preflight(source, skills, allow_unpinned_fixture=True).report["input_fingerprint"]
    )
    assert pq.read_table(source / "jobs_analysis.parquet").to_pylist() == original
    (skills / "freeze_receipt.json").write_text("changed")
    with pytest.raises(ValueError, match="changed after"):
        result.check_unchanged()


@pytest.mark.parametrize(
    "changes",
    [
        {"salary_min": Decimal("-1")},
        {"salary_max": Decimal("NaN")},
        {"salary_min": Decimal("3.001")},
        {"experience_min_years": Decimal("0.083333")},
        {"experience_max_years": Decimal("10000")},
        {"salary_min": Decimal("13000000")},
        {"location": []},
        {"location": [None]},
        {"location": [["Hà Nội"]]},
        {"requirements": "Có\x00ký tự lỗi"},
        {"job_title": " "},
        {"year": 2027},
    ],
)
def test_sql_projection_rejects_loss_or_invalid_values(changes):
    with pytest.raises(ValueError):
        validate_job(job(**changes))


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"jobs": [job(), job()]}, "Duplicate"),
        ({"pairs": [{"job_id": 999, "skill_code": "excel", "skill_name": "Excel"}]}, "Orphan"),
        (
            {
                "pairs": [
                    {"job_id": 1, "skill_code": "x", "skill_name": "A"},
                    {"job_id": 1, "skill_code": "x", "skill_name": "A"},
                ]
            },
            "Duplicate",
        ),
        (
            {
                "pairs": [
                    {"job_id": 1, "skill_code": "x", "skill_name": "A"},
                    {"job_id": 2, "skill_code": "x", "skill_name": "B"},
                ]
            },
            "Conflicting",
        ),
        ({"status_changes": {"status": "needs_review"}}, "pending review"),
        ({"status_changes": {"positive_skill_count": 10}}, "count mismatch"),
        ({"status_changes": {"requirements_text_hash": "wrong"}}, "text/count"),
    ],
)
def test_invalid_frozen_populations(tmp_path, kwargs, match):
    source, skills = frozen_runs(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=match):
        preflight(source, skills, allow_unpinned_fixture=True)


def test_modified_artifact_and_receipt_rejected(tmp_path):
    source, skills = frozen_runs(tmp_path)
    (skills / "technical_audit.json").write_text("{}")
    with pytest.raises(ValueError, match="SHA mismatch"):
        preflight(source, skills, allow_unpinned_fixture=True)


def test_cli_has_no_fixture_bypass_or_loading_command(tmp_path):
    source, skills = frozen_runs(tmp_path)
    assert (
        main(
            [
                "silver",
                "db-preflight",
                "--jobs-run",
                str(source),
                "--skills-run",
                str(skills),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "out").exists()


def test_different_s4_snapshot_rejected_even_if_receipts_valid(tmp_path):
    source, skills = frozen_runs(tmp_path)
    p = skills / "manifest.json"
    doc = json.loads(p.read_text())
    doc["input_hashes"][str((source / "jobs_analysis.parquet").resolve())] = "0" * 64
    write_json(p, doc)
    reseal(skills)
    with pytest.raises(ValueError, match="different S4 snapshot"):
        preflight(source, skills, allow_unpinned_fixture=True)


@pytest.mark.parametrize("kind", ["missing", "duplicate"])
def test_status_population_not_merely_row_count(tmp_path, kind):
    source, skills = frozen_runs(tmp_path)
    p = skills / "job_skill_status.parquet"
    rows = pq.read_table(p).to_pylist()
    rows = rows[:1] if kind == "missing" else [rows[0], rows[0]]
    pq.write_table(pa.Table.from_pylist(rows, schema=ARTIFACT_SCHEMAS[p.name]), p)
    reseal(skills)
    with pytest.raises(ValueError, match="population|status/ID"):
        preflight(source, skills, allow_unpinned_fixture=True)


def test_full_jobs_schema_is_required(tmp_path):
    source, skills = frozen_runs(tmp_path)
    p = source / "jobs_analysis.parquet"
    table = pq.read_table(p).drop(["job_type"])
    pq.write_table(table, p)
    doc = json.loads((source / "manifest.json").read_text())
    doc["artifacts"][p.name]["sha256"] = file_sha256(p)
    write_json(source / "manifest.json", doc)
    doc = json.loads((skills / "manifest.json").read_text())
    doc["input_hashes"] = {str(p.resolve()): file_sha256(p) for p in source.iterdir()}
    write_json(skills / "manifest.json", doc)
    reseal(skills)
    with pytest.raises(ValueError, match="full jobs schema"):
        preflight(source, skills, allow_unpinned_fixture=True)
