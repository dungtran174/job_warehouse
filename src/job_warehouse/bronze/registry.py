"""Transactional migrations and immutable, idempotent artifact registration."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from typing import Any

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from job_warehouse.bronze.database import RegistryConnection
from job_warehouse.bronze.validation import ValidatedArtifact, recheck_artifact
from job_warehouse.history.contract import (
    ARTIFACT_URL,
    ATTRIBUTION,
    CONTRACT_VERSION,
    DATASET_NAME,
    LICENSE_ID,
    REVISION,
    SOURCE_URL,
    HistoryProfileError,
)

MIGRATION_VERSION = "001_bronze"
MIGRATION_LOCK = 1976030101


def require_idle_connection(conn: RegistryConnection) -> None:
    if not conn.autocommit or conn.info.transaction_status != TransactionStatus.IDLE:
        raise HistoryProfileError("Registry operations require an idle autocommit connection")


def migrate_registry(conn: RegistryConnection) -> bool:
    require_idle_connection(conn)
    migration = files("job_warehouse.bronze").joinpath("migrations/001_bronze.sql").read_text()
    checksum = hashlib.sha256(migration.encode("utf-8")).hexdigest()
    with conn.transaction():
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
                raise HistoryProfileError("Applied migration checksum differs; do not edit it")
            return False
        conn.execute(migration)
        conn.execute(
            "INSERT INTO warehouse_meta.schema_migration (version, sha256) VALUES (%s, %s)",
            (MIGRATION_VERSION, checksum),
        )
    return True


@dataclass(frozen=True)
class Registration:
    file_id: int
    inserted: bool
    ingested_at: datetime
    sha256: str
    row_count: int
    relative_path: str


def artifact_metadata(artifact: ValidatedArtifact) -> dict[str, Any]:
    return {
        "dataset_name": DATASET_NAME,
        "revision": REVISION,
        "artifact_path": "data.parquet",
        "relative_path": artifact.relative_path,
        "sha256": artifact.sha256,
        "byte_size": artifact.byte_size,
        "row_count": artifact.row_count,
        "schema_json": artifact.schema_json,
        "source_url": SOURCE_URL,
        "artifact_url": ARTIFACT_URL,
        "license_id": LICENSE_ID,
        "attribution": ATTRIBUTION,
        "validation_version": CONTRACT_VERSION,
    }


def register_artifact(conn: RegistryConnection, artifact: ValidatedArtifact) -> Registration:
    """Never update the first row, including its reception time and original location."""
    require_idle_connection(conn)
    metadata = artifact_metadata(artifact)
    with conn.transaction():
        inserted = conn.execute(
            "INSERT INTO bronze.dataset_file "
            "(dataset_name, revision, artifact_path, relative_path, sha256, byte_size, "
            "row_count, schema_json, source_url, artifact_url, license_id, attribution, "
            "validation_version) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (dataset_name, revision, artifact_path) DO NOTHING RETURNING *",
            tuple(
                Jsonb(value) if key == "schema_json" else value for key, value in metadata.items()
            ),
        ).fetchone()
        row = inserted
        if row is None:
            row = conn.execute(
                "SELECT * FROM bronze.dataset_file "
                "WHERE dataset_name = %s AND revision = %s AND artifact_path = %s FOR SHARE",
                (DATASET_NAME, REVISION, "data.parquet"),
            ).fetchone()
            if row is None:
                raise HistoryProfileError("Registry row disappeared; retry registration")
            if row["sha256"] != artifact.sha256:
                raise HistoryProfileError(
                    "Artifact identity already exists with a different SHA256"
                )
            for key, value in metadata.items():
                if key != "relative_path" and row[key] != value:
                    raise HistoryProfileError(f"Existing registry metadata conflicts at {key}")
        # Recheck after SQL insertion and before COMMIT; changes roll back this transaction.
        recheck_artifact(artifact)
        result = Registration(
            row["file_id"],
            inserted is not None,
            row["ingested_at"],
            row["sha256"],
            row["row_count"],
            row["relative_path"],
        )
    return result
