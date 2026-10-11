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
