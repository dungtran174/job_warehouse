"""Read every published value back under one snapshot and compare with frozen Parquet."""

import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from psycopg import sql

from job_warehouse.bronze.database import RegistryConnection
from job_warehouse.bronze.registry import require_idle_connection
from job_warehouse.silver.database.loader import _check_columns, prepare_load, table_counts
from job_warehouse.silver.database.projection import JOB_COLUMNS, SKILL_COLUMNS, parquet_rows

VERSION = "silver-full-readback-v1"


def _decimal_json(value: Any) -> dict[str, str]:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Invalid verification value")
    rounded = value.quantize(Decimal("0.01"))
    if value != rounded:
        raise ValueError("Verification cannot round numeric values")
    return {"decimal": format(rounded, "f")}


def field_hashes(values: tuple[Any, ...]) -> bytes:
    """Fixed 32-byte SHA per typed field, retaining NULL, text and array order."""
    return b"".join(
        hashlib.sha256(
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                default=_decimal_json,
            ).encode("utf-8")
        ).digest()
        for value in values
    )


def _source_index(
    index: sqlite3.Connection, jobs: Path, skills: Path, batch_size: int
) -> dict[str, Any]:
    index.executescript("""
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, fields BLOB, seen INTEGER DEFAULT 0);
        CREATE TABLE skills (job_id INTEGER, code TEXT, fields BLOB, seen INTEGER DEFAULT 0,
            PRIMARY KEY(job_id,code));
    """)
    nulls: Counter[str] = Counter(dict.fromkeys(JOB_COLUMNS, 0))
    years: Counter[int] = Counter()
    industries: Counter[str] = Counter()
    for row in parquet_rows(jobs, batch_size=batch_size):
        index.execute("INSERT INTO jobs(id,fields) VALUES (?,?)", (row[0], field_hashes(row)))
        nulls.update(n for n, v in zip(JOB_COLUMNS, row, strict=True) if v is None)
        years[row[-1]] += 1
        industries[row[JOB_COLUMNS.index("job_industry")]] += 1
    for row in parquet_rows(skills, skills=True, batch_size=batch_size):
        index.execute(
            "INSERT INTO skills(job_id,code,fields) VALUES (?,?,?)",
            (row[0], row[1], field_hashes(row)),
        )
    return {"null_counts": dict(nulls), "by_year": dict(years), "by_industry": dict(industries)}


def _compare(
    conn: RegistryConnection, index: sqlite3.Connection, *, skills: bool, batch_size: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    name = "skills" if skills else "jobs"
    table = "job_skill_match" if skills else "jobs"
    columns = SKILL_COLUMNS if skills else JOB_COLUMNS
    key_predicate = "job_id=? AND code=?" if skills else "id=?"
    order = 'job_id,skill_code COLLATE "C"' if skills else "id"
    source_order = "job_id,code" if skills else "id"
    source_count = index.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    source_digest = hashlib.sha256()
    for (fields,) in index.execute(f"SELECT fields FROM {name} ORDER BY {source_order}"):
        source_digest.update(fields)
    actual_digest = hashlib.sha256()
    modified = extra = duplicate = actual_count = 0
    changed_fields: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    nulls: Counter[str] = Counter(dict.fromkeys(columns, 0))
    years: Counter[int] = Counter()
    industries: Counter[str] = Counter()
    with conn.cursor(name="silver_verify_" + uuid4().hex) as cursor:
        cursor.itersize = batch_size
        cursor.execute(
            sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
                sql.SQL(",").join(map(sql.Identifier, columns)),
                sql.Identifier("silver", table),
                sql.SQL(order),
            )
        )
        for row in cursor:
            values = tuple(row[c] for c in columns)
            key = values[:2] if skills else values[:1]
            fields = field_hashes(values)
            actual_digest.update(fields)
            actual_count += 1
            expected = index.execute(
                f"SELECT fields,seen FROM {name} WHERE {key_predicate}", key
            ).fetchone()
            differences = []
            if expected is None:
                extra += 1
            elif expected[1]:
                duplicate += 1
            else:
                index.execute(f"UPDATE {name} SET seen=1 WHERE {key_predicate}", key)
                if fields != expected[0]:
                    modified += 1
                    differences = [
                        c
                        for i, c in enumerate(columns)
                        if fields[i * 32 : (i + 1) * 32] != expected[0][i * 32 : (i + 1) * 32]
                    ]
                    changed_fields.update(differences)
            if (expected is None or expected[1] or differences) and len(samples) < 20:
                samples.append({"key": list(key), "different_fields": differences})
            if not skills:
                nulls.update(c for c, v in row.items() if v is None)
                years[row["year"]] += 1
                industries[row["job_industry"]] += 1
    missing = index.execute(f"SELECT count(*) FROM {name} WHERE seen=0").fetchone()[0]
    source_sha, actual_sha = source_digest.hexdigest(), actual_digest.hexdigest()
    result = {
        "source_rows": source_count,
        "database_rows": actual_count,
        "missing_rows": missing,
        "extra_rows": extra,
        "duplicate_rows": duplicate,
        "modified_rows": modified,
        "different_field_counts": dict(changed_fields),
        "source_content_sha256": source_sha,
        "database_content_sha256": actual_sha,
        "matches": not (missing or extra or duplicate or modified) and source_sha == actual_sha,
        "mismatch_samples": samples,
    }
    return result, {
        "null_counts": dict(nulls),
        "by_year": dict(years),
        "by_industry": dict(industries),
    }


def verify_publication(
    conn: RegistryConnection,
    jobs_run: Path,
    skills_run: Path,
    *,
    batch_size: int = 4096,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    """No business DB writes; an ephemeral local index contains keys/hashes, never job text."""
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    require_idle_connection(conn)
    prepared = prepare_load(jobs_run, skills_run, allow_unpinned_fixture=allow_unpinned_fixture)
    with (
        tempfile.TemporaryDirectory(prefix="silver-verify-") as tmp,
        sqlite3.connect(Path(tmp) / "hashes.sqlite") as index,
    ):
        expected_stats = _source_index(index, prepared.jobs, prepared.skills, batch_size)
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            _check_columns(conn)
            current = conn.execute(
                "SELECT run_id,input_fingerprint,status,expected_counts,actual_counts "
                "FROM ops.silver_load_run WHERE is_current"
            ).fetchall()
            jobs, actual_stats = _compare(conn, index, skills=False, batch_size=batch_size)
            skills, _ = _compare(conn, index, skills=True, batch_size=batch_size)
            counts = table_counts(conn)
            checks = conn.execute("""
                SELECT (SELECT count(*) FROM silver.job_skill_match s LEFT JOIN silver.jobs j
                        ON j.id=s.job_id WHERE j.id IS NULL) AS orphan_skill_pairs,
                       (SELECT count(*) FROM (SELECT skill_code FROM silver.job_skill_match
                        GROUP BY skill_code HAVING count(DISTINCT skill_name)>1) q)
                        AS conflicting_skill_names
            """).fetchone()
            ledger_ok = len(current) == 1 and all(
                (
                    current[0]["input_fingerprint"] == prepared.fingerprint,
                    current[0]["status"] == "published",
                    current[0]["expected_counts"] == prepared.verified.report["counts"],
                    current[0]["actual_counts"] == counts,
                )
            )
            sizes = conn.execute("""
                SELECT pg_database_size(current_database()) AS database_bytes,
                       pg_total_relation_size('silver.jobs') AS jobs_bytes,
                       pg_total_relation_size('silver.job_skill_match') AS skills_bytes,
                       pg_total_relation_size('ops.silver_load_run') AS load_ledger_bytes
            """).fetchone()
        prepared.check_unchanged()
    passed = all(
        (
            jobs["matches"],
            skills["matches"],
            ledger_ok,
            expected_stats == actual_stats,
            counts == prepared.verified.report["counts"],
            checks is not None and all(v == 0 for v in checks.values()),
        )
    )
    return {
        "status": "passed_full_readback" if passed else "failed_full_readback",
        "verification_version": VERSION,
        "fixture_only": allow_unpinned_fixture,
        "input_fingerprint": prepared.fingerprint,
        "publication_run_id": str(current[0]["run_id"]) if len(current) == 1 else None,
        "current_ledger_matches": ledger_ok,
        "counts": counts,
        "jobs": jobs,
        "skills": skills,
        "expected_distributions": expected_stats,
        "database_distributions": actual_stats,
        "integrity": checks,
        "database_sizes": sizes,
        "source_files_unchanged": True,
        "read_only_repeatable_snapshot": True,
    }
