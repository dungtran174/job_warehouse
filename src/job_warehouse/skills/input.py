"""Verify immutable S4 input before reading job requirements."""

import json
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.contract import REVISION
from job_warehouse.history.identity import file_sha256

SCOPE = ("Công nghệ thông tin", "Kế toán / Kiểm toán", "Marketing")
INPUT_COLUMNS = ["id", "job_industry", "year", "requirements"]
PLACEHOLDERS = frozenset({"", "không", "none", "null", "n/a", "na", "-", "."})


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def require_new_destination(output_dir: Path) -> Path:
    destination = output_dir.resolve()
    if destination.exists():
        raise ValueError("Choose a new output directory")
    if any((p / "src/job_warehouse").is_dir() for p in (destination, *destination.parents)):
        raise ValueError("Skill artifacts must be outside the repository")
    return destination


def staging_directory(destination: Path) -> tempfile.TemporaryDirectory[str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=".skills-", dir=destination.parent)


@dataclass(frozen=True)
class VerifiedInput:
    parquet: Path
    manifest: dict[str, Any]
    hashes: dict[Path, str]
    rows: int

    def check_unchanged(self) -> None:
        if any(file_sha256(path) != sha for path, sha in self.hashes.items()):
            raise ValueError("Skill input changed during processing")

    def batches(self, batch_size: int = 2048) -> Iterator[list[dict[str, Any]]]:
        if batch_size < 1:
            raise ValueError("Batch size must be positive")
        seen: set[int] = set()
        with pq.ParquetFile(self.parquet) as source:
            for batch in source.iter_batches(batch_size=batch_size, columns=INPUT_COLUMNS):
                rows: list[dict[str, Any]] = batch.to_pylist()
                for row in rows:
                    ident = row["id"]
                    if not isinstance(ident, int) or ident <= 0 or ident in seen:
                        raise ValueError("Missing, invalid or duplicate job ID")
                    if not isinstance(row["job_industry"], str) or not row["job_industry"]:
                        raise ValueError("Invalid job industry")
                    if row["year"] not in range(2022, 2027):
                        raise ValueError("Invalid source year")
                    seen.add(ident)
                yield rows
        if len(seen) != self.rows:
            raise ValueError("Input population mismatch")


def verify_jobs_run(jobs_run: Path, *, allow_unpinned_fixture: bool = False) -> VerifiedInput:
    manifest_path = jobs_run / "manifest.json"
    parquet = jobs_run / "jobs_analysis.parquet"
    hashes = {path: file_sha256(path) for path in (manifest_path, parquet)}
    manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    if hashes[parquet] != manifest["artifacts"][parquet.name]["sha256"]:
        raise ValueError("S4 jobs input SHA mismatch")
    if not allow_unpinned_fixture:
        if (
            manifest["source"].get("revision") != REVISION
            or manifest["source"].get("dataset") != "tinixai/vietnamese-job-descriptions"
            or manifest["source"].get("pinned_artifact_verified") is not True
        ):
            raise ValueError("Unpinned S4 input")
        acceptance_path = jobs_run / "acceptance.json"
        hashes[acceptance_path] = file_sha256(acceptance_path)
        acceptance = json.loads(acceptance_path.read_text())
        if (
            acceptance.get("status") != "accepted_offline_not_db_published"
            or acceptance.get("run_manifest_sha256") != hashes[manifest_path]
        ):
            raise ValueError("S4 acceptance does not verify the input manifest")
        validation_path = Path(acceptance["validation_report"])
        hashes[validation_path] = file_sha256(validation_path)
        if hashes[validation_path] != acceptance["validation_report_sha256"]:
            raise ValueError("S4 validation report SHA mismatch")
    with pq.ParquetFile(parquet) as source:
        schema = source.schema_arrow
        expected_types = [pa.int64(), pa.string(), pa.int16(), pa.string()]
        if any(
            name not in schema.names or schema.field(name).type != kind
            for name, kind in zip(INPUT_COLUMNS, expected_types, strict=True)
        ):
            raise ValueError("S4 skill input schema mismatch")
        rows = source.metadata.num_rows
    if rows != manifest["partition"]["analysis"]:
        raise ValueError("S4 input population mismatch")
    return VerifiedInput(parquet, manifest, hashes, rows)
