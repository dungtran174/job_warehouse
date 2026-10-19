"""Apply evidence-bound adjudications to an immutable needs-review population.

This imports reviewed claims, not new global extraction rules. Semantic decisions
remain in an external, hashed bundle; technical validation cannot prove meaning.
"""

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.input import (
    json_text,
    require_new_destination,
    staging_directory,
    verify_jobs_run,
)
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS, EVIDENCE_SCHEMA, PAIR_SCHEMA

VERSION = "curated-skills-review-v4"
DECISIONS = {"accept", "reject", "unclear"}


def evidence_start(row: dict[str, str], text: str) -> int:
    """Keep an adjudicated occurrence when the same quote appears several times."""
    quote = row["evidence"]
    supplied = row.get("evidence_start", "")
    start = int(supplied) if supplied else text.index(quote)
    if start < 0 or text[start : start + len(quote)] != quote:
        raise ValueError("Adjudicated evidence start does not match source text")
    return start


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _tracked_bundle(directory: Path, document: dict[str, Any]) -> dict[Path, str]:
    hashes = {directory / "bundle.json": file_sha256(directory / "bundle.json")}
    for name, sha in document["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError("Review bundle contains an invalid path")
        if file_sha256(path) != sha:
            raise ValueError(f"Review bundle SHA mismatch: {name}")
        hashes[path] = sha
    required = {"source.csv", "details.csv", "claims.csv", "catalogue.csv", "policy.json"}
    if not required <= set(document["files"]):
        raise ValueError("Review bundle is incomplete")
    return hashes


def _validate_claims(
    bundle: Path,
    jobs: dict[int, dict[str, Any]],
    baseline_catalogue: list[dict[str, str]],
    *,
    proposals: bool = False,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    catalogue = read_csv(bundle / "catalogue.csv")
    codes = {r["skill_code"]: r for r in catalogue}
    if len(codes) != len(catalogue) or any(
        not re.fullmatch(r"[a-z][a-z0-9_]*", r["skill_code"])
        or not r["skill_name"].strip()
        or r["skill_group"] not in {"technology", "tool", "domain", "language"}
        or any(x in r["skill_name"].casefold() for x in ("kỹ năng mềm", "phẩm chất"))
        for r in catalogue
    ):
        raise ValueError("Invalid or out-of-scope review catalogue")
    if len({r["skill_name"].casefold() for r in catalogue}) != len(catalogue):
        raise ValueError("Duplicate canonical skill name")
    if any(codes.get(r["skill_code"]) != r for r in baseline_catalogue):
        raise ValueError("Baseline taxonomy must remain unchanged")

    source = read_csv(bundle / "source.csv")
    id_column = "id" if proposals else "job_id"
    source_by_id = {int(r[id_column]): r for r in source}
    if len(source_by_id) != len(source) or set(source_by_id) != set(jobs):
        raise ValueError("Review IDs differ from needs-review population")
    for ident, job in jobs.items():
        row = source_by_id[ident]
        if any(str(job[k]) != row[k] for k in ("requirements", "job_industry", "year")):
            raise ValueError("Review source differs from S4")

    details = read_csv(bundle / "details.csv")
    expected = {f"csv:{i}": row for i, row in enumerate(details, 2)}
    detail_ids = {int(r[id_column]) for r in details}
    if not detail_ids <= set(jobs) or (not proposals and detail_ids != set(jobs)):
        raise ValueError("Detailed review population mismatch")
    summary: dict[int, Counter[str]] = defaultdict(Counter)
    accepted_names: dict[int, set[str]] = defaultdict(set)
    for row in details:
        ident = int(row[id_column])
        if proposals:
            quote = row["trích dẫn nguyên văn làm bằng chứng"]
            if not quote or quote not in jobs[ident]["requirements"]:
                raise ValueError("Original proposal evidence is not in requirements")
            continue
        if row["kết luận"] not in {"lấy", "không lấy", "chưa rõ"}:
            raise ValueError("Unknown original review conclusion")
        quote = row["trích dẫn nguyên văn"]
        if not quote or quote not in jobs[ident]["requirements"]:
            raise ValueError("Original review evidence is not in requirements")
        summary[ident][row["kết luận"]] += 1
        if row["kết luận"] == "lấy":
            accepted_names[ident].add(row["tên kỹ năng chuẩn"])
    for ident, row in source_by_id.items():
        if proposals:
            continue
        for decision, key in (
            ("lấy", "số kỹ năng lấy"),
            ("không lấy", "số kỹ năng không lấy"),
            ("chưa rõ", "số kỹ năng chưa rõ"),
        ):
            if summary[ident][decision] != int(row[key]):
                raise ValueError("Aggregate and detailed review disagree")
        if accepted_names[ident] != {
            s.strip() for s in row["tên kỹ năng chuẩn được lấy"].split(";") if s.strip()
        }:
            raise ValueError("Aggregate accepted names disagree with details")

    claims = read_csv(bundle / "claims.csv")
    seen: set[str] = set()
    covered: set[str] = set()
    for row in claims:
        claim = row["claim_id"]
        if claim in seen:
            raise ValueError("Duplicate review claim")
        seen.add(claim)
        ident = int(row["job_id"])
        if ident not in jobs or row["decision"] not in DECISIONS:
            raise ValueError("Invalid review claim population or decision")
        if claim in expected:
            original = expected[claim]
            if proposals:
                original = {
                    "job_id": original["id"],
                    "tên kỹ năng chuẩn": original["tên kỹ năng đề xuất"],
                    "kết luận": "proposed",
                    "trích dẫn nguyên văn": original["trích dẫn nguyên văn làm bằng chứng"],
                }
            if any(
                row[key] != original[source_key]
                for key, source_key in (
                    ("job_id", "job_id"),
                    ("source_skill_name", "tên kỹ năng chuẩn"),
                    ("source_decision", "kết luận"),
                    ("source_evidence", "trích dẫn nguyên văn"),
                )
            ):
                raise ValueError("Original claim was changed")
            covered.add(claim)
        elif not claim.startswith("extra:") or any(
            row[k] for k in ("source_skill_name", "source_decision", "source_evidence")
        ):
            raise ValueError("Untraceable added claim")
        if row["requirements_text_hash"] != text_hash(jobs[ident]["requirements"]):
            raise ValueError("Claim requirements hash mismatch")
        quote = row["evidence"]
        if not quote or quote not in jobs[ident]["requirements"] or not row["reason"]:
            raise ValueError("Invalid adjudicated evidence or missing reason")
        evidence_start(row, jobs[ident]["requirements"])
        if row["decision"] == "accept":
            if row["skill_code"] not in codes:
                raise ValueError("Accepted claim has no canonical skill")
            if row["skill_name"] != codes[row["skill_code"]]["skill_name"]:
                raise ValueError("Canonical name/code mismatch")
            if any(x in row["source_skill_name"].casefold() for x in ("kỹ năng mềm", "phẩm chất")):
                raise ValueError("Cannot accept soft skills or traits")
    if covered != set(expected):
        raise ValueError("Original review claims omitted")
    return claims, codes


def apply_review(
    jobs_run: Path,
    baseline_run: Path,
    bundle: Path,
    output_dir: Path,
    *,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    """Add curated pairs for all held-out jobs, preserving every other job."""
    destination = require_new_destination(output_dir)
    verified = verify_jobs_run(jobs_run, allow_unpinned_fixture=allow_unpinned_fixture)
    document = json.loads((bundle / "bundle.json").read_text())
    kind = document.get("kind", "held_out_review")
    if kind not in {"held_out_review", "no_match_proposals", "no_proposal_followup"}:
        raise ValueError("Unknown review bundle kind")
    followup = kind == "no_proposal_followup"
    proposals = kind in {"no_match_proposals", "no_proposal_followup"}
    tracked = _tracked_bundle(bundle, document)
    policy = json.loads((bundle / "policy.json").read_text())
    if policy.get("version") != document["policy_version"]:
        raise ValueError("Review policy version mismatch")
    implementation_sha = file_sha256(Path(__file__))
    manifest_path = baseline_run / "manifest.json"
    baseline = json.loads(manifest_path.read_text())
    tracked[manifest_path] = file_sha256(manifest_path)
    if tracked[manifest_path] != document["baseline_manifest_sha256"]:
        raise ValueError("Baseline manifest differs from review bundle")
    if baseline["input_hashes"].get(str(verified.parquet)) != file_sha256(verified.parquet):
        raise ValueError("Baseline skills and review use different S4 input")
    if not allow_unpinned_fixture:
        acceptance_path = baseline_run / (
            "review_completion.json" if proposals else "acceptance.json"
        )
        tracked[acceptance_path] = file_sha256(acceptance_path)
        acceptance = json.loads(acceptance_path.read_text())
        expected_acceptance = {
            "held_out_review": "accepted_offline_pilot_three_industries",
            "no_match_proposals": "reviewed_claims_offline_not_db_published",
            "no_proposal_followup": "reviewed_proposals_offline_not_db_published",
        }[kind]
        if (
            tracked[acceptance_path] != document["baseline_acceptance_sha256"]
            or acceptance.get("manifest_sha256") != tracked[manifest_path]
            or acceptance.get("status") != expected_acceptance
        ):
            raise ValueError("Baseline acceptance mismatch")
        if proposals:
            expected_status = (
                "curated_proposals_applied_offline_not_db_published"
                if followup
                else "curated_review_applied_offline_not_db_published"
            )
            if baseline.get("status") != expected_status:
                raise ValueError(
                    "Follow-up requires the completed no-match review"
                    if followup
                    else "No-match proposals require the completed held-out review"
                )
            audit_path = baseline_run / "technical_audit.json"
            tracked[audit_path] = file_sha256(audit_path)
            if tracked[audit_path] != acceptance["technical_audit_sha256"]:
                raise ValueError("Baseline technical audit SHA mismatch")
            previous_bundle = baseline_run / "review_bundle"
            tracked.update(
                _tracked_bundle(
                    previous_bundle, json.loads((previous_bundle / "bundle.json").read_text())
                )
            )
    for name, detail in baseline["artifacts"].items():
        path = baseline_run / name
        if not path.resolve().is_relative_to(baseline_run.resolve()):
            raise ValueError("Invalid baseline artifact path")
        tracked[path] = file_sha256(path)
        if tracked[path] != detail["sha256"]:
            raise ValueError("Baseline artifact SHA mismatch")
    for name, schema in ARTIFACT_SCHEMAS.items():
        if pq.read_schema(baseline_run / name) != schema:
            raise ValueError("Baseline schema mismatch")
    targets: set[int] = set()
    target_status = (
        "review_no_proposal" if followup else "processed_no_match" if proposals else "needs_review"
    )
    with pq.ParquetFile(baseline_run / "job_skill_status.parquet") as reader:
        for batch in reader.iter_batches(columns=["job_id", "status"]):
            targets.update(r["job_id"] for r in batch.to_pylist() if r["status"] == target_status)
    jobs = {row["id"]: row for batch in verified.batches() for row in batch if row["id"] in targets}
    if not targets or set(jobs) != targets:
        raise ValueError("Missing needs-review S4 jobs")
    claims, codes = _validate_claims(
        bundle,
        jobs,
        read_csv(
            baseline_run
            / ("review_bundle/catalogue.csv" if proposals else "taxonomy_snapshot/taxonomy.csv")
        ),
        proposals=proposals,
    )
    by_job: dict[int, list[dict[str, str]]] = defaultdict(list)
    additions = {}
    new_evidence = []
    for row in claims:
        ident = int(row["job_id"])
        by_job[ident].append(row)
        if row["decision"] != "accept":
            continue
        code = row["skill_code"]
        additions[ident, code] = {
            "job_id": ident,
            "skill_code": code,
            "skill_name": codes[code]["skill_name"],
        }
        quote = row["evidence"]
        start = evidence_start(row, jobs[ident]["requirements"])
        new_evidence.append(
            {
                "job_id": ident,
                "skill_code": code,
                "start": start,
                "end": start + len(quote),
                "text": quote,
                "context_start": start,
                "context_end": start + len(quote),
                "context_text": quote,
                "context": "reviewed_positive",
                "rule_id": row["claim_id"],
                "logic": row["reason"],
                "group_id": "condition:" + row["claim_id"] if row["condition"] else None,
                "requirements_text_hash": row["requirements_text_hash"],
                "positive_pair_included": True,
                "taxonomy_version": document["taxonomy_version"],
                "extractor_version": VERSION,
                "policy_version": document["policy_version"],
            }
        )
    pairs = pq.read_table(baseline_run / "job_skill_match.parquet").to_pylist()
    keys = {(r["job_id"], r["skill_code"]) for r in pairs}
    if len(keys) != len(pairs) or any(r["job_id"] in targets for r in pairs):
        raise ValueError("Baseline pairs duplicate or unexpectedly include held-out jobs")
    pairs.extend(additions[k] for k in sorted(additions))
    statuses: Counter[str] = Counter()
    positive_counts = Counter(k[0] for k in additions)
    evidence_counts = Counter(r["job_id"] for r in new_evidence)
    with staging_directory(destination) as temporary:
        stage = Path(temporary)
        shutil.copytree(bundle, stage / "review_bundle")
        pq.write_table(
            pa.Table.from_pylist(pairs, schema=PAIR_SCHEMA), stage / "job_skill_match.parquet"
        )
        for name in ("job_skill_status.parquet", "job_skill_evidence.parquet"):
            with (
                pq.ParquetFile(baseline_run / name) as reader,
                pq.ParquetWriter(
                    stage / name, ARTIFACT_SCHEMAS[name], compression="snappy"
                ) as writer,
            ):
                for batch in reader.iter_batches():
                    if name == "job_skill_evidence.parquet":
                        writer.write_batch(batch)
                        continue
                    rows = batch.to_pylist()
                    for row in rows:
                        ident = row["job_id"]
                        if ident in targets:
                            if row["requirements_text_hash"] != text_hash(
                                jobs[ident]["requirements"]
                            ):
                                raise ValueError("Baseline status text hash mismatch")
                            pending = any(c["decision"] == "unclear" for c in by_job[ident])
                            row["status"] = (
                                "reviewed_partial_match"
                                if pending and positive_counts[ident]
                                else "needs_review"
                                if pending
                                else "reviewed_match"
                                if positive_counts[ident]
                                else "review_no_proposal"
                                if proposals and not by_job[ident]
                                else "reviewed_no_match"
                            )
                            row["positive_skill_count"] = positive_counts[ident]
                            row["evidence_count"] += evidence_counts[ident]
                            row["reasons"] = [
                                "curated_followup_applied" if followup else "curated_review_applied"
                            ] + (["unresolved_individual_claims"] if pending else [])
                            if row["status"] == "review_no_proposal":
                                row["reasons"] = ["no_submitted_proposal_not_proof_of_absence"]
                        statuses[row["status"]] += 1
                    writer.write_table(pa.Table.from_pylist(rows, schema=ARTIFACT_SCHEMAS[name]))
                if name == "job_skill_evidence.parquet":
                    writer.write_table(pa.Table.from_pylist(new_evidence, schema=EVIDENCE_SCHEMA))
        artifacts = {}
        for name, schema in ARTIFACT_SCHEMAS.items():
            path = stage / name
            with pq.ParquetFile(path) as reader:
                if reader.schema_arrow != schema:
                    raise ValueError("Review output schema mismatch")
                artifacts[name] = {"sha256": file_sha256(path), "rows": reader.metadata.num_rows}
        if artifacts["job_skill_status.parquet"]["rows"] != verified.rows:
            raise ValueError("Review output population mismatch")
        if pq.read_table(stage / "job_skill_match.parquet").to_pylist() != pairs:
            raise ValueError("Review pair readback mismatch")
        verified.check_unchanged()
        if any(file_sha256(path) != sha for path, sha in tracked.items()):
            raise ValueError("Review inputs changed during processing")
        if file_sha256(Path(__file__)) != implementation_sha:
            raise ValueError("Review implementation changed during processing")
        report = {
            "status": (
                "curated_proposals_applied_offline_not_db_published"
                if proposals
                else "curated_review_applied_offline_not_db_published"
            ),
            "bundle_kind": kind,
            "created_at": datetime.now(UTC).isoformat(),
            "version": VERSION,
            "baseline_run": str(baseline_run.resolve()),
            "jobs_run": str(jobs_run.resolve()),
            "source": verified.manifest["source"],
            "input_hashes": {str(p): sha for p, sha in (tracked | verified.hashes).items()},
            "implementation_sha256": implementation_sha,
            "target_jobs": len(targets),
            "source_claims": len(read_csv(bundle / "details.csv")),
            "adjudicated_claims": len(claims),
            "decisions": dict(Counter(r["decision"] for r in claims)),
            "added_pairs": len(additions),
            "total_pairs": len(pairs),
            "catalogue_concepts": len(codes),
            "status_counts": dict(statuses),
            "artifacts": artifacts,
            "limits": [
                "AI semantic review with owner policy decisions; not human ground truth.",
                f"Expanded vocabulary applied only to baseline {target_status} jobs.",
                "No submitted proposal is not evidence that the job has no skills.",
                "Baseline precision/recall does not certify this expanded review vocabulary.",
                "No PostgreSQL publication or completeness claim for every skill in a job.",
            ],
        }
        (stage / "manifest.json").write_text(json_text(report))
        stage.rename(destination)
    return report
