"""Stream exact Parquet values to PostgreSQL COPY; no business transformations."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from job_warehouse.silver.database.preflight import JOBS_SCHEMA, validate_job

JOB_COLUMNS = tuple(JOBS_SCHEMA.names)
SKILL_COLUMNS = ("job_id", "skill_code", "skill_name")


def parquet_rows(
    path: Path, *, skills: bool = False, batch_size: int = 4096
) -> Iterator[tuple[Any, ...]]:
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    columns = SKILL_COLUMNS if skills else JOB_COLUMNS
    with pq.ParquetFile(path) as source:
        for batch in source.iter_batches(batch_size=batch_size, columns=list(columns)):
            for row in batch.to_pylist():
                if skills:
                    if type(row["job_id"]) is not int or not 0 < row["job_id"] < 2**63:
                        raise ValueError("Invalid skill job ID")
                    for name in ("skill_code", "skill_name"):
                        value = row[name]
                        if not isinstance(value, str) or not value.strip() or "\x00" in value:
                            raise ValueError(f"Invalid skill text: {name}")
                        value.encode("utf-8", errors="strict")
                else:
                    validate_job(row)
                # Decimal and None stay native, arrays remain lists in source order.
                yield tuple(row[name] for name in columns)
