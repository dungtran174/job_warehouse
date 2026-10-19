"""Read-only checks of frozen S4/S5 files before any database mutation."""

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.database.migration import migration_sha256
from job_warehouse.skills.expansion_merge import checked_artifacts
from job_warehouse.skills.input import json_text, verify_jobs_run
from job_warehouse.skills.profile import text_hash

VERSION = "silver-preflight-v1"
JOBS_SCHEMA = pa.schema(
    [
        ("id", pa.int64()),
        ("job_title", pa.string()),
        ("company_name", pa.string()),
        ("salary_min", pa.decimal128(18, 2)),
        ("salary_max", pa.decimal128(18, 2)),
        ("location", pa.list_(pa.string())),
        ("job_type", pa.string()),
        ("job_industry", pa.string()),
        ("experience_min_years", pa.decimal128(18, 6)),
        ("experience_max_years", pa.decimal128(18, 6)),
        ("education_level", pa.string()),
        ("job_position", pa.string()),
        ("requirements", pa.string()),
        ("year", pa.int16()),
    ]
)


@dataclass(frozen=True)
class PreflightResult:
    report: dict[str, Any]
    hashes: dict[Path, str]

    def check_unchanged(self) -> None:
        if any(file_sha256(p) != h for p, h in self.hashes.items()):
            raise ValueError("Silver input changed after preflight")


def _document(path: Path, tracked: dict[Path, str]) -> dict[str, Any]:
    path = path.resolve()
    tracked[path] = file_sha256(path)
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def _bound_file(path: Path, expected: str, tracked: dict[Path, str]) -> None:
    path = path.resolve()
    tracked[path] = file_sha256(path)
    if tracked[path] != expected:
        raise ValueError(f"Receipt SHA mismatch: {path.name}")


def _acceptance(run: Path, tracked: dict[Path, str]) -> dict[str, Any]:
    receipt = _document(run / "freeze_receipt.json", tracked)
    acceptance = _document(run / "acceptance.json", tracked)
    manifest_sha = tracked[(run / "manifest.json").resolve()]
    if (
        receipt.get("status") != "frozen_offline_review_closure"
        or receipt.get("run_manifest_sha256") != manifest_sha
        or acceptance.get("status") != "accepted_closure_offline_not_db_published"
        or acceptance.get("manifest_sha256") != manifest_sha
        or receipt.get("needs_review_jobs") != 0
    ):
        raise ValueError("S5 closure acceptance/receipt mismatch")
    for document, fields in [
        (
            receipt,
            [
                ("technical_audit.json", "technical_audit_sha256"),
                ("replay_check.json", "replay_check_sha256"),
            ],
        ),
        (acceptance, [("technical_audit.json", "technical_audit_sha256")]),
    ]:
        for name, key in fields:
            _bound_file(run / name, document[key], tracked)
    for document, path_key, sha_key in [
        (receipt, "gate_path", "gate_sha256"),
        (acceptance, "completion_path", "completion_sha256"),
    ]:
        _bound_file(Path(document[path_key]), document[sha_key], tracked)
    gate = _document(Path(receipt["gate_path"]), tracked)
    if gate.get("status") != "accepted_owner_clear_keywords_or_skip" or not gate.get(
        "proof_hashes"
    ):
        raise ValueError("S5 completion gate is not accepted")
    for name, sha in gate["proof_hashes"].items():
        _bound_file(Path(name), sha, tracked)
    audit = _document(run / "technical_audit.json", tracked)
    replay = _document(run / "replay_check.json", tracked)
    if (
        audit.get("status") != "passed_full_source_pair_evidence_audit"
        or replay.get("status") != "passed_identical_three_parquet_sha256"
    ):
        raise ValueError("S5 audit/replay gate is not passed")
    checksums = _document(run / "checksums.json", tracked)
    required = {
        "manifest.json",
        "acceptance.json",
        "freeze_receipt.json",
        "technical_audit.json",
        "replay_check.json",
        "job_skill_match.parquet",
        "job_skill_status.parquet",
        "job_skill_evidence.parquet",
    }
    if not required <= checksums.keys():
        raise ValueError("Incomplete S5 checksums")
    for name, sha in checksums.items():
        path = (run / name).resolve()
        if not path.is_relative_to(run.resolve()):
            raise ValueError("Unsafe checksums path")
        _bound_file(path, sha, tracked)
    return receipt


def _text(value: Any, field: str, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or "\x00" in value or (required and not value.strip()):
        raise ValueError(f"Invalid SQL text: {field}")
    value.encode("utf-8", errors="strict")


def _decimal(value: Any, precision: int, field: str) -> None:
    if value is None:
        return
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value < 0
        or value >= Decimal(10) ** (precision - 2)
        or value != value.quantize(Decimal("0.01"))
    ):
        raise ValueError(f"Lossy or invalid numeric conversion: {field}")


def validate_job(row: dict[str, Any]) -> None:
    """Validate target SQL representation without normalizing or changing values."""
    if type(row["id"]) is not int or not 0 < row["id"] < 2**63:
        raise ValueError("Invalid job ID")
    if type(row["year"]) is not int or row["year"] not in range(2022, 2027):
        raise ValueError("Invalid source year")
    for name in (
        "job_title",
        "job_industry",
        "company_name",
        "job_type",
        "education_level",
        "job_position",
        "requirements",
    ):
        _text(row[name], name, required=name in {"job_title", "job_industry"})
    locations = row["location"]
    if not isinstance(locations, list) or not locations:
        raise ValueError("Invalid location array")
    for location in locations:
        _text(location, "location", required=True)
    for prefix, precision in [("salary", 18), ("experience", 6)]:
        names = (
            ["salary_min", "salary_max"]
            if prefix == "salary"
            else ["experience_min_years", "experience_max_years"]
        )
        low, high = (row[n] for n in names)
        for name in names:
            _decimal(row[name], precision, name)
        if low is not None and high is not None and low > high:
            raise ValueError(f"Reversed {prefix} bounds")


def preflight(
    jobs_run: Path, skills_run: Path, *, allow_unpinned_fixture: bool = False
) -> PreflightResult:
    """Check all jobs/pairs/statuses, frozen evidence hashes and exact S4 lineage.

    The fixture escape hatch is only a Python test API; the CLI always pins production.
    No files, pointers, database rows or extracted skills are changed.
    """
    jobs_run, skills_run = jobs_run.resolve(), skills_run.resolve()
    source = verify_jobs_run(jobs_run, allow_unpinned_fixture=allow_unpinned_fixture)
    manifest, tracked = checked_artifacts(skills_run)
    tracked = {p.resolve(): h for p, h in {**tracked, **source.hashes}.items()}
    receipt = _acceptance(skills_run, tracked)
    for path, sha in source.hashes.items():
        if manifest["input_hashes"].get(str(path.resolve())) != sha:
            raise ValueError("S5 uses a different S4 snapshot")
    if manifest.get("source") != source.manifest["source"]:
        raise ValueError("S4/S5 source provenance mismatch")
    with pq.ParquetFile(source.parquet) as parquet:
        if parquet.schema_arrow != JOBS_SCHEMA:
            raise ValueError("S4 full jobs schema mismatch")
    industries: Counter[str] = Counter()
    nulls: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    # A bounded per-run in-memory index; never touches a production database.
    with sqlite3.connect(":memory:") as index:
        index.executescript("""
            CREATE TABLE jobs (id INTEGER PRIMARY KEY, industry TEXT, year INTEGER,
                req_hash TEXT, actual_pairs INTEGER NOT NULL DEFAULT 0, seen INTEGER DEFAULT 0);
            CREATE TABLE names (code TEXT PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE pairs (id INTEGER, code TEXT, PRIMARY KEY(id, code));
        """)
        try:
            with pq.ParquetFile(source.parquet) as parquet:
                for batch in parquet.iter_batches(batch_size=4096):
                    for row in batch.to_pylist():
                        validate_job(row)
                        index.execute(
                            "INSERT INTO jobs(id,industry,year,req_hash) VALUES (?,?,?,?)",
                            (
                                row["id"],
                                row["job_industry"],
                                row["year"],
                                text_hash(row["requirements"])
                                if row["requirements"] is not None
                                else None,
                            ),
                        )
                        industries[row["job_industry"]] += 1
                        nulls.update(n for n, v in row.items() if v is None)
            pair_count = 0
            with pq.ParquetFile(skills_run / "job_skill_match.parquet") as parquet:
                for batch in parquet.iter_batches(batch_size=8192):
                    for row in batch.to_pylist():
                        ident, code, name = (row[n] for n in ("job_id", "skill_code", "skill_name"))
                        _text(code, "skill_code", required=True)
                        _text(name, "skill_name", required=True)
                        if (
                            index.execute(
                                "UPDATE jobs SET actual_pairs=actual_pairs+1 WHERE id=?", (ident,)
                            ).rowcount
                            != 1
                        ):
                            raise ValueError("Orphan skill job ID")
                        index.execute("INSERT INTO pairs VALUES (?,?)", (ident, code))
                        old = index.execute(
                            "SELECT name FROM names WHERE code=?", (code,)
                        ).fetchone()
                        if old is not None and old[0] != name:
                            raise ValueError("Conflicting canonical skill names")
                        index.execute("INSERT OR IGNORE INTO names VALUES (?,?)", (code, name))
                        pair_count += 1
            with pq.ParquetFile(skills_run / "job_skill_status.parquet") as parquet:
                for batch in parquet.iter_batches(batch_size=8192):
                    for row in batch.to_pylist():
                        ident = row["job_id"]
                        found = index.execute(
                            "SELECT industry,year,req_hash,actual_pairs,seen FROM jobs WHERE id=?",
                            (ident,),
                        ).fetchone()
                        expected = (
                            row["job_industry"],
                            row["year"],
                            row["requirements_text_hash"],
                            row["positive_skill_count"],
                            0,
                        )
                        if found != expected or row["status"] == "needs_review":
                            raise ValueError("S5 status/ID/text/count mismatch or pending review")
                        index.execute("UPDATE jobs SET seen=1 WHERE id=?", (ident,))
                        statuses[row["status"]] += 1
        except sqlite3.IntegrityError as exc:
            raise ValueError("Duplicate job ID or skill pair") from exc
        total, with_skills, seen = index.execute(
            "SELECT count(*),sum(actual_pairs>0),sum(seen) FROM jobs"
        ).fetchone()
        with_skills, seen = with_skills or 0, seen or 0
        if seen != total or total != source.rows:
            raise ValueError("Incomplete job/status population")
        counts = {
            "jobs": total,
            "skill_pairs": pair_count,
            "jobs_with_skills": with_skills,
            "jobs_without_skills": total - with_skills,
            "industry_labels": len(industries),
        }
        if (receipt["total_skill_pairs"], receipt["total_jobs_with_skills"]) != (
            pair_count,
            with_skills,
        ):
            raise ValueError("Receipt population differs from files")
        if not allow_unpinned_fixture and counts != {
            "jobs": 590693,
            "skill_pairs": 875580,
            "jobs_with_skills": 380984,
            "jobs_without_skills": 209709,
            "industry_labels": 34,
        }:
            raise ValueError("Production population differs from S6 approved input")
    fingerprint_inputs = {
        "version": VERSION,
        "migration_sha256": migration_sha256(),
        "jobs_manifest_sha256": tracked[(jobs_run / "manifest.json").resolve()],
        "skills_manifest_sha256": tracked[(skills_run / "manifest.json").resolve()],
        "jobs_sha256": tracked[source.parquet.resolve()],
        "skill_pairs_sha256": tracked[(skills_run / "job_skill_match.parquet").resolve()],
    }
    result = PreflightResult(
        {
            "status": "passed_preflight_not_db_published",
            "counts": counts,
            "by_industry": dict(sorted(industries.items())),
            "null_counts": dict(sorted(nulls.items())),
            "skill_status_counts": dict(sorted(statuses.items())),
            "fingerprint_components": fingerprint_inputs,
            "input_fingerprint": hashlib.sha256(json_text(fingerprint_inputs).encode()).hexdigest(),
            "input_hashes": {str(p): h for p, h in sorted(tracked.items())},
            "fixture_only": allow_unpinned_fixture,
        },
        tracked,
    )
    result.check_unchanged()
    return result
