"""Combine a new uniform automatic run with immutable document-bound reviews."""

import csv
import json
import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.expanded import has_marketing_context
from job_warehouse.skills.input import SCOPE, json_text, require_new_destination, staging_directory
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.review_import import _tracked_bundle, read_csv
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS


def reviewed_code_after_policy(code: str, quote: str) -> str:
    """Apply the owner's explicit specialist-label decision without losing history."""
    if code == "tax_reporting" and not re.search(r"báo cáo thuế|tax report", quote, re.I):
        if re.search(r"quyết toán thuế", quote, re.I):
            return "review_quyet_toan_thue"
        if re.search(r"kê khai thuế|khai báo thuế|khai thuế|tax declaration", quote, re.I):
            return "review_ke_khai_thue"
    if (
        code == "social_media"
        and re.search(r"(?:quản lý|quản trị|phát triển).{0,30}fanpage", quote, re.I)
        and not re.search(
            r"social media|social marketing|mạng xã hội|truyền thông xã hội|marketing facebook",
            quote,
            re.I,
        )
    ):
        return "review_quan_tri_fanpage"
    return code


def checked_artifacts(run: Path) -> tuple[dict[str, Any], dict[Path, str]]:
    manifest_path = run / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    tracked = {manifest_path: file_sha256(manifest_path)}
    for name, artifact in manifest["artifacts"].items():
        path = (run / name).resolve()
        if not path.is_relative_to(run.resolve()) or not path.is_file():
            raise ValueError("Invalid run artifact")
        tracked[path] = file_sha256(path)
        if tracked[path] != artifact["sha256"]:
            raise ValueError("Run artifact SHA mismatch")
    for name, schema in ARTIFACT_SCHEMAS.items():
        if name not in manifest["artifacts"] or pq.read_schema(run / name) != schema:
            raise ValueError("Incomplete or invalid skill run")
    return manifest, tracked


def merge_expansion(
    automatic_run: Path, baseline_run: Path, review_runs: list[Path], output_dir: Path
) -> dict[str, Any]:
    """Recompute automatic pairs, preserve reviewed positives, block reviewed negatives.

    This does not semantically accept the new rules or replace a latest pointer.
    Every review is tied to the same S4 snapshot and exact requirements hash.
    """
    destination = require_new_destination(output_dir)
    automatic, tracked = checked_artifacts(automatic_run)
    baseline, hashes = checked_artifacts(baseline_run)
    tracked.update(hashes)
    if automatic.get("extractor_version") not in {
        "requirements-skills-expanded-v1",
        "requirements-skills-expanded-v2",
        "requirements-skills-expanded-v3",
        "requirements-skills-expanded-v4",
        "requirements-skills-expanded-v5",
    }:
        raise ValueError("Expected a uniform expanded automatic run")
    s4 = {p: h for p, h in automatic["input_hashes"].items() if p.endswith("jobs_analysis.parquet")}
    if not s4 or any(baseline["input_hashes"].get(p) != h for p, h in s4.items()):
        raise ValueError("Expanded and baseline runs use different S4 input")
    completion = baseline_run / "review_completion.json"
    tracked[completion] = file_sha256(completion)
    document = json.loads(completion.read_text())
    if document.get("manifest_sha256") != tracked[baseline_run / "manifest.json"]:
        raise ValueError("Baseline review completion SHA mismatch")
    catalogue = read_csv(automatic_run / "taxonomy_snapshot/taxonomy.csv")
    names = {r["skill_code"]: r["skill_name"] for r in catalogue}
    codes_by_name = {v.casefold(): k for k, v in names.items()}
    statuses = pq.read_table(automatic_run / "job_skill_status.parquet").to_pylist()
    by_id = {r["job_id"]: r for r in statuses}
    if len(by_id) != len(statuses):
        raise ValueError("Duplicate automatic status job")
    source_path = Path(next(iter(s4)))
    tracked[source_path] = file_sha256(source_path)
    if tracked[source_path] != s4[str(source_path)]:
        raise ValueError("S4 content changed since automatic run")
    source_texts = {}
    for batch in pq.ParquetFile(source_path).iter_batches(columns=["id", "requirements"]):
        for row in batch.to_pylist():
            if by_id[row["id"]]["job_industry"] in SCOPE:
                source_texts[row["id"]] = row["requirements"]
                if by_id[row["id"]]["requirements_text_hash"] != (
                    text_hash(row["requirements"]) if row["requirements"] is not None else None
                ):
                    raise ValueError("S4 source text differs from status hash")
    accepted: set[tuple[int, str]] = set()
    rejected: set[tuple[int, str]] = set()
    review_evidence: list[dict[str, Any]] = []
    migrated: set[tuple[int, str, str]] = set()
    for batch in pq.ParquetFile(baseline_run / "job_skill_evidence.parquet").iter_batches():
        for row in batch.to_pylist():
            if row["context"] != "reviewed_positive":
                continue
            ident, code = row["job_id"], row["skill_code"]
            if code not in names or (
                by_id[ident]["requirements_text_hash"] != row["requirements_text_hash"]
            ):
                raise ValueError("Baseline reviewed positive differs from expanded input")
            updated_code = reviewed_code_after_policy(code, row["text"])
            if updated_code not in names:
                raise ValueError("Policy target missing from taxonomy")
            if updated_code != code:
                migrated.add((ident, code, updated_code))
                row = dict(
                    row,
                    skill_code=updated_code,
                    rule_id="owner_specialist_policy:" + row["rule_id"],
                )
            accepted.add((ident, updated_code))
            review_evidence.append(row)
    for run in review_runs:
        review_manifest, hashes = checked_artifacts(run)
        tracked.update(hashes)
        if any(review_manifest["input_hashes"].get(p) != h for p, h in s4.items()):
            raise ValueError("Review uses different S4 snapshot")
        bundle = run / "review_bundle"
        bundle_doc = json.loads((bundle / "bundle.json").read_text())
        tracked.update(_tracked_bundle(bundle, bundle_doc))
        for claim in read_csv(bundle / "claims.csv"):
            ident = int(claim["job_id"])
            status = by_id.get(ident)
            if (
                status is None
                or status["job_industry"] not in SCOPE
                or (status["requirements_text_hash"] != claim["requirements_text_hash"])
            ):
                raise ValueError("Review ID/hash/scope differs from automatic run")
            code = claim["skill_code"] or codes_by_name.get(claim["skill_name"].casefold())
            if claim["decision"] == "accept":
                if code not in names or names[code] != claim["skill_name"]:
                    raise ValueError("Reviewed positive missing in expanded taxonomy")
                updated_code = reviewed_code_after_policy(code, claim["evidence"])
                if updated_code not in names:
                    raise ValueError("Policy target missing from taxonomy")
                if updated_code != code:
                    migrated.add((ident, code, updated_code))
                accepted.add((ident, updated_code))
            elif claim["decision"] == "reject" and code:
                rejected.add((ident, code))
                rejected.add((ident, reviewed_code_after_policy(code, claim["evidence"])))
        for batch in pq.ParquetFile(run / "job_skill_evidence.parquet").iter_batches():
            for row in batch.to_pylist():
                if row["context"] == "reviewed_positive":
                    updated_code = reviewed_code_after_policy(row["skill_code"], row["text"])
                    if updated_code != row["skill_code"]:
                        row = dict(
                            row,
                            skill_code=updated_code,
                            rule_id="owner_specialist_policy:" + row["rule_id"],
                        )
                    review_evidence.append(row)
    # A specific reviewed positive takes precedence over a rejected occurrence of
    # the same concept elsewhere. No reviewed negative is silently reintroduced.
    retired_by_owner = {
        (ident, code)
        for ident, code in accepted
        if code == "content_marketing" and not has_marketing_context(source_texts[ident])
    }
    accepted -= retired_by_owner
    rejected.update(retired_by_owner)
    for row in review_evidence:
        if (row["job_id"], row["skill_code"]) in retired_by_owner:
            row["context"] = "reviewed_superseded_by_owner_policy"
            row["positive_pair_included"] = False
            row["rule_id"] = "owner_requires_marketing_context_outside_degree"
    rejected -= accepted
    rows = pq.read_table(automatic_run / "job_skill_match.parquet").to_pylist()
    pairs = {(r["job_id"], r["skill_code"]): r for r in rows}
    if len(pairs) != len(rows):
        raise ValueError("Duplicate automatic pair")
    blocked = sorted(set(pairs) & rejected)
    for key in blocked:
        del pairs[key]
    for ident, code in accepted:
        pairs[ident, code] = {"job_id": ident, "skill_code": code, "skill_name": names[code]}
    evidence_rows = pq.read_table(automatic_run / "job_skill_evidence.parquet").to_pylist()
    for r in evidence_rows:
        if (r["job_id"], r["skill_code"]) in rejected:
            r["positive_pair_included"] = False
            r["context"] = "reviewed_excluded"
            r["rule_id"] = "preserved_document_bound_rejection"
    # Previous review runs include earlier evidence. Deduplicate exact rows only.
    seen = {json.dumps(r, sort_keys=True, ensure_ascii=False) for r in evidence_rows}
    for r in review_evidence:
        encoded = json.dumps(r, sort_keys=True, ensure_ascii=False)
        if encoded not in seen:
            evidence_rows.append(r)
            seen.add(encoded)
    if any(
        r["job_id"] not in by_id
        or r["skill_code"] not in names
        or r["requirements_text_hash"] != by_id[r["job_id"]]["requirements_text_hash"]
        or source_texts[r["job_id"]][r["start"] : r["end"]] != r["text"]
        or source_texts[r["job_id"]][r["context_start"] : r["context_end"]] != r["context_text"]
        or (r["positive_pair_included"] and (r["job_id"], r["skill_code"]) not in pairs)
        for r in evidence_rows
    ):
        raise ValueError("Expanded evidence FK or requirements hash mismatch")
    positive_counts = Counter(ident for ident, _ in pairs)
    evidence_counts = Counter(r["job_id"] for r in evidence_rows)
    old_status = {
        r["job_id"]: r for r in pq.read_table(baseline_run / "job_skill_status.parquet").to_pylist()
    }
    if set(old_status) != set(by_id):
        raise ValueError("Job populations differ")
    gained_no_proposal = 0
    still_no_proposal = []
    for r in statuses:
        ident = r["job_id"]
        r["positive_skill_count"] = positive_counts[ident]
        r["evidence_count"] = evidence_counts[ident]
        if r["job_industry"] in SCOPE and r["status"] not in {
            "missing_requirements",
            "unusable_requirements",
        }:
            r["status"] = "expanded_match" if positive_counts[ident] else "expanded_no_match"
            r["reasons"] = sorted(
                set(r["reasons"] + ["uniform_expanded_rules_not_blind_validated"])
            )
        if old_status[ident]["status"] == "review_no_proposal":
            if positive_counts[ident]:
                gained_no_proposal += 1
            else:
                still_no_proposal.append(ident)
    old_pairs = {
        (r["job_id"], r["skill_code"])
        for r in pq.read_table(baseline_run / "job_skill_match.parquet").to_pylist()
    }
    report = {
        "status": "expanded_candidate_with_preserved_reviews_not_db_published",
        "jobs_with_skills": len(positive_counts),
        "skill_pairs": len(pairs),
        "baseline_jobs_with_skills": sum(
            r["positive_skill_count"] > 0 for r in old_status.values()
        ),
        "baseline_pairs": len(old_pairs),
        "added_pairs": len(set(pairs) - old_pairs),
        "removed_automatic_pairs": len(old_pairs - set(pairs)),
        "reviewed_positive_pairs_preserved": len(accepted),
        "reviewed_negative_pairs_blocked": len(blocked),
        "reviewed_pairs_routed_to_specialist_by_owner": len(migrated),
        "reviewed_content_pairs_superseded_by_owner_context_policy": len(retired_by_owner),
        "original_no_proposal_population": sum(
            r["status"] == "review_no_proposal" for r in old_status.values()
        ),
        "original_no_proposal_now_with_skills": gained_no_proposal,
        "original_no_proposal_still_no_match": len(still_no_proposal),
        "concepts": len(names),
        "concepts_with_pairs": len({c for _, c in pairs}),
        "statuses": dict(Counter(r["status"] for r in statuses)),
        "semantic_validation": "pending_expanded_rules_holdout; previous96_scores_not_applicable",
    }
    with staging_directory(destination) as temporary:
        stage = Path(temporary)
        shutil.copytree(automatic_run / "taxonomy_snapshot", stage / "taxonomy_snapshot")
        data = {
            "job_skill_match.parquet": [pairs[k] for k in sorted(pairs)],
            "job_skill_status.parquet": statuses,
            "job_skill_evidence.parquet": evidence_rows,
        }
        for name, records in data.items():
            schema = ARTIFACT_SCHEMAS[name]
            pq.write_table(
                pa.Table.from_pylist(records, schema=schema), stage / name, compression="zstd"
            )
            if pq.read_table(stage / name).to_pylist() != records:
                raise ValueError("Expanded readback mismatch")
        for filename, keys in (
            ("added_pairs.csv", sorted(set(pairs) - old_pairs)),
            ("removed_automatic_pairs.csv", sorted(old_pairs - set(pairs))),
            ("blocked_by_review.csv", blocked),
        ):
            with (stage / filename).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["job_id", "skill_code", "skill_name"])
                writer.writerows((i, c, names[c]) for i, c in keys)
        (stage / "remaining_no_proposal_ids.json").write_text(json_text(still_no_proposal))
        with (stage / "reviewed_specialist_policy_changes.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(["job_id", "previous_skill_code", "specialist_skill_code"])
            writer.writerows(sorted(migrated))
        (stage / "expansion_quality_report.json").write_text(json_text(report))
        if any(file_sha256(p) != h for p, h in tracked.items()):
            raise ValueError("Expansion input changed")
        manifest = {
            "status": report["status"],
            "created_at": datetime.now(UTC).isoformat(),
            "source": automatic["source"],
            "input_hashes": automatic["input_hashes"],
            "provenance": {str(p.resolve()): h for p, h in tracked.items()},
            "baseline_run": str(baseline_run.resolve()),
            "automatic_run": str(automatic_run.resolve()),
            "review_runs": [str(p.resolve()) for p in review_runs],
            "code_hashes": {
                str(p.resolve()): file_sha256(p) for p in Path(__file__).parent.glob("*.py")
            },
            "artifacts": {
                str(p.relative_to(stage)): {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in stage.rglob("*")
                if p.is_file()
            },
        }
        (stage / "manifest.json").write_text(json_text(manifest))
        if destination.exists():
            raise ValueError("Expansion output appeared during run")
        stage.rename(destination)
    return report
