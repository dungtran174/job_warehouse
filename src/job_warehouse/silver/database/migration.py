"""Checksum-locked, transactional Silver migration; never publish job data."""

import hashlib
from importlib.resources import files

from job_warehouse.bronze.database import RegistryConnection
from job_warehouse.bronze.registry import MIGRATION_LOCK, require_idle_connection
from job_warehouse.history.contract import HistoryProfileError

MIGRATION_VERSION = "002_silver"


def migration_text() -> str:
    return files("job_warehouse.silver.database").joinpath("migrations/001_silver.sql").read_text()


def migration_sha256() -> str:
    return hashlib.sha256(migration_text().encode()).hexdigest()


def migrate_silver(conn: RegistryConnection) -> bool:
    """Require a fresh schema, or the same ledger checksum; rollback on failure."""
    require_idle_connection(conn)
    migration = migration_text()
    checksum = hashlib.sha256(migration.encode()).hexdigest()
    with conn.transaction():
        # Share the Bronze lock so first-time creation of the ledger cannot race.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        conn.execute("CREATE SCHEMA IF NOT EXISTS warehouse_meta")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS warehouse_meta.schema_migration "
            "(version text PRIMARY KEY, sha256 char(64) NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        prior = conn.execute(
            "SELECT sha256 FROM warehouse_meta.schema_migration WHERE version = %s",
            (MIGRATION_VERSION,),
        ).fetchone()
        if prior is not None:
            if prior["sha256"] != checksum:
                raise HistoryProfileError("Silver migration checksum differs; do not edit it")
            return False
        conn.execute(migration)
        conn.execute(
            "INSERT INTO warehouse_meta.schema_migration (version, sha256) VALUES (%s, %s)",
            (MIGRATION_VERSION, checksum),
        )
    return True
