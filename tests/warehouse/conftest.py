"""Shared synthetic historical files, without dependencies on local real data."""

import pytest


@pytest.fixture
def bronze_file(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    from job_warehouse.history.contract import COLUMNS

    rows = [
        {**dict.fromkeys(COLUMNS, "Synthetic fixture"), "id": index + 1, "year": 2025}
        for index in range(32)
    ]
    rows[0]["requirements"] = None
    schema = pa.schema(
        [(column, pa.int64() if column in {"id", "year"} else pa.string()) for column in COLUMNS]
    )
    path = tmp_path / "history_data.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, row_group_size=7)
    return path


@pytest.fixture
def bronze_artifact(bronze_file):
    from job_warehouse.bronze.validation import validate_artifact
    from job_warehouse.history.identity import file_sha256

    return validate_artifact(
        bronze_file.parent,
        bronze_file.name,
        expected_sha256=file_sha256(bronze_file),
        expected_rows=32,
    )


@pytest.fixture(scope="module")
def silver_test_database():
    import os
    from uuid import uuid4

    from job_warehouse.bronze.database import connection_settings

    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.rows import dict_row

    if not os.environ.get("WAREHOUSE_TEST_DB_HOST"):
        pytest.skip("Set WAREHOUSE_TEST_DB_HOST for isolated PostgreSQL tests")
    settings = connection_settings(
        {
            f"WAREHOUSE_DB_{name}": os.environ[f"WAREHOUSE_TEST_DB_{name}"]
            for name in ["HOST", "PORT", "NAME", "USER", "PASSWORD", "PASSWORD_FILE"]
            if f"WAREHOUSE_TEST_DB_{name}" in os.environ
        }
    )
    name = f"silver_test_{uuid4().hex}"
    with psycopg.connect(**settings, autocommit=True, row_factory=dict_row) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            yield {**settings, "dbname": name}
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
