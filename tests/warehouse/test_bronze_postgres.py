"""Offline integration tests; create/drop only their own randomly named database."""

# ruff: noqa: E402
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("pyarrow")
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from job_warehouse.bronze.database import connection_settings
from job_warehouse.bronze.registry import artifact_metadata, migrate_registry, register_artifact
from job_warehouse.history.contract import HistoryProfileError

pytestmark = pytest.mark.warehouse_db


@pytest.fixture(scope="module")
def temporary_database():
    if not os.environ.get("WAREHOUSE_TEST_DB_HOST"):
        pytest.skip(
            "Set WAREHOUSE_TEST_DB_HOST to run isolated offline PostgreSQL integration tests"
        )
    names = ["HOST", "PORT", "NAME", "USER", "PASSWORD", "PASSWORD_FILE"]
    env = {
        f"WAREHOUSE_DB_{name}": os.environ[f"WAREHOUSE_TEST_DB_{name}"]
        for name in names
        if f"WAREHOUSE_TEST_DB_{name}" in os.environ
    }
    settings = connection_settings(env)
    name = f"warehouse_test_{uuid4().hex}"
    with psycopg.connect(**settings, autocommit=True, row_factory=dict_row) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            yield {**settings, "dbname": name}
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def registry_conn(temporary_database):
    with psycopg.connect(**temporary_database, autocommit=True, row_factory=dict_row) as conn:
        migrate_registry(conn)
        # Only the temporary database is cleared; existing warehouse rows are never touched.
        conn.execute("TRUNCATE bronze.dataset_file RESTART IDENTITY")
        yield conn


def count_rows(conn):
    return conn.execute("SELECT count(*) AS n FROM bronze.dataset_file").fetchone()["n"]


def test_migration_is_repeatable_and_checksum_is_enforced(registry_conn):
    assert migrate_registry(registry_conn) is False
    with registry_conn.transaction():
        registry_conn.execute("UPDATE warehouse_meta.schema_migration SET sha256 = %s", ("a" * 64,))
    try:
        with pytest.raises(HistoryProfileError, match="checksum"):
            migrate_registry(registry_conn)
    finally:
        # Restore ledger so the module's next test can use this temporary DB.
        registry_conn.execute("DELETE FROM warehouse_meta.schema_migration")
        registry_conn.execute("DROP SCHEMA bronze CASCADE")
        assert migrate_registry(registry_conn) is True


def test_register_twice_keeps_one_row_and_first_timestamp(registry_conn, bronze_artifact):
    first = register_artifact(registry_conn, bronze_artifact)
    second = register_artifact(
        registry_conn, replace(bronze_artifact, relative_path="alias.parquet")
    )
    assert first.inserted and not second.inserted
    assert first.file_id == second.file_id
    assert first.ingested_at == second.ingested_at
    assert first.relative_path == second.relative_path == "history_data.parquet"
    assert count_rows(registry_conn) == 1
    row = registry_conn.execute("SELECT * FROM bronze.dataset_file").fetchone()
    assert row["row_count"] == 32
    assert row["license_id"] == "CC-BY-NC-4.0"
    assert row["schema_json"] == bronze_artifact.schema_json


def test_sha_and_metadata_conflicts_preserve_existing_registry(registry_conn, bronze_artifact):
    first = register_artifact(registry_conn, bronze_artifact)
    for change in [{"sha256": "a" * 64}, {"row_count": 33}]:
        with pytest.raises(HistoryProfileError, match="different SHA256|metadata conflicts"):
            register_artifact(registry_conn, replace(bronze_artifact, **change))
    assert register_artifact(registry_conn, bronze_artifact).ingested_at == first.ingested_at
    assert count_rows(registry_conn) == 1


def test_crash_after_insert_rolls_back_and_replay_succeeds(
    registry_conn, bronze_artifact, monkeypatch
):
    def crash(_):
        raise RuntimeError("Synthetic interruption before commit")

    with monkeypatch.context() as context:
        context.setattr("job_warehouse.bronze.registry.recheck_artifact", crash)
        with pytest.raises(RuntimeError, match="interruption"):
            register_artifact(registry_conn, bronze_artifact)
    assert count_rows(registry_conn) == 0
    assert register_artifact(registry_conn, bronze_artifact).inserted


def test_file_changed_after_validation_rolls_back(registry_conn, bronze_artifact):
    bronze_artifact.path.write_bytes(b"changed synthetic file")
    with pytest.raises(HistoryProfileError, match="changed after"):
        register_artifact(registry_conn, bronze_artifact)
    assert count_rows(registry_conn) == 0


def test_parallel_registration_keeps_one_row(registry_conn, temporary_database, bronze_artifact):
    def register(_):
        with psycopg.connect(**temporary_database, autocommit=True, row_factory=dict_row) as conn:
            return register_artifact(conn, bronze_artifact)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, range(2)))
    assert sum(result.inserted for result in results) == 1
    assert results[0].file_id == results[1].file_id
    assert count_rows(registry_conn) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"sha256": "invalid"},
        {"revision": "invalid"},
        {"byte_size": 0},
        {"row_count": -1},
        {"relative_path": "../file.parquet"},
        {"license_id": None},
    ],
)
def test_database_constraints_reject_bad_metadata(registry_conn, bronze_artifact, change):
    metadata = {**artifact_metadata(bronze_artifact), **change}
    statement = sql.SQL("INSERT INTO bronze.dataset_file ({}) VALUES ({})").format(
        sql.SQL(", ").join(map(sql.Identifier, metadata)),
        sql.SQL(", ").join(sql.Placeholder() for _ in metadata),
    )
    params = tuple(
        Jsonb(value) if key == "schema_json" else value for key, value in metadata.items()
    )
    with pytest.raises(psycopg.IntegrityError), registry_conn.transaction():
        registry_conn.execute(statement, params)
    assert count_rows(registry_conn) == 0


def test_nested_transaction_cannot_report_uncommitted_registration(registry_conn, bronze_artifact):
    with registry_conn.transaction(), pytest.raises(HistoryProfileError, match="idle autocommit"):
        register_artifact(registry_conn, bronze_artifact)
    assert count_rows(registry_conn) == 0


def test_migration_failure_rolls_back_all_ddl(registry_conn, monkeypatch):
    registry_conn.execute("DROP SCHEMA bronze CASCADE")
    registry_conn.execute("DELETE FROM warehouse_meta.schema_migration")

    class BrokenMigration:
        def joinpath(self, _):
            return self

        def read_text(self):
            return "CREATE SCHEMA bronze; CREATE TABLE bronze.partial(id int); INVALID SQL;"

    try:
        with monkeypatch.context() as context:
            context.setattr("job_warehouse.bronze.registry.files", lambda _: BrokenMigration())
            with pytest.raises(psycopg.ProgrammingError):
                migrate_registry(registry_conn)
        assert (
            registry_conn.execute("SELECT to_regnamespace('bronze') AS name").fetchone()["name"]
            is None
        )
        assert (
            registry_conn.execute(
                "SELECT count(*) AS n FROM warehouse_meta.schema_migration"
            ).fetchone()["n"]
            == 0
        )
    finally:
        assert migrate_registry(registry_conn) is True
