"""S6 batch-one CLI: validation and schema only, no business-data load."""

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
