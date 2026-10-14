"""Publish source-industry labels and a minimum-count analysis subset offline."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.contract import EXPECTED_ROWS, EXPECTED_SHA256, REVISION
from job_warehouse.history.identity import file_sha256, record_key
from job_warehouse.silver.industry_labels import (
    INDUSTRY_LABEL_VERSION,
    industry_display_candidate,
    industry_equivalence_key,
)
from job_warehouse.silver.industry_rollup import (
    INDUSTRY_ROLLUP_VERSION,
    resolve_industry_rollup,
)

POLICY_VERSION = "owner-source-industry-20261015-v1"
INDUSTRY_COLUMNS = (
    "job_industry_raw",
    "job_industry",
    "industry_label_record_count",
    "industry_scope_500",
    "industry_scope_1000",
    "industry_label_version",
)


def policy_text() -> str:
    return (
        files("job_warehouse.silver")
        .joinpath("mappings/industry_rollup_policy.csv")
        .read_text(encoding="utf-8")
    )


def read_policy() -> tuple[dict[str, str], list[dict[str, str]]]:
    import io

    rows = list(csv.DictReader(io.StringIO(policy_text())))
    decisions: dict[str, str] = {}
    kept: set[str] = set()
    for row in rows:
        child, parent = row["child"], row["parent"]
        if not child or child in decisions or child in kept:
            raise ValueError("Duplicate/empty industry policy child")
        if row["action"] == "merge" and parent:
            decisions[child] = parent
        elif row["action"] == "keep" and not parent:
            kept.add(child)
        else:
            raise ValueError("Invalid industry policy action")
    for child in decisions:
        resolve_industry_rollup(child, decisions)
    return decisions, rows


def source_mapping(counts: Counter[str]) -> dict[str, str]:
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for label in counts:
        if not label.strip():
            raise ValueError("Empty source industry label")
        groups[industry_equivalence_key(label)].append(label)
    decisions, _ = read_policy()
    mapping = {}
    for members in groups.values():
        representative = min(members, key=lambda s: (-counts[s], s))
        canonical = industry_display_candidate(representative)
        final = resolve_industry_rollup(canonical, decisions)
        for label in members:
            mapping[label] = final
    return mapping


def run_industry(
    bronze: Path,
    base_run: Path,
    output_dir: Path,
    *,
    threshold: int = 500,
    batch_size: int = 4096,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    """Keep full Silver; count labels on full core before selecting analysis rows."""
    if threshold < 1 or batch_size < 1:
        raise ValueError("Threshold and batch size must be positive")
    destination = output_dir.resolve()
    if destination.exists():
        raise ValueError("Choose a new output directory")
    if any((p / "src/job_warehouse").is_dir() for p in (destination, *destination.parents)):
        raise ValueError("Industry output must be outside the repository")
    base_parquet = base_run / "enrichment.parquet"
    base_manifest = base_run / "manifest.json"
    manifest = json.loads(base_manifest.read_text())
    hashes = {p: file_sha256(p) for p in (bronze, base_parquet, base_manifest)}
    if hashes[base_parquet] != manifest["artifacts"]["enrichment.parquet"]["sha256"]:
        raise ValueError("Base enrichment SHA mismatch")
    if not allow_unpinned_fixture and hashes[bronze] != EXPECTED_SHA256:
        raise ValueError("Bronze SHA does not match the pinned historical artifact")
    source = pq.read_table(bronze, columns=["id", "job_industry"])
    if not allow_unpinned_fixture and source.num_rows != EXPECTED_ROWS:
        raise ValueError("Bronze row count mismatch")
    ids, raw = source["id"].to_pylist(), source["job_industry"].to_pylist()
    if any(not isinstance(label, str) for label in raw) or len(set(ids)) != len(ids):
        raise ValueError("Invalid Bronze IDs or industry labels")
    raw_counts: Counter[str] = Counter(raw)
    mapping = source_mapping(raw_counts)
    decisions, policy_rows = read_policy()
    frozen_policy = policy_text()
    code_paths = [
        Path(__file__),
        Path(__file__).with_name("industry_labels.py"),
        Path(__file__).with_name("industry_rollup.py"),
    ]
    code_hashes = {p: file_sha256(p) for p in code_paths}
    counts: Counter[str] = Counter()
    seen: set[int] = set()
    pf = pq.ParquetFile(base_parquet)
    for batch in pf.iter_batches(
        batch_size=batch_size, columns=["source_row_index", "source_dataset_id", "record_key"]
    ):
        for row in batch.to_pylist():
            index = row["source_row_index"]
            if not isinstance(index, int) or not 0 <= index < len(raw) or index in seen:
                raise ValueError("Invalid or duplicate physical source row")
            if row["source_dataset_id"] != ids[index] or row["record_key"] != record_key(
                hashes[bronze], index
            ):
                raise ValueError("Base/Bronze identity mismatch")
            seen.add(index)
            counts[mapping[raw[index]]] += 1
    partition = manifest.get("partition", {})
    expected = partition.get("enrichment", manifest.get("summary", {}).get("core_records"))
    if expected != len(seen):
        raise ValueError("Base manifest population mismatch")
    old_names = [name for name in pf.schema_arrow.names if name not in INDUSTRY_COLUMNS]
    new_fields = [
        pa.field("job_industry_raw", pa.string(), nullable=False),
        pa.field("job_industry", pa.string(), nullable=False),
        pa.field("industry_label_record_count", pa.int64(), nullable=False),
        pa.field("industry_scope_500", pa.bool_(), nullable=False),
        pa.field("industry_scope_1000", pa.bool_(), nullable=False),
        pa.field("industry_label_version", pa.string(), nullable=False),
    ]
    schema = pa.schema([pf.schema_arrow.field(n) for n in old_names] + new_fields)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".industry-", dir=destination.parent) as tmp:
        stage = Path(tmp)
        selected = 0
        with (
            pq.ParquetWriter(stage / "enrichment.parquet", schema, compression="zstd") as full,
            pq.ParquetWriter(
                stage / "jobs_analysis.parquet", schema, compression="zstd"
            ) as analysis,
        ):
            for batch in pf.iter_batches(batch_size=batch_size):
                table = pa.Table.from_batches([batch]).select(old_names)
                labels = [raw[i] for i in table["source_row_index"].to_pylist()]
                final = [mapping[s] for s in labels]
                ns = [counts[s] for s in final]
                values = [
                    labels,
                    final,
                    ns,
                    [n >= 500 for n in ns],
                    [n >= 1000 for n in ns],
                    [INDUSTRY_LABEL_VERSION + "+" + POLICY_VERSION] * len(labels),
                ]
                for field, value in zip(new_fields, values, strict=True):
                    table = table.append_column(field, pa.array(value, type=field.type))
                full.write_table(table)
                chosen = table.filter(pa.array([n >= threshold for n in ns], type=pa.bool_()))
                selected += chosen.num_rows
                analysis.write_table(chosen)
        out = pq.ParquetFile(stage / "enrichment.parquet")
        subset = pq.ParquetFile(stage / "jobs_analysis.parquet")
        readback = 0
        for i, batch in enumerate(pf.iter_batches(batch_size=batch_size)):
            before = pa.Table.from_batches([batch])
            after = out.read_row_group(i)
            if not before.select(old_names).equals(after.select(old_names)):
                raise ValueError("Unrelated Silver fields changed")
            labels = [raw[k] for k in before["source_row_index"].to_pylist()]
            if after["job_industry_raw"].to_pylist() != labels or after[
                "job_industry"
            ].to_pylist() != [mapping[s] for s in labels]:
                raise ValueError("Industry mapping readback mismatch")
            mask = [counts[mapping[s]] >= threshold for s in labels]
            if not after.filter(pa.array(mask, type=pa.bool_())).equals(subset.read_row_group(i)):
                raise ValueError("Analysis selection readback mismatch")
            readback += after.num_rows
        if readback != len(seen) or subset.metadata.num_rows != selected:
            raise ValueError("Industry publication count mismatch")
        if any(file_sha256(p) != h for p, h in hashes.items()) or policy_text() != frozen_policy:
            raise ValueError("Input or policy changed during industry processing")
        if any(file_sha256(p) != h for p, h in code_hashes.items()):
            raise ValueError("Industry code changed during processing")
        with (stage / "bronze_to_silver_industry.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["job_industry_raw", "job_industry", "bronze_records", "silver_group_records"]
            )
            w.writerows((s, mapping[s], n, counts[mapping[s]]) for s, n in raw_counts.most_common())
        with (stage / "owner_rollup_applied.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["decision_code", "child", "parent", "action", "final_parent"])
            w.writerows(
                (
                    r["decision_code"],
                    r["child"],
                    r["parent"],
                    r["action"],
                    resolve_industry_rollup(r["child"], decisions),
                )
                for r in policy_rows
            )
        (stage / "industry_policy.csv").write_text(frozen_policy, encoding="utf-8")
        report = {
            "full": len(seen),
            "analysis": selected,
            "excluded": len(seen) - selected,
            "labels": len(counts),
            "labels_selected": sum(n >= threshold for n in counts.values()),
            "threshold": threshold,
            "retain_other_and_unknown": True,
            "counts": dict(counts),
            "full_readback_passed": True,
        }
        (stage / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        result = {
            "status": "source_industry_and_analysis_published_offline",
            "created_at": datetime.now(UTC).isoformat(),
            "source": {
                "revision": REVISION,
                "pinned_artifact_verified": not allow_unpinned_fixture,
            },
            "policy_version": POLICY_VERSION,
            "normalizer_version": INDUSTRY_LABEL_VERSION,
            "rollup_version": INDUSTRY_ROLLUP_VERSION,
            "input_hashes": {str(p.resolve()): h for p, h in hashes.items()},
            "asset_hashes": {p.name: h for p, h in code_hashes.items()},
            "partition": {"enrichment": len(seen), "analysis": selected},
            "summary": report,
            "artifacts": {
                p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in stage.iterdir()
            },
        }
        (stage / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if destination.exists():
            raise ValueError("Output appeared during processing")
        os.rename(stage, destination)
    return result
