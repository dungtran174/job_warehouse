"""Add a validated expansion batch without recomputing accepted pilot claims."""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.expansion_merge import checked_artifacts
from job_warehouse.skills.input import json_text, require_new_destination, staging_directory
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS
from job_warehouse.skills.scopes import processing_scope
from job_warehouse.skills.taxonomy import load_taxonomy


def merge_batch(
    candidate_run: Path,
    baseline_run: Path,
    gate_path: Path,
    output_dir: Path,
    *,
    batch_name: str,
) -> dict[str, Any]:
    """Require an evidenced per-industry gate; never change a latest pointer here."""
    approved_scope = batch_scope(batch_name)
    destination = require_new_destination(output_dir)
    candidate, tracked = checked_artifacts(candidate_run)
    scope = processing_scope(batch_name, tuple(candidate.get("processed_scope", approved_scope)))
    baseline, baseline_hashes = checked_artifacts(baseline_run)
    tracked.update(baseline_hashes)
    tracked[gate_path] = file_sha256(gate_path)
    gate = json.loads(gate_path.read_text())
    if (
        gate.get("status") != "accepted_ai_holdout_not_human_gold"
        or gate.get("scope") != list(scope)
        or candidate["policy"]["scope"] != list(approved_scope)
        or gate.get("taxonomy_sha256")
        != file_sha256(candidate_run / "taxonomy_snapshot/taxonomy.csv")
        or gate.get("aliases_sha256")
        != file_sha256(candidate_run / "taxonomy_snapshot/aliases.csv")
        or gate.get("policy_sha256") != file_sha256(candidate_run / "taxonomy_snapshot/policy.json")
    ):
        raise ValueError("Batch semantic gate or frozen taxonomy mismatch")
    if set(gate.get("by_industry", {})) != set(scope):
        raise ValueError("Gate must cover every industry")
    for metrics in gate["by_industry"].values():
        if (
            metrics.get("texts", 0) < 50
            or metrics.get("tp", 0) < 1
            or metrics.get("precision") is None
            or metrics["precision"] < 0.95
            or metrics.get("recall") is None
            or metrics["recall"] < 0.80
        ):
            raise ValueError("Batch did not pass per-industry precision/recall gate")
    if not gate.get("asset_hashes") or not gate.get("validation_artifacts"):
        raise ValueError("Gate requires code and review provenance")
    for path, sha in gate["asset_hashes"].items():
        if candidate["asset_hashes"].get(path) != sha:
            raise ValueError("Candidate code differs from the evaluated code")
    for path, sha in gate["validation_artifacts"].items():
        tracked[Path(path)] = file_sha256(Path(path))
        if tracked[Path(path)] != sha:
            raise ValueError("Review provenance SHA mismatch")
    completion = baseline_run / "review_completion.json"
    if not completion.exists():
        completion = baseline_run / "acceptance.json"
    tracked[completion] = file_sha256(completion)
    baseline_acceptance = json.loads(completion.read_text())
    manifest_sha = baseline_hashes[baseline_run / "manifest.json"]
    if baseline_acceptance.get("manifest_sha256") != manifest_sha or baseline_acceptance.get(
        "status"
    ) not in {
        "reviewed_proposals_offline_not_db_published",
        "accepted_offline_not_db_published",
        "accepted_batch_offline_not_db_published",
    }:
        raise ValueError("Baseline acceptance does not bind its manifest")
    source_paths = {
        p: sha
        for p, sha in candidate["input_hashes"].items()
        if p.endswith("jobs_analysis.parquet")
    }
    if len(source_paths) != 1 or any(
        baseline["input_hashes"].get(p) != sha for p, sha in source_paths.items()
    ):
        raise ValueError("Batch and baseline have different source input")
    source_path, source_sha = next(iter(source_paths.items()))
    tracked[Path(source_path)] = file_sha256(Path(source_path))
    if tracked[Path(source_path)] != source_sha:
        raise ValueError("Source input SHA mismatch")
    old_status = pq.read_table(baseline_run / "job_skill_status.parquet")
    new_status = pq.read_table(candidate_run / "job_skill_status.parquet")
    if not old_status.select(["job_id", "job_industry", "year", "requirements_text_hash"]).equals(
        new_status.select(["job_id", "job_industry", "year", "requirements_text_hash"])
    ):
        raise ValueError("Batch population, order or source hashes differ")
    mask = pc.is_in(new_status["job_industry"], value_set=pa.array(scope))
    scoped_rows = new_status.filter(mask).to_pylist()
    statuses = {r["job_id"]: r for r in scoped_rows}
    if len(statuses) != len(scoped_rows):
        raise ValueError("Duplicate batch status ID")
    if any(
        r["status"] not in {"out_of_scope", "missing_requirements", "unusable_requirements"}
        for r in old_status.filter(mask).to_pylist()
    ):
        raise ValueError("Batch already processed in baseline; do not overwrite it")
    source_texts = {}
    for batch in pq.ParquetFile(source_path).iter_batches(columns=["id", "requirements"]):
        for row in batch.to_pylist():
            if row["id"] in statuses:
                source_texts[row["id"]] = row["requirements"]
                if statuses[row["id"]]["requirements_text_hash"] != (
                    text_hash(row["requirements"]) if row["requirements"] is not None else None
                ):
                    raise ValueError("Batch source hash mismatch")
    pairs = pq.read_table(candidate_run / "job_skill_match.parquet").to_pylist()
    taxonomy = load_taxonomy(candidate_run / "taxonomy_snapshot")
    if any(
        r["skill_code"] not in taxonomy.skills
        or taxonomy.skills[r["skill_code"]].name != r["skill_name"]
        for r in pairs
    ):
        raise ValueError("Batch pair code or canonical name mismatch")
    for row in pq.read_table(baseline_run / "job_skill_match.parquet").to_pylist():
        if row["skill_code"] in taxonomy.skills and (
            taxonomy.skills[row["skill_code"]].name != row["skill_name"]
        ):
            raise ValueError("Batch changes an existing skill name")
    pair_keys = {(r["job_id"], r["skill_code"]) for r in pairs}
    if len(pair_keys) != len(pairs) or any(i not in statuses for i, _ in pair_keys):
        raise ValueError("Duplicate or out-of-scope batch pair")
    evidence = pq.read_table(candidate_run / "job_skill_evidence.parquet").to_pylist()
    positive_keys = set()
    evidence_counts: Counter[int] = Counter()
    for row in evidence:
        ident = row["job_id"]
        text = source_texts.get(ident)
        if (
            text is None
            or row["skill_code"] not in taxonomy.skills
            or not (
                0
                <= row["context_start"]
                <= row["start"]
                < row["end"]
                <= row["context_end"]
                <= len(text)
                and text[row["start"] : row["end"]] == row["text"]
                and text[row["context_start"] : row["context_end"]] == row["context_text"]
                and text_hash(text) == row["requirements_text_hash"]
            )
        ):
            raise ValueError("Invalid batch evidence offsets/text/hash/FK")
        evidence_counts[ident] += 1
        if row["positive_pair_included"]:
            if row["context"] not in candidate["policy"]["positive_contexts"]:
                raise ValueError("Batch pair includes non-positive evidence")
            positive_keys.add((ident, row["skill_code"]))
    if positive_keys != pair_keys:
        raise ValueError("Batch pairs differ from positive evidence")
    pair_counts = Counter(i for i, _ in pair_keys)
    if any(
        r["positive_skill_count"] != pair_counts[i] or r["evidence_count"] != evidence_counts[i]
        for i, r in statuses.items()
    ):
        raise ValueError("Batch status counts mismatch")
    report = {
        "status": "accepted_batch_offline_not_db_published",
        "batch": batch_name,
        "scope": list(scope),
        "deferred_industries": sorted(set(approved_scope) - set(scope)),
        "batch_jobs": len(statuses),
        "batch_jobs_with_skills": len(pair_counts),
        "added_pairs": len(pair_keys),
        "added_evidence": len(evidence),
        "batch_status_counts": dict(Counter(r["status"] for r in statuses.values())),
        "semantic_reference": "two blind AI references, adjudicated; not human gold",
        "baseline_outside_batch_preserved": True,
    }
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        for name, schema in ARTIFACT_SCHEMAS.items():
            old = pq.read_table(baseline_run / name)
            new = pq.read_table(candidate_run / name)
            if name == "job_skill_status.parquet":
                # Both tables are in identical source order.
                columns = [pc.if_else(mask, new[c], old[c]) for c in schema.names]
                merged = pa.Table.from_arrays(columns, schema=schema)
                if not merged.filter(pc.invert(mask)).equals(old.filter(pc.invert(mask))):
                    raise ValueError("Outside-batch statuses changed")
            else:
                if any(i in statuses for i in old["job_id"].to_pylist()):
                    raise ValueError("Baseline has existing batch pairs or evidence")
                merged = pa.concat_tables([old, new])
                if not merged.slice(0, old.num_rows).equals(old):
                    raise ValueError("Baseline records changed")
            pq.write_table(merged, stage / name, compression="zstd")
            if not pq.read_table(stage / name).equals(merged):
                raise ValueError("Merged artifact readback failed")
        (stage / "batch_report.json").write_text(json_text(report))
        if any(file_sha256(p) != sha for p, sha in tracked.items()):
            raise ValueError("Input changed during batch merge")
        manifest = {
            **report,
            "input_hashes": {str(p.resolve()): sha for p, sha in tracked.items()},
            "baseline_run": str(baseline_run.resolve()),
            "candidate_run": str(candidate_run.resolve()),
            "gate_sha256": tracked[gate_path],
            "source": candidate["source"],
            "artifacts": {p.name: {"sha256": file_sha256(p)} for p in stage.iterdir()},
        }
        (stage / "manifest.json").write_text(json_text(manifest))
        (stage / "acceptance.json").write_text(
            json_text(
                {
                    "status": report["status"],
                    "manifest_sha256": file_sha256(stage / "manifest.json"),
                    "gate_sha256": tracked[gate_path],
                    "database_published": False,
                }
            )
        )
        if destination.exists():
            raise ValueError("Output appeared during batch merge")
        os.rename(stage, destination)
    return report
