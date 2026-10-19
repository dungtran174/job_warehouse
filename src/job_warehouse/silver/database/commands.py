"""Explicit Silver preflight, migration and transactional loading commands."""

import os
from pathlib import Path

import psycopg

from job_warehouse.bronze.database import connect_registry
from job_warehouse.silver.database.migration import migrate_silver, migration_sha256
from job_warehouse.silver.database.preflight import preflight
from job_warehouse.skills.input import json_text, require_new_destination, staging_directory


def run_preflight(jobs_run: Path, skills_run: Path, output_dir: Path) -> None:
    destination = require_new_destination(output_dir)
    result = preflight(jobs_run, skills_run)
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        (stage / "preflight.json").write_text(json_text(result.report))
        result.check_unchanged()
        if destination.exists():
            raise ValueError("Preflight output appeared during processing")
        os.rename(stage, destination)


def run_migration() -> None:
    try:
        with connect_registry() as conn:
            applied = migrate_silver(conn)
    except psycopg.Error as exc:
        # Connection errors may contain credentials or user-supplied DSN details.
        raise ValueError(
            f"Silver migration failed ({type(exc).__name__}); check DB locally"
        ) from None
    print(f"Silver schema: {'applied' if applied else 'unchanged'}; sha256={migration_sha256()}")


def run_load(jobs_run: Path, skills_run: Path, output_dir: Path, *, batch_size: int = 4096) -> None:
    from uuid import uuid4

    from job_warehouse.silver.database.loader import load_silver

    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    destination = require_new_destination(output_dir)
    destination.mkdir(parents=True, exist_ok=False)
    run_id = uuid4()
    # Persist a lookup key before any DB work, including a report-write failure later.
    (destination / "request.json").write_text(
        json_text(
            {
                "run_id": str(run_id),
                "jobs_run": str(jobs_run.resolve()),
                "skills_run": str(skills_run.resolve()),
            }
        )
    )
    print(f"Silver load run_id={run_id}; report={destination}", flush=True)
    result = None
    try:
        with connect_registry() as conn:
            result = load_silver(conn, jobs_run, skills_run, batch_size=batch_size, run_id=run_id)
        (destination / "load.json").write_text(json_text(result))
    except (psycopg.Error, ValueError, OSError) as exc:
        outcome = "DB succeeded, local report failed" if result else "Outcome requires DB lookup"
        raise ValueError(
            f"{outcome}; run_id={run_id}; check ops.silver_load_run before retrying "
            f"({type(exc).__name__})"
        ) from None
    print(f"Silver load: {result['status']}; run_id={run_id}")


def run_verification(
    jobs_run: Path, skills_run: Path, output_dir: Path, *, batch_size: int = 4096
) -> bool:
    from job_warehouse.silver.database.verification import verify_publication

    destination = require_new_destination(output_dir)
    try:
        with connect_registry() as conn:
            result = verify_publication(conn, jobs_run, skills_run, batch_size=batch_size)
    except psycopg.Error as exc:
        raise ValueError(
            f"Silver verification failed ({type(exc).__name__}); check DB locally"
        ) from None
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        (stage / "verification.json").write_text(json_text(result))
        if destination.exists():
            raise ValueError("Verification output appeared during processing")
        os.rename(stage, destination)
    print(f"Silver verification: {result['status']}; report={destination}")
    return bool(result["status"] == "passed_full_readback")
