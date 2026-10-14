"""Verify pinned S2 → map functions/places → scope → reconcile → atomic local output."""

import hashlib
import json
import os
import re
import tempfile
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.contract import EXPECTED_ROWS, EXPECTED_SHA256, REVISION
from job_warehouse.history.identity import file_sha256, record_key
from job_warehouse.silver import CORE_VERSION
from job_warehouse.silver.core_runner import configuration_hashes as core_hashes
from job_warehouse.silver.enrichment import ENRICHMENT_VERSION, LOCATION_VERSION, TAXONOMY_VERSION
from job_warehouse.silver.enrichment.address_matching import (
    address_key,
    compatible_units,
    same_address,
)
from job_warehouse.silver.enrichment.assets import configuration_hashes
from job_warehouse.silver.enrichment.locations import (
    address_identity,
    address_reference_rules,
    classify_location,
    foreign_rules,
    locality_rules,
    place_rules,
    places,
)
from job_warehouse.silver.enrichment.occupations import (
    aliases,
    classify_occupation,
    domain_rules,
    families,
    title_rules,
)
from job_warehouse.silver.enrichment.schema import enrichment_schema
from job_warehouse.silver.enrichment.scope import scope_reason
from job_warehouse.silver.schema import core_schema
from job_warehouse.silver.text import normalize_text

COLUMNS = [
    "record_key",
    "source_row_index",
    "source_dataset_id",
    "id",
    "source_content_hash",
    "year_value",
    "job_title_clean",
    "job_industry",
    "location",
]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_core_manifest(path: Path) -> dict[str, Any]:
    try:
        value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or not isinstance(value["partition"]["core"], int)
            or isinstance(value["partition"]["core"], bool)
            or value["partition"]["core"] < 0
            or not isinstance(value["input"]["rows"], int)
            or value["input"]["rows"] < value["partition"]["core"]
            or not isinstance(value["asset_hashes"], dict)
            or not isinstance(value["run_signature"], str)
            or not isinstance(value["source"], dict)
            or not re.fullmatch(r"[0-9a-f]{64}", value["input"]["sha256"])
            or not re.fullmatch(r"[0-9a-f]{64}", value["artifacts"]["core.parquet"]["sha256"])
            or not isinstance(value["core_version"], str)
            or not isinstance(value["partition"]["keys_unique_complete"], bool)
        ):
            raise ValueError("Invalid manifest values")
        return value
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid S2 core manifest structure or values") from exc


def _row(raw: dict[str, Any]) -> dict[str, Any]:
    occupation = classify_occupation(raw["job_title_clean"], raw["job_industry"])
    location = classify_location(raw["location"])
    return {
        **{key: raw[key] for key in COLUMNS[:3]},
        "source_content_hash": raw["source_content_hash"],
        "year_value": raw["year_value"],
        "job_title_clean": raw["job_title_clean"],
        "job_industry_clean": normalize_text(raw["job_industry"], short=True).clean,
        "location_clean": normalize_text(raw["location"], short=True).clean,
        "occupation_primary": occupation.primary,
        "occupation_status": occupation.status,
        "occupation_method": occupation.method,
        "occupation_candidates": list(occupation.candidates),
        "occupation_source_candidates": list(occupation.source_candidates),
        "domains": list(occupation.domains),
        "occupation_flags": list(occupation.flags),
        "occupation_evidence": [asdict(e) for e in occupation.evidence],
        "location_places": list(location.places),
        "location_status": location.status,
        "location_group": location.group,
        "location_remote": location.remote,
        "location_nationwide": location.nationwide,
        "location_foreign": list(location.foreign),
        "location_flags": list(location.flags),
        "location_evidence": [asdict(e) for e in location.evidence],
        "location_address_links": [asdict(link) for link in location.address_links],
        "family_record_count": 0,
        "scope_500": False,
        "scope_1000": False,
        "scope_reason": "occupation_unresolved",
        "enrichment_version": ENRICHMENT_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "location_version": LOCATION_VERSION,
    }


def run_enrichment(
    core_path: Path,
    core_manifest: Path,
    output_dir: Path,
    *,
    batch_size: int = 2048,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    destination = output_dir.resolve()
    for ancestor in (destination, *destination.parents):
        if (ancestor / "pyproject.toml").is_file() and (ancestor / "src/job_warehouse").is_dir():
            raise ValueError("Real Silver outputs/reports must stay outside the repository")
    if destination.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    started = time.monotonic()
    manifest_hash = file_sha256(core_manifest)
    manifest = _load_core_manifest(core_manifest)
    input_hash = file_sha256(core_path)
    if manifest["artifacts"]["core.parquet"]["sha256"] != input_hash:
        raise ValueError("S2 core SHA256 differs from its manifest")
    if manifest["core_version"] != CORE_VERSION or manifest["asset_hashes"] != core_hashes():
        raise ValueError("S2 core version/assets do not match the supported contract")
    if manifest["partition"]["keys_unique_complete"] is not True:
        raise ValueError("S2 partition has not reconciled its identities")
    source_hash = manifest["input"]["sha256"]
    if not allow_unpinned_fixture and (
        source_hash != EXPECTED_SHA256
        or manifest["input"]["rows"] != EXPECTED_ROWS
        or manifest["source"].get("revision") != REVISION
        or manifest["source"].get("pinned_artifact_verified") is not True
    ):
        raise ValueError("Only the pinned historical core is supported by the CLI")
    # Clear caches between runs so changed mapping files cannot reuse old results.
    for cached in [
        families,
        aliases,
        title_rules,
        domain_rules,
        classify_occupation,
        places,
        place_rules,
        foreign_rules,
        locality_rules,
        address_reference_rules,
        classify_location,
    ]:
        cached.cache_clear()
    families()
    aliases()
    title_rules()
    domain_rules()
    places()
    place_rules()
    foreign_rules()
    locality_rules()
    address_reference_rules()
    assets = configuration_hashes()
    signature = hashlib.sha256(
        _json(
            {
                "core": input_hash,
                "core_manifest": manifest_hash,
                "assets": assets,
                "version": ENRICHMENT_VERSION,
                "thresholds": [500, 1000],
            }
        ).encode()
    ).hexdigest()
    counts: Counter[str] = Counter()
    year_counts: Counter[tuple[str, int]] = Counter()
    quality: Counter[str] = Counter()
    representatives: dict[str, str | None] = {}
    unique_counts: Counter[str] = Counter()
    seen: set[str] = set()
    examples: dict[str, list[dict[str, Any]]] = {}
    schema = enrichment_schema()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".silver-enrichment-", dir=destination.parent
    ) as temporary:
        stage = Path(temporary)
        with (
            pq.ParquetFile(core_path) as source,
            pq.ParquetWriter(stage / "mapping.parquet", schema, compression="zstd") as writer,
        ):
            if not source.schema_arrow.equals(core_schema(), check_metadata=False):
                raise ValueError("Input is not the full typed S2 core schema")
            if source.metadata.num_rows != manifest["partition"]["core"]:
                raise ValueError("S2 core footer row count differs from manifest")
            n = 0
            for batch in source.iter_batches(
                batch_size=batch_size, columns=COLUMNS, use_threads=False
            ):
                batch.validate(full=True)
                output = []
                for raw in batch.to_pylist():
                    key = raw["record_key"]
                    if key in seen or key != record_key(source_hash, raw["source_row_index"]):
                        raise ValueError("Duplicate or invalid core physical-row identity")
                    if not 0 <= raw["source_row_index"] < manifest["input"]["rows"]:
                        raise ValueError("Core source row index is outside its artifact")
                    if raw["source_dataset_id"] != raw["id"] or not raw["job_title_clean"]:
                        raise ValueError("Invalid source ID or title in core")
                    if not re.fullmatch(r"[0-9a-f]{64}", raw["source_content_hash"]):
                        raise ValueError("Invalid content candidate fingerprint")
                    seen.add(key)
                    row = _row(raw)
                    primary = row["occupation_primary"]
                    if primary:
                        counts[primary] += 1
                        year_counts[(primary, row["year_value"])] += 1
                    fingerprint = row["source_content_hash"]
                    if fingerprint not in representatives:
                        representatives[fingerprint] = primary
                        if primary:
                            unique_counts[primary] += 1
                    elif representatives[fingerprint] != primary:
                        raise ValueError(
                            "Identical raw content has inconsistent occupation decisions"
                        )
                    for field in ["occupation_status", "occupation_method", "location_status"]:
                        quality[f"{field}:{row[field]}"] += 1
                        group = f"{field}:{row[field]}"
                        if len(examples.setdefault(group, [])) < 5:
                            examples[group].append(row)
                    for field in ["occupation_flags", "location_flags"]:
                        quality.update(f"{field}:{flag}" for flag in row[field])
                    for field in ["occupation_evidence", "location_evidence"]:
                        for evidence in row[field]:
                            if (
                                row[evidence["field"]][evidence["start"] : evidence["end"]]
                                != evidence["text"]
                            ):
                                raise ValueError("Evidence offset differs from its clean source")
                    for link in row["location_address_links"]:
                        text = row["location_clean"]
                        partial = address_identity(
                            text[link["partial_start"] : link["partial_end"]]
                        )
                        complete = address_identity(
                            text[link["complete_start"] : link["complete_end"]]
                        )
                        if not partial or not (
                            complete.startswith(partial + ",")
                            and compatible_units(partial, complete)
                            if link["rule_id"] == "location.repeated_address_exact_prefix"
                            else same_address(address_key(partial), address_key(complete))
                        ):
                            raise ValueError("Repeated-address proof differs from its source")
                    # Address text is only transient for evidence checking.
                    # Reconstruct it from the immutable S2 location when auditing;
                    # do not persist a second detailed address in S3 enrichment.
                    row.pop("location_clean")
                    output.append(row)
                    n += 1
                writer.write_table(pa.Table.from_pylist(output, schema=schema))
                if n % (batch_size * 50) == 0:
                    print(f"Silver enrichment: {n} core rows mapped", flush=True)
        if len(seen) != manifest["partition"]["core"]:
            raise ValueError("Enrichment/core row reconciliation failed")
        digest = hashlib.sha256()
        eligible: Counter[str] = Counter()
        with (
            pq.ParquetFile(stage / "mapping.parquet") as mapped,
            pq.ParquetWriter(stage / "enrichment.parquet", schema, compression="zstd") as writer,
        ):
            for batch in mapped.iter_batches(batch_size=batch_size, use_threads=False):
                output = batch.to_pylist()
                for row in output:
                    primary = row["occupation_primary"]
                    row["family_record_count"] = counts[primary] if primary else 0
                    row["scope_reason"] = scope_reason(primary, counts, 500)
                    for threshold in [500, 1000]:
                        row[f"scope_{threshold}"] = (
                            scope_reason(primary, counts, threshold) == "eligible"
                        )
                        eligible[str(threshold)] += row[f"scope_{threshold}"]
                    digest.update(_json(row).encode() + b"\n")
                writer.write_table(pa.Table.from_pylist(output, schema=schema))
        (stage / "mapping.parquet").unlink()
        # Full readback tests stored grain, logical digest and nonnull/evidence constraints.
        read_digest = hashlib.sha256()
        read_keys: set[str] = set()
        with pq.ParquetFile(stage / "enrichment.parquet") as output:
            for batch in output.iter_batches(batch_size=batch_size, use_threads=False):
                batch.validate(full=True)
                for row in batch.to_pylist():
                    if row["record_key"] in read_keys:
                        raise ValueError("Duplicate output key after serialization")
                    read_keys.add(row["record_key"])
                    if any(row[field.name] is None for field in schema if not field.nullable):
                        raise ValueError("Null in logical required output field")
                    read_digest.update(_json(row).encode() + b"\n")
        if read_keys != seen or read_digest.digest() != digest.digest():
            raise ValueError("Stored enrichment differs from generated content")
        if (
            file_sha256(core_path) != input_hash
            or file_sha256(core_manifest) != manifest_hash
            or configuration_hashes() != assets
            or core_hashes() != manifest["asset_hashes"]
        ):
            raise ValueError("Input or assets changed during enrichment")
        report = {
            "rows": len(seen),
            "status_counts": dict(sorted(quality.items())),
            "family_counts": dict(sorted(counts.items())),
            "family_year": [
                {"family": k, "year": y, "count": v} for (k, y), v in sorted(year_counts.items())
            ],
            "scope": {
                str(t): {
                    "families": sorted(k for k, v in counts.items() if v >= t),
                    "records": eligible[str(t)],
                }
                for t in [500, 1000]
            },
            "duplicate_candidate_sensitivity": {
                "policy": "retain_and_flag",
                "candidate_representatives": len(representatives),
                "extra_candidate_records": len(seen) - len(representatives),
                "representative_family_counts": dict(sorted(unique_counts.items())),
                "warning": "Exact raw-content candidates are not verified unique vacancies; "
                "no rows removed.",
            },
            "trend_gate": "not_applied; year coverage and per-year samples need separate review",
            "place_counts_are_not_additive": True,
        }
        _write_json(stage / "quality_report.json", report)
        _write_json(stage / "review_examples.json", examples)
        _write_json(
            stage / "schema.json",
            [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema],
        )
        result = {
            "status": "enriched_not_db_published",
            "created_at": datetime.now(UTC).isoformat(),
            "enrichment_version": ENRICHMENT_VERSION,
            "taxonomy_version": TAXONOMY_VERSION,
            "location_version": LOCATION_VERSION,
            "asset_hashes": assets,
            "run_signature": signature,
            "input": {
                "path": str(core_path.resolve()),
                "sha256": input_hash,
                "rows": len(seen),
                "manifest_path": str(core_manifest.resolve()),
                "manifest_sha256": manifest_hash,
                "core_run_signature": manifest["run_signature"],
                "raw_sha256": source_hash,
            },
            "source": manifest["source"],
            "partition": {
                "core": len(seen),
                "enrichment": len(read_keys),
                "keys_unique_complete": True,
            },
            "content_digest": digest.hexdigest(),
            "semantic_validation": "pending_independent_review",
            "scope_thresholds": [500, 1000],
            "limits": [
                "No salary, skills, database publication, Gold or geography crosswalk.",
                "Scope is provisional until independent semantic review; "
                "no deletion of rare or unresolved records.",
            ],
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        result["artifacts"] = {
            p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
            for p in sorted(stage.iterdir())
        }
        _write_json(stage / "manifest.json", result)
        if destination.exists():
            raise ValueError("Output directory appeared during processing")
        os.rename(stage, destination)
    return result
