"""Validate → batch normalize → reconcile → atomically publish local artifacts."""

import hashlib
import heapq
import json
import os
import resource
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.bronze.validation import validate_artifact
from job_warehouse.history.contract import (
    ATTRIBUTION,
    CONTRACT_VERSION,
    DATASET_NAME,
    EXPECTED_ROWS,
    EXPECTED_SHA256,
    LICENSE_ID,
    REVISION,
    SOURCE_URL,
)
from job_warehouse.history.identity import HistoryRow, file_sha256
from job_warehouse.silver import CORE_VERSION, EXTRACTOR_VERSION, MAPPING_VERSION
from job_warehouse.silver.core import normalize_row
from job_warehouse.silver.schema import core_schema, quarantine_schema


def configuration_hashes() -> dict[str, str]:
    root = files("job_warehouse.silver")
    assets = [x for x in root.iterdir() if x.name.endswith(".py")]
    assets.extend(root.joinpath("mappings").iterdir())
    return {
        x.name: hashlib.sha256(x.read_bytes()).hexdigest()
        for x in sorted(assets, key=lambda x: x.name)
        if x.is_file()
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class ReviewPool:
    """Bounded deterministic samples, grouped by clean requirements hash."""

    def __init__(self) -> None:
        self.heaps: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
        self.seen: set[str] = set()

    def add(self, row: dict[str, Any]) -> None:
        digest = row["requirements_text_hash"]
        if digest is None:
            return
        for attribute in ["education", "experience"]:
            split = "holdout" if int(digest[:8], 16) % 5 == 0 else "tune"
            for claim in row[f"{attribute}_inference_claims"]:
                group = "accepted" if claim["claim_status"] == "accepted" else "review"
                key = f"{digest}:{attribute}:{claim['claim_ordinal']}"
                if key in self.seen:
                    continue
                self.seen.add(key)
                label = f"{split}:{attribute}:{group}"
                score = int(hashlib.sha256(key.encode()).hexdigest(), 16)
                sample = {
                    "record_key": row["record_key"],
                    "source_dataset_id": row["source_dataset_id"],
                    "source_row_index": row["source_row_index"],
                    "year": row["year_value"],
                    "requirements_text_hash": digest,
                    "requirements_clean": row["requirements_clean"],
                    "claim": claim,
                    "sample_group": label,
                }
                heap = self.heaps.setdefault(label, [])
                limit = 200 if split == "holdout" and group == "accepted" else 20
                item = (-score, key, sample)
                if len(heap) < limit:
                    heapq.heappush(heap, item)
                elif item[:2] > heap[0][:2]:
                    heapq.heapreplace(heap, item)

    def write(self, directory: Path) -> dict[str, int]:
        counts: dict[str, int] = {}
        for group, heap in sorted(self.heaps.items()):
            destination = directory / (group.replace(":", "_") + ".jsonl")
            with destination.open("w", encoding="utf-8") as stream:
                for _, _, sample in sorted(heap, reverse=True):
                    stream.write(_json(sample) + "\n")
            counts[group] = len(heap)
        return counts


def run_core(
    input_path: Path,
    output_dir: Path,
    *,
    batch_size: int = 2048,
    expected_sha256: str = EXPECTED_SHA256,
    expected_rows: int = EXPECTED_ROWS,
    expected_quarantine: int | None = 21,
) -> dict[str, Any]:
    destination = output_dir.resolve()
    # Detect the destination's project ancestors too: installed wheels need not
    # live under the checkout, unlike editable installs and the processor image.
    for ancestor in (destination, *destination.parents):
        if (ancestor / "pyproject.toml").is_file() and (ancestor / "src/job_warehouse").is_dir():
            raise ValueError("Real Silver outputs/reports must stay outside the repository")
    if destination.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    started = time.monotonic()
    artifact = validate_artifact(
        input_path.parent,
        input_path.name,
        expected_sha256=expected_sha256,
        expected_rows=expected_rows,
        batch_size=batch_size,
    )
    rules = configuration_hashes()
    signature = hashlib.sha256(
        _json(
            {
                "input": artifact.sha256,
                "rules": rules,
                "core": CORE_VERSION,
                "extractor": EXTRACTOR_VERSION,
            }
        ).encode()
    ).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    by_year: Counter[tuple[int, str]] = Counter()
    changed: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}
    seen_keys: set[str] = set()
    row_digest = hashlib.sha256()
    review = ReviewPool()
    with tempfile.TemporaryDirectory(prefix=".silver-core-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        with (
            pq.ParquetWriter(
                staging / "core.parquet", core_schema(), compression="zstd"
            ) as core_writer,
            pq.ParquetWriter(
                staging / "core_quarantine.parquet", quarantine_schema(), compression="zstd"
            ) as quarantine_writer,
            pq.ParquetFile(artifact.path) as source,
        ):
            index = 0
            for batch in source.iter_batches(batch_size=batch_size, use_threads=False):
                batch.validate(full=True)
                core_rows, quarantined = [], []
                for raw in batch.to_pylist():
                    row, reason = normalize_row(cast(HistoryRow, raw), artifact.sha256, index)
                    key = row["record_key"]
                    if key in seen_keys:
                        raise ValueError("Output key collision")
                    seen_keys.add(key)
                    index += 1
                    row_digest.update(
                        _json({"partition": reason or "core", "row": row}).encode() + b"\n"
                    )
                    year = raw["year"]
                    counts["input"] += 1
                    by_year[(year, "input")] += 1
                    if reason:
                        quarantined.append(row)
                        counts["quarantine"] += 1
                        counts[f"quarantine:{reason}"] += 1
                        by_year[(year, "quarantine")] += 1
                        continue
                    core_rows.append(row)
                    counts["core"] += 1
                    by_year[(year, "core")] += 1
                    counts["records_with_flags"] += bool(row["quality_flags"])
                    for field in [
                        "company_mapping_status",
                        "education_status",
                        "job_type_status",
                        "position_status",
                        "experience_status",
                        "experience_kind",
                        "experience_group",
                        "requirements_status",
                        "education_inference_status",
                        "experience_inference_status",
                        "education_comparison_status",
                        "experience_comparison_status",
                    ]:
                        metric = f"{field}:{row[field]}"
                        counts[metric] += 1
                        by_year[(year, metric)] += 1
                    for flag in row["quality_flags"]:
                        counts[f"flag:{flag}"] += 1
                    for field in [
                        "job_title",
                        "company_name",
                        "job_description",
                        "benefits",
                        "requirements",
                    ]:
                        changed[field] += raw[field] != row[f"{field}_clean"]
                    for attribute in ["education", "experience"]:
                        for claim in row[f"{attribute}_inference_claims"]:
                            counts[
                                f"claims:{attribute}:{claim['claim_status']}:{claim['context']}"
                            ] += 1
                        if row[f"{attribute}_comparison_status"] == "source_unavailable" and row[
                            f"{attribute}_inference_status"
                        ] in {"single", "alternatives"}:
                            counts[f"source_unavailable_with_inference:{attribute}"] += 1
                    review.add(row)
                    for flag in row["quality_flags"]:
                        sample = examples.setdefault(flag, [])
                        limit = (
                            48
                            if flag == "job_position:wrong_field_content"
                            else 32
                            if flag == "education_level:ambiguous_degree_label"
                            else 2
                        )
                        if len(sample) < limit:
                            sample.append(
                                {
                                    "source_row_index": row["source_row_index"],
                                    "source_dataset_id": row["source_dataset_id"],
                                    "record_key": key,
                                    "year": year,
                                    "reason": flag,
                                    "job_position": raw["job_position"],
                                    "education_level": raw["education_level"],
                                    "requirements_clean": row["requirements_clean"],
                                }
                            )
                if core_rows:
                    core_writer.write_table(pa.Table.from_pylist(core_rows, schema=core_schema()))
                if quarantined:
                    quarantine_writer.write_table(
                        pa.Table.from_pylist(quarantined, schema=quarantine_schema())
                    )
                if index % (batch_size * 50) == 0:
                    print(f"Silver core: {index} rows decoded", flush=True)
        if (
            counts["input"] != artifact.row_count
            or counts["core"] + counts["quarantine"] != counts["input"]
        ):
            raise ValueError("Core/quarantine reconciliation failed")
        if expected_quarantine is not None and counts["quarantine"] != expected_quarantine:
            raise ValueError("Quarantine count differs from the reviewed policy expectation")
        for name, expected in [
            ("core.parquet", counts["core"]),
            ("core_quarantine.parquet", counts["quarantine"]),
        ]:
            with pq.ParquetFile(staging / name) as output:
                if output.metadata.num_rows != expected:
                    raise ValueError("Output row count differs from reconciliation")
        if file_sha256(artifact.path) != artifact.sha256 or configuration_hashes() != rules:
            raise ValueError("Input or rule assets changed during normalization")
        review_counts = review.write(staging)
        quality = {
            "counts": dict(sorted(counts.items())),
            "changed_fields_core_denominator": dict(changed),
            "by_year": [
                {"year": year, "metric": metric, "count": n}
                for (year, metric), n in sorted(by_year.items())
            ],
            "example_scope": "bounded review examples; source data stays outside Git",
        }
        (staging / "core_quality_report.json").write_text(
            json.dumps(quality, ensure_ascii=False, indent=2) + "\n"
        )
        (staging / "quality_review_samples.json").write_text(
            json.dumps(examples, ensure_ascii=False, indent=2) + "\n"
        )
        manifest: dict[str, Any] = {
            "status": "normalized_not_db_published",
            "created_at": datetime.now(UTC).isoformat(),
            "core_version": CORE_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "mapping_version": MAPPING_VERSION,
            "input_contract_version": CONTRACT_VERSION,
            "run_signature": signature,
            "asset_hashes": rules,
            "source": {
                "dataset": DATASET_NAME,
                "revision": REVISION,
                "source_url": SOURCE_URL,
                "license": LICENSE_ID,
                "attribution": ATTRIBUTION,
                "pinned_artifact_verified": artifact.sha256 == EXPECTED_SHA256
                and artifact.row_count == EXPECTED_ROWS,
            },
            "input": {
                "path": str(artifact.path),
                "sha256": artifact.sha256,
                "rows": artifact.row_count,
                "sha256_unchanged": True,
            },
            "partition": {
                "core": counts["core"],
                "quarantine": counts["quarantine"],
                "keys_unique_complete": True,
            },
            "content_digest": row_digest.hexdigest(),
            "output_schemas": {"core": str(core_schema()), "quarantine": str(quarantine_schema())},
            "review_samples": review_counts,
            "semantic_validation": "pending_independent_review",
            "limits": [
                "No salary/location/industry normalization, dedup removal, "
                "skills, database publish or Gold.",
                "Rule confidence is not a calibrated probability; "
                "review samples are not yet ground truth.",
            ],
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        manifest["artifacts"] = {
            p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
            for p in sorted(staging.iterdir())
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        # Do not overwrite an earlier good run; destination must still be absent.
        if destination.exists():
            raise ValueError("Output directory appeared during processing")
        os.rename(staging, destination)
    return manifest
