"""Reproducible local skill build with separate business pairs, evidence and status."""

import csv
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills import EXTRACTOR_VERSION, TAXONOMY_VERSION
from job_warehouse.skills.input import (
    PLACEHOLDERS,
    SCOPE,
    json_text,
    require_new_destination,
    staging_directory,
    verify_jobs_run,
)
from job_warehouse.skills.matcher import SkillMatcher
from job_warehouse.skills.models import ContextOverride, Extraction, SkillPolicy
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.taxonomy import MAPPINGS, load_taxonomy

PAIR_SCHEMA = pa.schema(
    [
        ("job_id", pa.int64()),
        ("skill_code", pa.string()),
        ("skill_name", pa.string()),
    ]
)
STATUS_SCHEMA = pa.schema(
    [
        ("job_id", pa.int64()),
        ("job_industry", pa.string()),
        ("year", pa.int16()),
        ("status", pa.string()),
        ("requirements_text_hash", pa.string()),
        ("positive_skill_count", pa.int32()),
        ("evidence_count", pa.int32()),
        ("reasons", pa.list_(pa.string())),
    ]
)
EVIDENCE_SCHEMA = pa.schema(
    [
        ("job_id", pa.int64()),
        ("skill_code", pa.string()),
        ("start", pa.int32()),
        ("end", pa.int32()),
        ("text", pa.string()),
        ("context_start", pa.int32()),
        ("context_end", pa.int32()),
        ("context_text", pa.string()),
        ("context", pa.string()),
        ("rule_id", pa.string()),
        ("logic", pa.string()),
        ("group_id", pa.string()),
        ("requirements_text_hash", pa.string()),
        ("positive_pair_included", pa.bool_()),
        ("taxonomy_version", pa.string()),
        ("extractor_version", pa.string()),
        ("policy_version", pa.string()),
    ]
)
ARTIFACT_SCHEMAS = {
    "job_skill_match.parquet": PAIR_SCHEMA,
    "job_skill_status.parquet": STATUS_SCHEMA,
    "job_skill_evidence.parquet": EVIDENCE_SCHEMA,
}


def _digest_rows(digest: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True).encode())
        digest.update(b"\n")


def load_policy(
    directory: Path = MAPPINGS, *, scope: tuple[str, ...] = SCOPE
) -> tuple[SkillPolicy, dict[str, Any]]:
    document: dict[str, Any] = json.loads((directory / "policy.json").read_text())
    if document.get("scope") != list(scope):
        raise ValueError("Skill scope differs from the approved industry labels")
    policy = SkillPolicy(
        document["version"],
        tuple(document["positive_contexts"]),
        document["certificate_policy"],
        tuple(ContextOverride(**entry) for entry in document.get("context_overrides", [])),
    )
    return policy, document


def run_skills(
    jobs_run: Path,
    output_dir: Path,
    *,
    taxonomy_dir: Path = MAPPINGS,
    batch_size: int = 2048,
    allow_unpinned_fixture: bool = False,
    expanded_context: bool = False,
    batch_name: str | None = None,
    enabled_industries: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    destination = require_new_destination(output_dir)
    source = verify_jobs_run(jobs_run, allow_unpinned_fixture=allow_unpinned_fixture)
    assets = [
        *Path(__file__).parent.glob("*.py"),
        *taxonomy_dir.glob("*.csv"),
        taxonomy_dir / "policy.json",
    ]
    asset_hashes = {p: file_sha256(p) for p in assets}
    taxonomy = load_taxonomy(taxonomy_dir)
    scope: tuple[str, ...] = SCOPE
    policy_scope: tuple[str, ...] = SCOPE
    if enabled_industries is not None and batch_name is None:
        raise ValueError("Industry subset requires an explicit batch")
    if batch_name is not None:
        from job_warehouse.skills.batches import batch_scope
        from job_warehouse.skills.scopes import processing_scope

        policy_scope = batch_scope(batch_name)
        scope = processing_scope(batch_name, enabled_industries)
        if expanded_context:
            raise ValueError("A batch cannot enable the experimental global expanded matcher")
    policy, policy_document = load_policy(taxonomy_dir, scope=policy_scope)
    matcher: SkillMatcher
    extractor_version, taxonomy_version = EXTRACTOR_VERSION, TAXONOMY_VERSION
    if batch_name == "construction_design_projects":
        from job_warehouse.skills.conservative import CONSERVATIVE_VERSION
        from job_warehouse.skills.construction import ConstructionSkillMatcher

        matcher = ConstructionSkillMatcher(taxonomy, policy)
        extractor_version = CONSERVATIVE_VERSION
        taxonomy_version = policy_document["taxonomy_version"]
    elif batch_name == "engineering_production":
        from job_warehouse.skills.conservative import CONSERVATIVE_VERSION
        from job_warehouse.skills.engineering import EngineeringSkillMatcher

        matcher = EngineeringSkillMatcher(taxonomy, policy)
        extractor_version = CONSERVATIVE_VERSION
        taxonomy_version = policy_document["taxonomy_version"]
    elif batch_name == "logistics_transport":
        from job_warehouse.skills.conservative import CONSERVATIVE_VERSION
        from job_warehouse.skills.logistics import LogisticsSkillMatcher

        matcher = LogisticsSkillMatcher(taxonomy, policy)
        extractor_version = CONSERVATIVE_VERSION
        taxonomy_version = policy_document["taxonomy_version"]
    elif batch_name == "hr_finance_legal":
        from job_warehouse.skills.conservative import (
            CONSERVATIVE_VERSION,
            KEYWORD_COMPLETION,
            ConservativeHRFinanceMatcher,
        )
        from job_warehouse.skills.hr_finance import HR_FINANCE_VERSION, HRFinanceSkillMatcher

        if policy_document.get("decisions", {}).get("completion_policy") == KEYWORD_COMPLETION:
            matcher = ConservativeHRFinanceMatcher(taxonomy, policy)
            extractor_version = CONSERVATIVE_VERSION
        else:
            matcher = HRFinanceSkillMatcher(taxonomy, policy)
            extractor_version = HR_FINANCE_VERSION
        taxonomy_version = policy_document["taxonomy_version"]
    elif batch_name == "real_estate":
        from job_warehouse.skills.real_estate import REAL_ESTATE_VERSION, RealEstateSkillMatcher

        matcher = RealEstateSkillMatcher(taxonomy, policy)
        extractor_version = REAL_ESTATE_VERSION
        taxonomy_version = policy_document["taxonomy_version"]
    elif batch_name == "sales_customer_service":
        from job_warehouse.skills.sales import SALES_EXTRACTOR_VERSION, SalesSkillMatcher

        matcher = SalesSkillMatcher(taxonomy, policy)
        extractor_version = SALES_EXTRACTOR_VERSION
        taxonomy_version = policy_document["taxonomy_version"]
    elif expanded_context:
        from job_warehouse.skills.expanded import (
            EXPANDED_TAXONOMY_VERSION,
            EXPANDED_VERSION,
            ExpandedSkillMatcher,
        )

        matcher = ExpandedSkillMatcher(taxonomy, policy)
        extractor_version, taxonomy_version = EXPANDED_VERSION, EXPANDED_TAXONOMY_VERSION
    else:
        matcher = SkillMatcher(taxonomy, policy)

    @lru_cache(maxsize=8192)
    def cached_extract(text: str) -> Extraction:
        return matcher.extract(text)

    counts: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    coverage: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    digests = {name: hashlib.sha256() for name in ARTIFACT_SCHEMAS}
    artifact_rows: Counter[str] = Counter()
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        writers = {
            name: pq.ParquetWriter(stage / name, schema, compression="zstd")
            for name, schema in ARTIFACT_SCHEMAS.items()
        }
        try:
            with (stage / "skill_review.csv").open("w", newline="", encoding="utf-8") as stream:
                review = csv.writer(stream)
                review.writerow(["job_id", "job_industry", "year", "reasons", "requirements"])
                for batch in source.batches(batch_size):
                    output: dict[str, list[dict[str, Any]]] = {name: [] for name in writers}
                    for row in batch:
                        ident, industry, year = row["id"], row["job_industry"], row["year"]
                        text = row["requirements"]
                        hashed = text_hash(text) if text is not None else None
                        in_scope = industry in scope
                        if text is None:
                            result = Extraction("missing_requirements")
                        elif text.strip().casefold() in PLACEHOLDERS:
                            result = Extraction("unusable_requirements")
                        elif not in_scope:
                            result = Extraction("out_of_scope")
                        else:
                            result = cached_extract(text)
                        counts["input_rows"] += 1
                        counts[result.status] += 1
                        cov = coverage[(industry, year)]
                        cov["rows"] += 1
                        cov[result.status] += 1
                        if in_scope:
                            counts["scope_rows"] += 1
                            if result.status not in {
                                "missing_requirements",
                                "unusable_requirements",
                            }:
                                counts["scope_eligible"] += 1
                            else:
                                counts[f"scope_{result.status}"] += 1
                        output["job_skill_status.parquet"].append(
                            {
                                "job_id": ident,
                                "job_industry": industry,
                                "year": year,
                                "status": result.status,
                                "requirements_text_hash": hashed,
                                "positive_skill_count": len(result.skill_codes),
                                "evidence_count": len(result.evidence),
                                "reasons": list(result.reasons),
                            }
                        )
                        if result.status in {"needs_review", "expanded_partial_match"}:
                            review.writerow(
                                [ident, industry, year, "; ".join(result.reasons), text]
                            )
                        if len(result.skill_codes) != len(set(result.skill_codes)):
                            raise ValueError("Duplicate job-skill pair")
                        for code in result.skill_codes:
                            output["job_skill_match.parquet"].append(
                                {
                                    "job_id": ident,
                                    "skill_code": code,
                                    "skill_name": taxonomy.skills[code].name,
                                }
                            )
                            skills[code] += 1
                        for evidence in result.evidence:
                            if text[evidence.start : evidence.end] != evidence.text:
                                raise ValueError("Evidence substring mismatch")
                            if (
                                not evidence.context_start
                                <= evidence.start
                                < evidence.end
                                <= evidence.context_end
                            ):
                                raise ValueError("Invalid evidence context offsets")
                            output["job_skill_evidence.parquet"].append(
                                {
                                    "job_id": ident,
                                    **asdict(evidence),
                                    "context_text": text[
                                        evidence.context_start : evidence.context_end
                                    ],
                                    "requirements_text_hash": hashed,
                                    "positive_pair_included": (
                                        evidence.skill_code in result.skill_codes
                                        and evidence.context in policy.positive_contexts
                                    ),
                                    "taxonomy_version": taxonomy_version,
                                    "extractor_version": extractor_version,
                                    "policy_version": policy.version,
                                }
                            )
                    for name, records in output.items():
                        writers[name].write_table(
                            pa.Table.from_pylist(records, schema=ARTIFACT_SCHEMAS[name])
                        )
                        _digest_rows(digests[name], records)
                        artifact_rows[name] += len(records)
        finally:
            for writer in writers.values():
                writer.close()
        readback = {}
        for name, schema in ARTIFACT_SCHEMAS.items():
            digest = hashlib.sha256()
            n = 0
            with pq.ParquetFile(stage / name) as parquet:
                if parquet.schema_arrow != schema:
                    raise ValueError("Skill output schema changed")
                for batch in parquet.iter_batches(batch_size=batch_size):
                    records = batch.to_pylist()
                    _digest_rows(digest, records)
                    n += len(records)
            if n != artifact_rows[name] or digest.hexdigest() != digests[name].hexdigest():
                raise ValueError("Skill readback content or population mismatch")
            readback[name] = {"rows": n, "content_digest": digest.hexdigest()}
        processed = (
            counts["processed_match"]
            + counts["processed_no_match"]
            + (counts["expanded_partial_match"] if expanded_context or batch_name else 0)
        )
        report = {
            "status": "candidate_skills_not_semantically_accepted",
            "scope": list(scope),
            "batch": batch_name,
            "deferred_industries": sorted(set(policy_scope) - set(scope)),
            "counts": dict(counts),
            "artifacts": readback,
            "distinct_skills_with_pairs": len(skills),
            "skill_job_counts": dict(sorted(skills.items(), key=lambda kv: (-kv[1], kv[0]))),
            "coverage": {
                "processed_jobs": processed,
                "eligible_in_scope": counts["scope_eligible"],
                "fraction_in_scope": processed / counts["scope_eligible"]
                if counts["scope_eligible"]
                else None,
                "fraction_of_input": processed / counts["input_rows"]
                if counts["input_rows"]
                else None,
                "prevalence_denominator": (
                    "processed_match + processed_no_match + expanded_partial_match"
                    if expanded_context or batch_name
                    else "processed_match + processed_no_match under same filters"
                ),
            },
            "by_industry_year": [
                {"job_industry": industry, "year": year, **dict(c)}
                for (industry, year), c in sorted(coverage.items())
            ],
            "readback_passed": True,
            "semantic_validation": "pending_independent_holdout",
            "cache": {"maxsize": 8192, "hits": cached_extract.cache_info().hits},
            "limits": [
                "Pairs mean required OR preferred mentions, not all mandatory skills",
                "Finite vocabulary and configured industry labels only; "
                "no-match is not absence of skill",
                "Foreign languages may be inferred from mapped certificates; "
                "evidence distinguishes it",
                (
                    "Unresolved individual claims retained; clear pairs may still be included"
                    if expanded_context or batch_name
                    else "Unresolved documents withheld from positive pairs "
                    "and processed denominator"
                ),
                "No PostgreSQL publish, Gold model or dashboard; "
                "candidate output requires validation",
            ],
        }
        (stage / "skill_quality_report.json").write_text(json_text(report))
        snapshot = stage / "taxonomy_snapshot"
        snapshot.mkdir()
        for path in taxonomy_dir.iterdir():
            if path.suffix in {".json", ".csv"}:
                shutil.copyfile(path, snapshot / path.name)
        source.check_unchanged()
        if any(file_sha256(p) != sha for p, sha in asset_hashes.items()):
            raise ValueError("Skill code or taxonomy changed during processing")
        manifest = {
            "status": report["status"],
            "created_at": datetime.now(UTC).isoformat(),
            "source": source.manifest["source"],
            "input_rows": source.rows,
            "extractor_version": extractor_version,
            "taxonomy_version": taxonomy_version,
            "policy": policy_document,
            "processed_scope": list(scope),
            "batch": batch_name,
            "input_hashes": {str(p.resolve()): h for p, h in source.hashes.items()},
            "asset_hashes": {str(p.resolve()): sha for p, sha in asset_hashes.items()},
            "readback": readback,
            "artifacts": {
                str(p.relative_to(stage)): {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in stage.rglob("*")
                if p.is_file()
            },
        }
        (stage / "manifest.json").write_text(json_text(manifest))
        if destination.exists():
            raise ValueError("Output appeared during skill processing")
        os.rename(stage, destination)
    return report
