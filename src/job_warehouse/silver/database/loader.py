"""COPY to temporary tables and publish both Silver tables atomically."""

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from job_warehouse.bronze.database import RegistryConnection
from job_warehouse.bronze.registry import require_idle_connection
from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.database.migration import MIGRATION_VERSION, migration_sha256
from job_warehouse.silver.database.preflight import PreflightResult, preflight
from job_warehouse.silver.database.projection import JOB_COLUMNS, SKILL_COLUMNS, parquet_rows
from job_warehouse.skills.input import json_text

VERSION = "silver-transactional-loader-v1"
WRITER_LOCK = 1976030102
STAGE_JOBS = "pg_temp._s6_jobs"
STAGE_SKILLS = "pg_temp._s6_skills"


@dataclass(frozen=True)
class PreparedLoad:
    jobs: Path
    skills: Path
    verified: PreflightResult
    code_hashes: dict[Path, str]
    fingerprint: str

    def check_unchanged(self) -> None:
        self.verified.check_unchanged()
        if any(file_sha256(p) != h for p, h in self.code_hashes.items()):
            raise ValueError("Silver loader code changed during load")


def prepare_load(
    jobs_run: Path, skills_run: Path, *, allow_unpinned_fixture: bool = False
) -> PreparedLoad:
    verified = preflight(jobs_run, skills_run, allow_unpinned_fixture=allow_unpinned_fixture)
    root = Path(__file__).parent
    assets = {
        root / name: file_sha256(root / name)
        for name in (
            "loader.py",
            "projection.py",
            "preflight.py",
            "migration.py",
            "migrations/001_silver.sql",
        )
    }
    components = {
        "version": VERSION,
        "preflight_fingerprint": verified.report["input_fingerprint"],
        "loader_hashes": {p.name: h for p, h in assets.items()},
        "fixture_only": allow_unpinned_fixture,
    }
    return PreparedLoad(
        jobs_run.resolve() / "jobs_analysis.parquet",
        skills_run.resolve() / "job_skill_match.parquet",
        verified,
        assets,
        hashlib.sha256(json_text(components).encode()).hexdigest(),
    )


def _table(name: str) -> sql.Identifier:
    if name not in {STAGE_JOBS, STAGE_SKILLS, "silver.jobs", "silver.job_skill_match"}:
        raise ValueError("Unexpected Silver table")
    return sql.Identifier(*name.split("."))


def _check_columns(conn: RegistryConnection, *, staging: bool = False) -> None:
    """The migration ledger alone cannot detect manual type/column changes."""
    job_types = (
        "bigint",
        "character varying",
        "character varying",
        "numeric(18,2)",
        "numeric(18,2)",
        "character varying[]",
        "character varying",
        "character varying",
        "numeric(6,2)",
        "numeric(6,2)",
        "character varying",
        "character varying",
        "text",
        "smallint",
    )
    for table, columns, types, required in [
        (
            STAGE_JOBS if staging else "silver.jobs",
            JOB_COLUMNS,
            job_types,
            {"id", "job_title", "location", "job_industry", "year"},
        ),
        (
            STAGE_SKILLS if staging else "silver.job_skill_match",
            SKILL_COLUMNS,
            ("bigint", "character varying", "character varying"),
            set(SKILL_COLUMNS),
        ),
    ]:
        actual = conn.execute(
            "SELECT attname,format_type(atttypid,atttypmod) AS kind,attnotnull "
            "FROM pg_attribute WHERE attrelid=to_regclass(%s) "
            "AND attnum>0 AND NOT attisdropped ORDER BY attnum",
            (table,),
        ).fetchall()
        expected = [(n, t, n in required) for n, t in zip(columns, types, strict=True)]
        if [(r["attname"], r["kind"], r["attnotnull"]) for r in actual] != expected:
            raise ValueError(f"Silver schema drift detected: {table}")


def _checkpoint(event: str, conn: RegistryConnection) -> None:
    """Fault-injection boundary for offline integration tests; no runtime action."""


def _copy(
    conn: RegistryConnection, path: Path, table: str, *, skills: bool, batch_size: int
) -> None:
    columns = SKILL_COLUMNS if skills else JOB_COLUMNS
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        _table(table), sql.SQL(",").join(map(sql.Identifier, columns))
    )
    with conn.cursor().copy(statement) as copy:
        for row in parquet_rows(path, skills=skills, batch_size=batch_size):
            copy.write_row(row)


def table_counts(conn: RegistryConnection, *, staging: bool = False) -> dict[str, int]:
    jobs = _table(STAGE_JOBS if staging else "silver.jobs")
    skills = _table(STAGE_SKILLS if staging else "silver.job_skill_match")
    row = conn.execute(
        sql.SQL(
            "SELECT (SELECT count(*) FROM {}) AS jobs, "
            "(SELECT count(*) FROM {}) AS skill_pairs, "
            "(SELECT count(DISTINCT job_id) FROM {}) AS jobs_with_skills, "
            "(SELECT count(DISTINCT job_industry) FROM {}) AS industry_labels"
        ).format(jobs, skills, skills, jobs)
    ).fetchone()
    assert row is not None
    counts = {name: int(value) for name, value in row.items()}
    counts["jobs_without_skills"] = counts["jobs"] - counts["jobs_with_skills"]
    return counts


def _equal(conn: RegistryConnection) -> bool:
    """Compare every field in both directions; counts alone cannot detect drift."""
    for live, stage, columns in [
        ("silver.jobs", STAGE_JOBS, JOB_COLUMNS),
        ("silver.job_skill_match", STAGE_SKILLS, SKILL_COLUMNS),
    ]:
        fields = sql.SQL(",").join(map(sql.Identifier, columns))
        row = conn.execute(
            sql.SQL(
                "SELECT EXISTS ((SELECT {} FROM {} EXCEPT ALL SELECT {} FROM {}) "
                "UNION ALL (SELECT {} FROM {} EXCEPT ALL SELECT {} FROM {})) AS differs"
            ).format(
                fields,
                _table(live),
                fields,
                _table(stage),
                fields,
                _table(stage),
                fields,
                _table(live),
            )
        ).fetchone()
        assert row is not None
        if row["differs"]:
            return False
    return True


def _stage(conn: RegistryConnection, prepared: PreparedLoad, batch_size: int) -> None:
    with conn.transaction():
        conn.execute("CREATE TEMP TABLE _s6_jobs (LIKE silver.jobs INCLUDING ALL)")
        conn.execute("CREATE TEMP TABLE _s6_skills (LIKE silver.job_skill_match INCLUDING ALL)")
        _check_columns(conn, staging=True)
        _copy(conn, prepared.jobs, STAGE_JOBS, skills=False, batch_size=batch_size)
        _checkpoint("after_jobs_copy", conn)
        _copy(conn, prepared.skills, STAGE_SKILLS, skills=True, batch_size=batch_size)
        orphan = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_temp._s6_skills s "
            "LEFT JOIN pg_temp._s6_jobs j ON j.id=s.job_id WHERE j.id IS NULL) AS bad"
        ).fetchone()
        names = conn.execute(
            "SELECT EXISTS(SELECT skill_code FROM pg_temp._s6_skills GROUP BY skill_code "
            "HAVING count(DISTINCT skill_name)>1) AS bad"
        ).fetchone()
        if orphan is None or names is None or orphan["bad"] or names["bad"]:
            raise ValueError("Staging skill FK/name mismatch")
        if table_counts(conn, staging=True) != prepared.verified.report["counts"]:
            raise ValueError("Staging population mismatch")
        prepared.check_unchanged()
    _checkpoint("after_stage", conn)


def _finish(
    conn: RegistryConnection,
    run_id: UUID,
    counts: dict[str, int],
    *,
    current: bool,
    operation: str,
    current_run_id: str,
) -> None:
    updated = conn.execute(
        "UPDATE ops.silver_load_run SET status='published', actual_counts=%s, "
        "finished_at=clock_timestamp(), is_current=%s, "
        "input_manifest=input_manifest || jsonb_build_object('operation',%s::text, "
        "'current_run_id',%s::text) "
        "WHERE run_id=%s AND status='running'",
        (Jsonb(counts), current, operation, current_run_id, run_id),
    )

    if updated.rowcount != 1:
        raise ValueError("Load attempt no longer running; publication rolled back")


def _publish(conn: RegistryConnection, prepared: PreparedLoad, run_id: UUID) -> dict[str, Any]:
    expected = prepared.verified.report["counts"]
    with conn.transaction():
        # Block uncoordinated INSERT/UPDATE/DELETE too; readers can still SELECT.
        conn.execute("SET LOCAL lock_timeout = '10s'")
        conn.execute("LOCK TABLE silver.jobs, silver.job_skill_match IN SHARE ROW EXCLUSIVE MODE")
        _check_columns(conn)
        current = conn.execute(
            "SELECT run_id,input_fingerprint FROM ops.silver_load_run WHERE is_current FOR UPDATE"
        ).fetchone()
        same_input = current is not None and current["input_fingerprint"] == prepared.fingerprint
        identical = _equal(conn) if same_input else False
        prepared.check_unchanged()
        if identical:
            operation = "verified_noop"
            current_id = str(current["run_id"]) if current else str(run_id)
            _finish(
                conn,
                run_id,
                expected,
                current=False,
                operation=operation,
                current_run_id=current_id,
            )
        else:
            operation = "republished_after_content_drift" if same_input else "published"
            conn.execute("DELETE FROM silver.job_skill_match")
            conn.execute("DELETE FROM silver.jobs")
            _checkpoint("after_delete", conn)
            conn.execute("INSERT INTO silver.jobs SELECT * FROM pg_temp._s6_jobs")
            _checkpoint("after_jobs_insert", conn)
            conn.execute("INSERT INTO silver.job_skill_match SELECT * FROM pg_temp._s6_skills")
            if table_counts(conn) != expected or not _equal(conn):
                raise ValueError("Published content differs from staging")
            conn.execute("UPDATE ops.silver_load_run SET is_current=false WHERE is_current")
            current_id = str(run_id)
            _finish(
                conn, run_id, expected, current=True, operation=operation, current_run_id=current_id
            )
        prepared.check_unchanged()
        _checkpoint("before_commit", conn)
    # A failure here must never downgrade a ledger row that already says published.
    _checkpoint("after_commit", conn)
    return {
        "status": operation,
        "run_id": str(run_id),
        "current_run_id": current_id,
        "input_fingerprint": prepared.fingerprint,
        "loader_version": VERSION,
        "counts": expected,
        "fixture_only": prepared.verified.report["fixture_only"],
        "content_verified_in_publication_transaction": True,
    }


def load_silver(
    conn: RegistryConnection,
    jobs_run: Path,
    skills_run: Path,
    *,
    batch_size: int = 4096,
    run_id: UUID | None = None,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    """Preflight before DB mutation; one attempt, one writer, one atomic publication.

    Exceptions after commit are ambiguous to the caller: consult the run ledger.
    A disconnected/crashed running attempt is closed by the next lock holder.
    No-op checks content and records verification without moving the current marker.
    """
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    require_idle_connection(conn)
    prepared = prepare_load(jobs_run, skills_run, allow_unpinned_fixture=allow_unpinned_fixture)
    schema = conn.execute(
        "SELECT sha256 FROM warehouse_meta.schema_migration WHERE version=%s", (MIGRATION_VERSION,)
    ).fetchone()
    if schema is None or schema["sha256"] != migration_sha256():
        raise ValueError("Apply and verify the Silver migration before loading")
    acquired = conn.execute(
        "SELECT pg_try_advisory_lock(%s) AS acquired", (WRITER_LOCK,)
    ).fetchone()
    if acquired is None or not acquired["acquired"]:
        raise ValueError("Another Silver writer is running; retry after it finishes")
    ident = run_id or uuid4()
    started = False
    try:
        # This connection is now the sole cooperative writer. Any older running attempt
        # has lost its session lock, so it cannot later commit publication through this loader.
        with conn.transaction():
            conn.execute(
                "UPDATE ops.silver_load_run SET status='failed',finished_at=clock_timestamp(), "
                'input_manifest=input_manifest || \'{"failure_kind":"abandoned_session"}\'::jsonb '
                "WHERE status='running'"
            )
            conn.execute(
                "INSERT INTO ops.silver_load_run (run_id,input_fingerprint,input_manifest,"
                "loader_version,status,expected_counts) VALUES (%s,%s,%s,%s,'running',%s)",
                (
                    ident,
                    prepared.fingerprint,
                    Jsonb(
                        {
                            "preflight": prepared.verified.report,
                            "loader_hashes": {p.name: h for p, h in prepared.code_hashes.items()},
                        }
                    ),
                    VERSION,
                    Jsonb(prepared.verified.report["counts"]),
                ),
            )
        started = True
        _check_columns(conn)
        _stage(conn, prepared, batch_size)
        return _publish(conn, prepared, ident)
    except BaseException as exc:
        if started and not conn.closed:
            # Preserve the original error; the next lock holder can close a lost session.
            with suppress(psycopg.Error):
                conn.execute(
                    "UPDATE ops.silver_load_run SET status='failed',finished_at=clock_timestamp(), "
                    "input_manifest=input_manifest || jsonb_build_object('failure_kind',%s::text) "
                    "WHERE run_id=%s AND status='running'",
                    (type(exc).__name__, ident),
                )
        raise
    finally:
        if not conn.closed:
            try:
                conn.execute("DROP TABLE IF EXISTS pg_temp._s6_skills, pg_temp._s6_jobs")
                conn.execute("SELECT pg_advisory_unlock(%s)", (WRITER_LOCK,))
            except psycopg.Error:
                # Closing the session releases temporary tables and its advisory lock.
                # Cleanup errors must not obscure the authoritative publication outcome.
                conn.close()
