"""Read-only full Parquet profiling, with aggregate and row-reference reports."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.contract import (
    ARTIFACT_URL,
    ATTRIBUTION,
    COLUMNS,
    CONTENT_COLUMNS,
    CONTRACT_VERSION,
    DATASET_NAME,
    DEFAULT_MIN_INDUSTRY_RECORDS,
    EXPECTED_ROWS,
    EXPECTED_SHA256,
    LICENSE_ID,
    LONG_TEXT_COLUMNS,
    REVISION,
    SENTINELS,
    SOURCE_URL,
    VALUE_COUNT_COLUMNS,
    YEARS,
    HistoryProfileError,
)
from job_warehouse.history.identity import (
    HistoryRow,
    Value,
    content_fingerprint,
    file_sha256,
    record_key,
)


@dataclass(slots=True)
class FieldAccumulator:
    hashed_distinct: bool = False
    null_count: int = 0
    blank_count: int = 0
    distinct: set[Value | bytes] = field(default_factory=set)
    sentinels: Counter[str] = field(default_factory=Counter)

    def add(self, value: Value) -> None:
        if value is None:
            self.null_count += 1
            return
        if isinstance(value, str):
            if not value.strip():
                self.blank_count += 1
            if value.strip().casefold() in SENTINELS:
                self.sentinels[value] += 1
            if self.hashed_distinct:
                self.distinct.add(hashlib.sha256(value.encode("utf-8")).digest())
                return
        self.distinct.add(value)

    def summary(self) -> dict[str, object]:
        return {
            "null_count": self.null_count,
            "blank_string_count": self.blank_count,
            "distinct_nonnull": len(self.distinct),
            "distinct_method": "sha256_raw_utf8" if self.hashed_distinct else "exact_values",
            "literal_sentinels": dict(sorted(self.sentinels.items())),
        }


@dataclass(frozen=True, slots=True)
class RowReference:
    row_index: int
    source_dataset_id: int | None


@dataclass(slots=True)
class DuplicateCandidate:
    fingerprint: str
    year: int | None
    members: list[RowReference]


@dataclass
class HistoryProfile:
    input_path: Path
    sha256: str
    byte_size: int
    footer_rows: int
    row_count: int
    expected_rows: int | None
    expected_sha256: str | None
    actual_schema: dict[str, str]
    fields: dict[str, dict[str, object]]
    id_min: int | None
    id_max: int | None
    invalid_id_count: int
    duplicate_ids: Counter[int]
    invalid_year_count: int
    value_counts: dict[str, Counter[Value]]
    industry_year_counts: Counter[tuple[Value, Value]]
    duplicate_candidates: list[DuplicateCandidate]
    identity_examples: list[dict[str, object]]
    validation_errors: list[str]

    @property
    def passed(self) -> bool:
        return not self.validation_errors

    def summary(self) -> dict[str, object]:
        return {
            "report_version": "history-profile-v1",
            "contract_version": CONTRACT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "source": {
                "dataset_name": DATASET_NAME,
                "revision": REVISION,
                "source_url": SOURCE_URL,
                "artifact_url": ARTIFACT_URL,
                "license_recorded": LICENSE_ID,
                "attribution": ATTRIBUTION,
                "pinned_artifact_verified": (
                    self.sha256 == EXPECTED_SHA256 and self.row_count == EXPECTED_ROWS
                ),
            },
            "input": {
                "path": str(self.input_path),
                "sha256": self.sha256,
                "byte_size": self.byte_size,
                "footer_rows": self.footer_rows,
                "rows_decoded": self.row_count,
                "expected_rows": self.expected_rows,
                "expected_sha256": self.expected_sha256,
                "sha256_before_after_equal": True,
            },
            "validation": {"passed": self.passed, "errors": self.validation_errors},
            "actual_schema": self.actual_schema,
            "fields": self.fields,
            "ids": {
                "min": self.id_min,
                "max": self.id_max,
                "invalid_count": self.invalid_id_count,
                "duplicate_groups": len(self.duplicate_ids),
                "duplicate_excess": sum(n - 1 for n in self.duplicate_ids.values()),
            },
            "year_distribution": count_entries(self.value_counts["year"]),
            "invalid_year_count": self.invalid_year_count,
            "content_duplicates": {
                "signature_columns": list(CONTENT_COLUMNS),
                "normalization": "none; original values including year",
                "candidate_groups": len(self.duplicate_candidates),
                "candidate_excess": sum(len(g.members) - 1 for g in self.duplicate_candidates),
                "policy": "retain_and_flag; no records removed by profiler",
                "review_sample_method": "up to 50 largest groups, then SHA256 order to 100",
                "review_sample": [asdict(g) for g in review_sample(self.duplicate_candidates)],
            },
            "identity_examples": self.identity_examples,
            "scope_policy": {
                "min_industry_records": DEFAULT_MIN_INDUSTRY_RECORDS,
                "comparison_threshold": 1000,
                "apply_after": "reviewed semantic group mapping and duplicate policy",
                "applied": False,
            },
            "limits": [
                "Distinct long-text counts use SHA256, not stored full texts.",
                "Duplicate fingerprints are candidates; they do not establish vacancy identity.",
                "No industry mapping, cleaning, skill extraction or database loading performed.",
                "Memory for exact scalar values and fingerprints grows with input cardinality.",
            ],
        }


def value_sort_key(value: Value) -> tuple[str, str]:
    return type(value).__name__, str(value)


def count_entries(counts: Counter[Value]) -> list[dict[str, object]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: value_sort_key(item[0]))
    ]


def review_sample(groups: list[DuplicateCandidate]) -> list[DuplicateCandidate]:
    largest = sorted(groups, key=lambda g: (-len(g.members), g.members[0].row_index))[:50]
    selected = {g.fingerprint for g in largest}
    rest = sorted((g for g in groups if g.fingerprint not in selected), key=lambda g: g.fingerprint)
    return largest + rest[: max(0, 100 - len(largest))]


def validate_schema(schema: pa.Schema) -> None:
    if len(schema.names) != len(COLUMNS) or set(schema.names) != set(COLUMNS):
        raise HistoryProfileError("Input must contain exactly the 14 historical contract columns")
    for name in COLUMNS:
        data_type = schema.field(name).type
        if name in {"id", "year"}:
            valid = pa.types.is_int64(data_type)
        else:
            valid = pa.types.is_string(data_type) or pa.types.is_large_string(data_type)
        if not valid:
            raise HistoryProfileError(f"Invalid type for {name}: {data_type}")


def profile_history(
    input_path: Path,
    *,
    batch_size: int = 4096,
    expected_sha256: str | None = None,
    expected_rows: int | None = None,
) -> HistoryProfile:
    if batch_size <= 0 or (expected_rows is not None and expected_rows < 0):
        raise HistoryProfileError("batch_size must be positive and expected_rows nonnegative")
    path = input_path.resolve(strict=True)
    if not path.is_file():
        raise HistoryProfileError("Input must be a local file")
    before_hash = file_sha256(path)
    if expected_sha256 is not None and before_hash != expected_sha256:
        raise HistoryProfileError("Input SHA256 does not match the expected pinned artifact")
    stats = {name: FieldAccumulator(name in LONG_TEXT_COLUMNS) for name in COLUMNS}
    counts: dict[str, Counter[Value]] = {name: Counter() for name in VALUE_COUNT_COLUMNS}
    industry_year_counts: Counter[tuple[Value, Value]] = Counter()
    duplicate_ids: Counter[int] = Counter()
    first_content: dict[str, RowReference] = {}
    duplicate_groups: dict[str, DuplicateCandidate] = {}
    identity_examples: list[dict[str, object]] = []
    id_min: int | None = None
    id_max: int | None = None
    invalid_ids = invalid_years = rows = 0
    with path.open("rb") as stream, pq.ParquetFile(stream) as parquet:
        validate_schema(parquet.schema_arrow)
        footer_rows = int(parquet.metadata.num_rows)
        actual_schema = {name: str(parquet.schema_arrow.field(name).type) for name in COLUMNS}
        for batch in parquet.iter_batches(
            batch_size=batch_size, columns=list(COLUMNS), use_threads=False
        ):
            for row in cast(list[HistoryRow], batch.to_pylist()):
                source_id = cast(int | None, row["id"])
                year = cast(int | None, row["year"])
                if source_id is None or source_id <= 0:
                    invalid_ids += 1
                if source_id is not None:
                    if source_id in stats["id"].distinct:
                        duplicate_ids[source_id] = duplicate_ids.get(source_id, 1) + 1
                    id_min = source_id if id_min is None else min(id_min, source_id)
                    id_max = source_id if id_max is None else max(id_max, source_id)
                if year not in YEARS:
                    invalid_years += 1
                for name in COLUMNS:
                    stats[name].add(row[name])
                for name in VALUE_COUNT_COLUMNS:
                    counts[name][row[name]] += 1
                industry_year_counts[(row["job_industry"], year)] += 1
                reference = RowReference(rows, source_id)
                fingerprint = content_fingerprint(row)
                if fingerprint in first_content:
                    if fingerprint not in duplicate_groups:
                        duplicate_groups[fingerprint] = DuplicateCandidate(
                            fingerprint, year, [first_content[fingerprint]]
                        )
                    duplicate_groups[fingerprint].members.append(reference)
                else:
                    first_content[fingerprint] = reference
                if len(identity_examples) < 5:
                    identity_examples.append(
                        {**asdict(reference), "record_key": record_key(before_hash, rows)}
                    )
                rows += 1
    if file_sha256(path) != before_hash:
        raise HistoryProfileError("Input changed during profiling; discard this attempt")
    errors = []
    if rows != footer_rows:
        errors.append(f"Decoded rows {rows} differ from footer rows {footer_rows}")
    if expected_rows is not None and rows != expected_rows:
        errors.append(f"Decoded rows {rows} differ from expected rows {expected_rows}")
    if invalid_ids:
        errors.append(f"Found {invalid_ids} null/nonpositive dataset IDs")
    if duplicate_ids:
        errors.append(f"Found {len(duplicate_ids)} duplicate dataset IDs")
    if invalid_years:
        errors.append(f"Found {invalid_years} missing/out-of-contract years")
    return HistoryProfile(
        path,
        before_hash,
        path.stat().st_size,
        footer_rows,
        rows,
        expected_rows,
        expected_sha256,
        actual_schema,
        {name: stat.summary() for name, stat in stats.items()},
        id_min,
        id_max,
        invalid_ids,
        duplicate_ids,
        invalid_years,
        counts,
        industry_year_counts,
        sorted(duplicate_groups.values(), key=lambda g: g.members[0].row_index),
        identity_examples,
        errors,
    )


def write_profile(profile: HistoryProfile, report_dir: Path) -> None:
    """Publish a new report directory; existing reports are never overwritten."""
    destination = report_dir.absolute()
    if destination.exists():
        raise HistoryProfileError("Report directory already exists; choose a new directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".history-profile-", dir=destination.parent
    ) as temporary:
        staging = Path(temporary)
        with (staging / "scalar_value_counts.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(["column", "raw_value_json", "count"])
            for name, counts in profile.value_counts.items():
                for value, count in sorted(
                    counts.items(), key=lambda item: value_sort_key(item[0])
                ):
                    writer.writerow([name, json.dumps(value, ensure_ascii=False), count])
        with (staging / "industry_year_counts.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(["raw_industry_json", "year_json", "count"])
            for (industry, year), count in sorted(
                profile.industry_year_counts.items(),
                key=lambda item: (value_sort_key(item[0][0]), value_sort_key(item[0][1])),
            ):
                writer.writerow([json.dumps(industry, ensure_ascii=False), json.dumps(year), count])
        with (staging / "duplicate_candidates.jsonl").open("w", encoding="utf-8") as stream:
            for group in profile.duplicate_candidates:
                stream.write(json.dumps(asdict(group), ensure_ascii=False) + "\n")
        (staging / "profile.json").write_text(
            json.dumps(profile.summary(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.rename(staging, destination)
