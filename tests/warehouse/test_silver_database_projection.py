"""Parquet streaming and SQL projection tests without a database."""

from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from silver_database_fixtures import frozen_runs, job

from job_warehouse.silver.database.loader import prepare_load
from job_warehouse.silver.database.preflight import JOBS_SCHEMA
from job_warehouse.silver.database.projection import JOB_COLUMNS, parquet_rows


def test_projection_preserves_native_decimal_null_and_arrays(tmp_path):
    rows = [job(id=i, company_name=None, requirements='Tiếng Việt\n"A" \\N') for i in range(1, 8)]
    p = tmp_path / "jobs.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=JOBS_SCHEMA), p, row_group_size=2)
    projected = list(parquet_rows(p, batch_size=1))
    assert [dict(zip(JOB_COLUMNS, row, strict=True)) for row in projected] == rows
    assert isinstance(projected[0][JOB_COLUMNS.index("experience_min_years")], Decimal)
    assert projected[0][JOB_COLUMNS.index("location")] == ["Hà Nội", "Bình Dương"]
    assert projected[0][JOB_COLUMNS.index("salary_min")] is None


def test_projection_rejects_rounding_and_invalid_batch_size(tmp_path):
    p = tmp_path / "jobs.parquet"
    pq.write_table(
        pa.Table.from_pylist([job(experience_min_years=Decimal("0.083333"))], schema=JOBS_SCHEMA), p
    )
    with pytest.raises(ValueError, match="numeric conversion"):
        list(parquet_rows(p))
    with pytest.raises(ValueError, match="positive"):
        list(parquet_rows(p, batch_size=0))


def test_prepared_fingerprint_binds_loader_version_and_checks_input_again(tmp_path, monkeypatch):
    from job_warehouse.silver.database import loader

    runs = frozen_runs(tmp_path)
    first = prepare_load(*runs, allow_unpinned_fixture=True)
    monkeypatch.setattr(loader, "VERSION", "fixture-next-version")
    second = prepare_load(*runs, allow_unpinned_fixture=True)
    assert first.fingerprint != second.fingerprint
    (runs[0] / "manifest.json").write_text("changed")
    with pytest.raises(ValueError, match="changed after preflight"):
        first.check_unchanged()
