"""Small synthetic frozen S4/S5 bundles shared by database tests."""

import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.database.preflight import JOBS_SCHEMA
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
