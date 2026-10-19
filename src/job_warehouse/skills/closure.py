"""Close remaining review jobs once: clear keywords or no extraction, never pending."""

import json
import os
import re
import shutil
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.expansion_merge import checked_artifacts
from job_warehouse.skills.general import GENERAL_MAPPINGS, GeneralSkillMatcher
from job_warehouse.skills.input import (
    json_text,
    require_new_destination,
    staging_directory,
    verify_jobs_run,
)
from job_warehouse.skills.models import Extraction
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS, load_policy
from job_warehouse.skills.taxonomy import load_taxonomy

VERSION = "requirements-review-closure-v1"


def resolve_text(text: str, matcher: GeneralSkillMatcher) -> Extraction:
    """Reuse tested keywords, then exclude unclear degree/negation/interest claims."""
    base = matcher.extract(text)
    evidence = []
    for e in base.evidence:
        before = re.split(r"[.;\n]", text[max(0, e.start - 160) : e.start])[-1]
        reason = None
        if (
            e.skill_code == "log_car_driving"
            and not re.search(r"lái xe|ô tô|hạng|driving|driver", e.text, re.I)
            and re.search(r"ngữ pháp|CEFR|Goethe|tiếng Đức|tiếng Pháp", text, re.I)
        ):
            reason = "closure_b2_language_not_driving"
        if re.search(
            r"không (?:yêu cầu|cần|bắt buộc)(?: về)?"
            r"(?: kỹ năng| biết| sử dụng| có kinh nghiệm)*\s*$",
            before,
            re.I,
        ):
            reason = "closure_explicit_skill_waiver"
        if re.search(r"(?:muốn nâng cao|đang học|mong muốn học)[^.;\n]{0,45}$", before, re.I):
            reason = "closure_learning_interest_not_capability"
        if e.skill_code in {"hr_human_resources", "review_quan_ly_chat_luong"} and re.search(
            r"pháp luật\s*$|chuyển đổi số trong\s*$", before, re.I
        ):
            reason = "closure_law_or_software_purpose_not_operation"
        if reason or e.context == "ambiguous":
            e = replace(e, context="excluded", rule_id=reason or "closure_skip_unclear_keyword")
        evidence.append(e)
    codes = tuple(
        sorted({e.skill_code for e in evidence if e.context in {"required", "preferred"}})
    )
    return Extraction("processed_match" if codes else "processed_no_match", codes, tuple(evidence))


def close_reviews(
    jobs_run: Path, baseline_run: Path, output_dir: Path, *, allow_unpinned_fixture: bool = False
) -> dict[str, Any]:
    destination = require_new_destination(output_dir)
    source = verify_jobs_run(jobs_run, allow_unpinned_fixture=allow_unpinned_fixture)
    manifest, tracked = checked_artifacts(baseline_run)
    if manifest.get("input_hashes", {}).get(str(source.parquet.resolve())) != file_sha256(
        source.parquet
    ):
        raise ValueError("Baseline and closure use different jobs input")
    receipt = baseline_run / "freeze_receipt.json"
    tracked[receipt] = file_sha256(receipt)
    if (
        json.loads(receipt.read_text()).get("run_manifest_sha256")
        != tracked[baseline_run / "manifest.json"]
    ):
        raise ValueError("Baseline freeze receipt mismatch")
    assets = [
        *Path(__file__).parent.glob("*.py"),
        *GENERAL_MAPPINGS.glob("*.csv"),
        GENERAL_MAPPINGS / "policy.json",
    ]
    tracked.update({p: file_sha256(p) for p in assets})
    old_status = pq.read_table(baseline_run / "job_skill_status.parquet").to_pylist()
    if len({r["job_id"] for r in old_status}) != len(old_status) or len(old_status) != source.rows:
        raise ValueError("Invalid baseline population")
    baseline_by_id = {r["job_id"]: r for r in old_status}
    targets = {r["job_id"]: r for r in old_status if r["status"] == "needs_review"}
    if not targets or any(r["positive_skill_count"] for r in targets.values()):
        raise ValueError("Expected unpaired needs-review jobs")
    taxonomy = load_taxonomy(GENERAL_MAPPINGS)
    matcher = GeneralSkillMatcher(
        taxonomy, load_policy(GENERAL_MAPPINGS, scope=batch_scope("general_industries"))[0]
    )
    results: dict[int, Extraction] = {}
    additions: list[dict[str, Any]] = []
    new_evidence: list[dict[str, Any]] = []
    for batch in source.batches():
        for row in batch:
            ident = row["id"]
            baseline_row = baseline_by_id.get(ident)
            if baseline_row is None or (
                row["job_industry"],
                row["year"],
                text_hash(row["requirements"]) if row["requirements"] is not None else None,
            ) != (
                baseline_row["job_industry"],
                baseline_row["year"],
                baseline_row["requirements_text_hash"],
            ):
                raise ValueError("Baseline population differs from source")
            if ident not in targets:
                continue
            text = row["requirements"]
            old = targets[ident]
            if (
                text is None
                or text_hash(text) != old["requirements_text_hash"]
                or (row["job_industry"], row["year"]) != (old["job_industry"], old["year"])
            ):
                raise ValueError("Target text or source metadata mismatch")
            result = resolve_text(text, matcher)
            results[ident] = result
            additions.extend(
                {"job_id": ident, "skill_code": c, "skill_name": taxonomy.skills[c].name}
                for c in result.skill_codes
            )
            for e in result.evidence:
                new_evidence.append(
                    {
                        "job_id": ident,
                        **asdict(e),
                        "context_text": text[e.context_start : e.context_end],
                        "requirements_text_hash": text_hash(text),
                        "positive_pair_included": e.skill_code in result.skill_codes
                        and e.context in {"required", "preferred"},
                        "taxonomy_version": "general-industry-keywords-v1",
                        "extractor_version": VERSION,
                        "policy_version": "owner-close-remaining-reviews-20261019",
                    }
                )
    if set(results) != set(targets):
        raise ValueError("Missing target jobs")
    counts: Counter[str] = Counter()
    for row in old_status:
        if row["job_id"] in results:
            x = results[row["job_id"]]
            row.update(
                status=x.status,
                positive_skill_count=len(x.skill_codes),
                evidence_count=len(x.evidence),
                reasons=[
                    "closed_clear_keywords" if x.skill_codes else "closed_no_extractable_skill"
                ],
            )
        counts[row["status"]] += 1
    names = {}
    for batch in pq.ParquetFile(baseline_run / "job_skill_match.parquet").iter_batches():
        for row in batch.to_pylist():
            if row["job_id"] in targets:
                raise ValueError("Review target already has accepted pairs")
            names[row["skill_code"]] = row["skill_name"]
    if any(
        r["skill_code"] in names and names[r["skill_code"]] != r["skill_name"] for r in additions
    ):
        raise ValueError("Canonical skill name changed")
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        shutil.copytree(GENERAL_MAPPINGS, stage / "taxonomy_snapshot")
        for name, schema in ARTIFACT_SCHEMAS.items():
            with pq.ParquetWriter(stage / name, schema) as writer:
                if name == "job_skill_status.parquet":
                    writer.write_table(pa.Table.from_pylist(old_status, schema=schema))
                else:
                    for batch in pq.ParquetFile(baseline_run / name).iter_batches():
                        rows = batch.to_pylist()
                        if name == "job_skill_evidence.parquet":
                            rows = [r for r in rows if r["job_id"] not in targets]
                        if rows:
                            writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                    rows = additions if name == "job_skill_match.parquet" else new_evidence
                    if rows:
                        writer.write_table(pa.Table.from_pylist(rows, schema=schema))
        report = {
            "status": "closed_clear_keywords_or_no_extraction",
            "target_jobs": len(targets),
            "jobs_with_new_skills": sum(bool(x.skill_codes) for x in results.values()),
            "added_pairs": len(additions),
            "status_counts": dict(counts),
            "pending_review_jobs": counts.get("needs_review", 0),
            "outside_target_results_preserved": True,
            "database_published": False,
            "independent_quality_claim": False,
        }
        (stage / "closure_report.json").write_text(json_text(report))
        source.check_unchanged()
        if any(file_sha256(p) != sha for p, sha in tracked.items()):
            raise ValueError("Closure input changed")
        output = {
            **report,
            "source": source.manifest["source"],
            "baseline_run": str(baseline_run.resolve()),
            "input_hashes": {
                **{str(p.resolve()): h for p, h in tracked.items()},
                **{str(p.resolve()): h for p, h in source.hashes.items()},
            },
            "extractor_version": VERSION,
            "artifacts": {
                p.name: {"sha256": file_sha256(p)} for p in stage.iterdir() if p.is_file()
            },
        }
        (stage / "manifest.json").write_text(json_text(output))
        if destination.exists():
            raise ValueError("Output appeared during closure")
        os.rename(stage, destination)
    return report
