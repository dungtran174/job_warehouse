"""Decode the complete pinned file without copying or cleaning its contents."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pyarrow.parquet as pq

from job_warehouse.history.contract import (
    COLUMNS,
    CONTRACT_VERSION,
    EXPECTED_ROWS,
    EXPECTED_SHA256,
    YEARS,
    HistoryProfileError,
)
from job_warehouse.history.identity import file_sha256
from job_warehouse.history.profile import validate_schema


@dataclass(frozen=True)
class ValidatedArtifact:
    path: Path
    relative_path: str
    sha256: str
    byte_size: int
    row_count: int
    schema_json: dict[str, object]


def resolve_input(input_root: Path, relative_path: str) -> tuple[Path, str]:
    relative = PurePosixPath(relative_path)
    if not relative_path or relative.is_absolute() or ".." in relative.parts:
        raise HistoryProfileError("Input path must be relative and stay inside input root")
    root = input_root.resolve(strict=True)
    if not root.is_dir():
        raise HistoryProfileError("Input root must be a directory")
    path = (root / relative_path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise HistoryProfileError("Input must be a file inside input root")
    return path, relative.as_posix()


def validate_artifact(
    input_root: Path,
    relative_path: str,
    *,
    expected_sha256: str = EXPECTED_SHA256,
    expected_rows: int = EXPECTED_ROWS,
    batch_size: int = 4096,
) -> ValidatedArtifact:
    """Overrides are for synthetic library tests; CLI accepts only the pinned file."""
    if batch_size <= 0 or expected_rows < 0:
        raise HistoryProfileError("batch_size must be positive and expected_rows nonnegative")
    path, relative = resolve_input(input_root, relative_path)
    before = file_sha256(path)
    if before != expected_sha256:
        raise HistoryProfileError("Input SHA256 does not match the pinned artifact")
    rows = 0
    seen: set[int] = set()
    with pq.ParquetFile(path) as parquet:
        validate_schema(parquet.schema_arrow)
        schema_json: dict[str, object] = {
            "contract_version": CONTRACT_VERSION,
            "columns": {name: str(parquet.schema_arrow.field(name).type) for name in COLUMNS},
        }
        footer_rows = parquet.metadata.num_rows
        for batch in parquet.iter_batches(batch_size=batch_size, use_threads=False):
            # Decode every column, and validate buffers/UTF-8 rather than trusting the footer.
            batch.validate(full=True)
            ids = batch.column(batch.schema.get_field_index("id")).to_pylist()
            years = batch.column(batch.schema.get_field_index("year")).to_pylist()
            for source_id, year in zip(ids, years, strict=True):
                if source_id is None or source_id <= 0 or source_id in seen:
                    raise HistoryProfileError("Found null, nonpositive or duplicate dataset ID")
                if year not in YEARS:
                    raise HistoryProfileError("Found missing or out-of-contract year")
                seen.add(source_id)
            rows += batch.num_rows
    if file_sha256(path) != before:
        raise HistoryProfileError("Input changed during validation")
    if rows != footer_rows or rows != expected_rows:
        raise HistoryProfileError("Decoded row count does not match footer and pinned contract")
    return ValidatedArtifact(path, relative, before, path.stat().st_size, rows, schema_json)


def recheck_artifact(artifact: ValidatedArtifact) -> None:
    if file_sha256(artifact.path) != artifact.sha256:
        raise HistoryProfileError("Input changed after validation; registry transaction aborted")
