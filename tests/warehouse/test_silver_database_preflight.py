"""Synthetic frozen inputs exercise validation without real data or PostgreSQL."""

import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from job_warehouse.cli import main
from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.database.preflight import JOBS_SCHEMA, preflight, validate_job
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS


def job(**changes):
    return {
        "id": 1,
        "job_title": "Kế toán 👩‍💻",
        "company_name": None,
        "salary_min": None,
        "salary_max": Decimal("12000000.00"),
        "location": ["Hà Nội", "Bình Dương"],
        "job_type": "Toàn thời gian, Remote",
        "job_industry": "Kế toán / Kiểm toán",
        "experience_min_years": Decimal("0.200000"),
        "experience_max_years": None,
        "education_level": "Đại học",
        "job_position": None,
        "requirements": 'Biết Excel, "Word"\nKhông sửa nội dung {a,b}',
        "year": 2026,
        **changes,
    }


def write_json(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False))


def frozen_runs(tmp_path, *, jobs=None, pairs=None, status_changes=None):
    source, skills = tmp_path / "s4", tmp_path / "s5"
    source.mkdir()
    skills.mkdir()
    jobs = jobs if jobs is not None else [job(), job(id=2, requirements=None)]
    pq.write_table(pa.Table.from_pylist(jobs, schema=JOBS_SCHEMA), source / "jobs_analysis.parquet")
    provenance = {"revision": "fixture", "pinned_artifact_verified": False}
    write_json(
        source / "manifest.json",
        {
            "source": provenance,
            "partition": {"analysis": len(jobs)},
            "artifacts": {
                "jobs_analysis.parquet": {"sha256": file_sha256(source / "jobs_analysis.parquet")}
            },
        },
    )
    pairs = (
        pairs
        if pairs is not None
        else [{"job_id": 1, "skill_code": "excel", "skill_name": "Excel"}]
    )
    statuses = [
        {
            "job_id": j["id"],
            "job_industry": j["job_industry"],
            "year": j["year"],
            "requirements_text_hash": text_hash(j["requirements"]) if j["requirements"] else None,
            "status": "processed_match" if j["id"] == 1 else "missing_requirements",
            "positive_skill_count": sum(p["job_id"] == j["id"] for p in pairs),
            "evidence_count": 0,
            "reasons": [],
            **(status_changes or {}),
        }
        for j in jobs
    ]
    data = {
        "job_skill_match.parquet": pairs,
        "job_skill_status.parquet": statuses,
        "job_skill_evidence.parquet": [],
    }
    for name, schema in ARTIFACT_SCHEMAS.items():
        pq.write_table(pa.Table.from_pylist(data[name], schema=schema), skills / name)
    write_json(
        skills / "manifest.json",
        {
            "source": provenance,
            "input_hashes": {str(p.resolve()): file_sha256(p) for p in source.iterdir()},
            "artifacts": {n: {"sha256": file_sha256(skills / n)} for n in data},
        },
    )
    write_json(skills / "owner_decision.json", {"decision": "fixture"})
    for n, status in [
        ("technical_audit.json", "passed_full_source_pair_evidence_audit"),
        ("replay_check.json", "passed_identical_three_parquet_sha256"),
    ]:
        write_json(skills / n, {"status": status})
    write_json(
        skills / "completion.json",
        {
            "status": "accepted_owner_clear_keywords_or_skip",
            "proof_hashes": {
                str(skills / "owner_decision.json"): file_sha256(skills / "owner_decision.json")
            },
        },
    )
    sha = file_sha256(skills / "manifest.json")
    audit_sha = file_sha256(skills / "technical_audit.json")
    complete_sha = file_sha256(skills / "completion.json")
    write_json(
        skills / "freeze_receipt.json",
        {
            "status": "frozen_offline_review_closure",
            "run_manifest_sha256": sha,
            "needs_review_jobs": 0,
            "technical_audit_sha256": audit_sha,
            "replay_check_sha256": file_sha256(skills / "replay_check.json"),
            "gate_path": str(skills / "completion.json"),
            "gate_sha256": complete_sha,
            "total_skill_pairs": len(pairs),
            "total_jobs_with_skills": len({p["job_id"] for p in pairs}),
        },
    )
    write_json(
        skills / "acceptance.json",
        {
            "status": "accepted_closure_offline_not_db_published",
            "manifest_sha256": sha,
            "technical_audit_sha256": audit_sha,
            "completion_path": str(skills / "completion.json"),
            "completion_sha256": complete_sha,
        },
    )
    write_json(skills / "checksums.json", {p.name: file_sha256(p) for p in skills.iterdir()})
    return source, skills


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


def reseal(skills):
    """Rebind synthetic receipts, so tests reach semantic checks beyond SHA validation."""
    p = skills / "manifest.json"
    manifest = json.loads(p.read_text())
    for name in ARTIFACT_SCHEMAS:
        manifest["artifacts"][name]["sha256"] = file_sha256(skills / name)
    write_json(p, manifest)
    for name, key in [
        ("freeze_receipt.json", "run_manifest_sha256"),
        ("acceptance.json", "manifest_sha256"),
    ]:
        p = skills / name
        doc = json.loads(p.read_text())
        doc[key] = file_sha256(skills / "manifest.json")
        write_json(p, doc)
    write_json(
        skills / "checksums.json",
        {p.name: file_sha256(p) for p in skills.iterdir() if p.name != "checksums.json"},
    )


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
