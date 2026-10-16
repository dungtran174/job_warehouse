"""Join verified S2/S3 identities, normalize salary, publish immutable local artifacts."""

import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.contract import EXPECTED_SHA256, REVISION
from job_warehouse.history.identity import file_sha256, record_key
from job_warehouse.silver.salary import POLICY_VERSION, SALARY_VERSION
from job_warehouse.silver.salary.parser import convert_salary, parse_salary
from job_warehouse.silver.salary.policy import apply_override, load_rates, owner_overrides

CORE_COLUMNS = [
    "id",
    "record_key",
    "source_row_index",
    "source_content_hash",
    "salary",
    "benefits",
    "year",
    "job_title_clean",
    "company_name_clean",
    "job_type_label_clean",
    "education_label_clean",
    "position_label_clean",
    "requirements_clean",
    "experience_min_years",
    "experience_max_years",
]
JOBS_SCHEMA = pa.schema(
    [
        ("id", pa.int64()),
        ("job_title", pa.string()),
        ("company_name", pa.string()),
        ("salary_min", pa.decimal128(18, 2)),
        ("salary_max", pa.decimal128(18, 2)),
        ("location", pa.list_(pa.string())),
        ("job_type", pa.string()),
        ("job_industry", pa.string()),
        ("experience_min_years", pa.decimal128(18, 6)),
        ("experience_max_years", pa.decimal128(18, 6)),
        ("education_level", pa.string()),
        ("job_position", pa.string()),
        ("requirements", pa.string()),
        ("year", pa.int16()),
    ]
)
AUDIT_SCHEMA = pa.schema(
    [
        ("id", pa.int64()),
        ("record_key", pa.string()),
        ("salary", pa.string()),
        ("year", pa.int16()),
        ("salary_min", pa.decimal128(18, 2)),
        ("salary_max", pa.decimal128(18, 2)),
        ("status", pa.string()),
        ("kind", pa.string()),
        # Preserve unrepresentable source amounts as text for review.
        ("source_min", pa.string()),
        ("source_max", pa.string()),
        ("currency", pa.string()),
        ("period", pa.string()),
        ("min_inclusive", pa.bool_()),
        ("max_inclusive", pa.bool_()),
        ("flags", pa.list_(pa.string())),
        ("reason", pa.string()),
        ("component", pa.string()),
        ("fx_rate", pa.string()),
        ("fx_reference", pa.string()),
        ("rounding_quantum", pa.string()),
        ("evidence_column", pa.string()),
        ("evidence_sha256", pa.string()),
        ("salary_numeric_eligible", pa.bool_()),
        ("salary_midpoint_eligible", pa.bool_()),
        ("analysis_selected", pa.bool_()),
    ]
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _verify(parquet: Path, manifest: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(manifest.read_text())
    if file_sha256(parquet) != data["artifacts"][parquet.name]["sha256"]:
        raise ValueError(f"Input SHA mismatch: {parquet.name}")
    return data


def run_salary(
    core_run: Path,
    industry_run: Path,
    output_dir: Path,
    *,
    fx_rates: Path | None = None,
    batch_size: int = 2048,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    destination = output_dir.resolve()
    if destination.exists():
        raise ValueError("Choose a new output directory")
    if any((p / "src/job_warehouse").is_dir() for p in (destination, *destination.parents)):
        raise ValueError("Salary output must be outside the repository")
    core_path, industry_path = core_run / "core.parquet", industry_run / "enrichment.parquet"
    core_manifest, industry_manifest = core_run / "manifest.json", industry_run / "manifest.json"
    inputs = [core_path, industry_path, core_manifest, industry_manifest]
    if fx_rates is not None:
        inputs.append(fx_rates)
        fx_document = json.loads(fx_rates.read_text())
        if "source_pdf" in fx_document:
            inputs.append(Path(fx_document["source_pdf"]))
    hashes = {p: file_sha256(p) for p in inputs}
    cm, im = _verify(core_path, core_manifest), _verify(industry_path, industry_manifest)
    if not allow_unpinned_fixture and (
        cm["input"]["sha256"] != EXPECTED_SHA256
        or not cm["source"]["pinned_artifact_verified"]
        or im["source"]["revision"] != REVISION
        or not im["source"]["pinned_artifact_verified"]
    ):
        raise ValueError("Unpinned S2/S3 input")
    rate_map, rate_document = load_rates(fx_rates)
    assets = list(Path(__file__).parent.glob("*.py")) + [
        Path(__file__).with_name("owner_overrides.csv")
    ]
    asset_hashes = {p: file_sha256(p) for p in assets}
    columns = [
        "record_key",
        "source_dataset_id",
        "source_row_index",
        "source_content_hash",
        "year_value",
        "job_industry",
        "location",
        "industry_scope_500",
    ]
    enrichment: dict[str, dict[str, Any]] = {}
    for row in pq.read_table(industry_path, columns=columns).to_pylist():
        key = row["record_key"]
        if key in enrichment:
            raise ValueError("Duplicate S3 key")
        enrichment[key] = row
    if len(enrichment) != im["partition"]["enrichment"]:
        raise ValueError("S3 population mismatch")
    selected_expected = sum(r["industry_scope_500"] for r in enrichment.values())
    if selected_expected != im["partition"]["analysis"]:
        raise ValueError("S3 selection mismatch; expected threshold 500")
    counters: Counter[str] = Counter()
    by_year: Counter[tuple[int, str]] = Counter()
    by_industry: Counter[tuple[str, str]] = Counter()
    coverage: dict[tuple[str, int], Counter[str]] = {}
    mappings: Counter[tuple[Any, ...]] = Counter()
    examples: dict[tuple[Any, ...], int] = {}
    seen: set[str] = set()
    source_ids: set[int] = set()
    parsed_cache: dict[tuple[str | None, int, int | None], dict[str, Any]] = {}
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".salary-", dir=destination.parent) as tmp:
        stage = Path(tmp)
        with (
            pq.ParquetWriter(
                stage / "salary_enrichment.parquet", AUDIT_SCHEMA, compression="zstd"
            ) as audit,
            pq.ParquetWriter(stage / "jobs.parquet", JOBS_SCHEMA, compression="zstd") as jobs,
            pq.ParquetWriter(
                stage / "jobs_analysis.parquet", JOBS_SCHEMA, compression="zstd"
            ) as chosen,
            pq.ParquetFile(core_path) as source,
        ):
            for batch in source.iter_batches(batch_size=batch_size, columns=CORE_COLUMNS):
                job_rows, audit_rows, mask = [], [], []
                for row in batch.to_pylist():
                    key, ident = row["record_key"], row["id"]
                    if key in seen or ident in source_ids or key not in enrichment:
                        raise ValueError("Missing or duplicate core/S3 identity")
                    e = enrichment[key]
                    if (
                        e["source_dataset_id"],
                        e["source_row_index"],
                        e["source_content_hash"],
                        e["year_value"],
                    ) != (
                        ident,
                        row["source_row_index"],
                        row["source_content_hash"],
                        row["year"],
                    ) or key != record_key(cm["input"]["sha256"], row["source_row_index"]):
                        raise ValueError("S2/S3 identity or content mismatch")
                    seen.add(key)
                    source_ids.add(ident)
                    cache_key = (
                        row["salary"],
                        row["year"],
                        ident if ident in owner_overrides() else None,
                    )
                    if cache_key not in parsed_cache:
                        parsed = apply_override(
                            ident, row["salary"], benefits=row["benefits"]
                        ) or parse_salary(row["salary"])
                        converted = convert_salary(parsed, rate_map.get(row["year"]))
                        parsed_cache[cache_key] = {
                            **asdict(converted),
                            "salary_numeric_eligible": converted.numeric_eligible,
                            "salary_midpoint_eligible": converted.midpoint_eligible,
                        }
                    result = parsed_cache[cache_key]
                    selected = bool(e["industry_scope_500"])
                    entry = {
                        "id": ident,
                        "record_key": key,
                        "salary": row["salary"],
                        "year": row["year"],
                        **result,
                        "analysis_selected": selected,
                    }
                    for field in ("source_min", "source_max", "fx_rate"):
                        entry[field] = str(entry[field]) if entry[field] is not None else None
                    audit_rows.append(entry)
                    if not isinstance(e["location"], str) or not e["location"].strip():
                        raise ValueError("S3 location missing")
                    job_rows.append(
                        {
                            "id": ident,
                            "job_title": row["job_title_clean"],
                            "company_name": row["company_name_clean"],
                            "salary_min": result["salary_min"],
                            "salary_max": result["salary_max"],
                            "location": list(dict.fromkeys(e["location"].split("; "))),
                            "job_type": row["job_type_label_clean"],
                            "job_industry": e["job_industry"],
                            "experience_min_years": row["experience_min_years"],
                            "experience_max_years": row["experience_max_years"],
                            "education_level": row["education_label_clean"],
                            "job_position": row["position_label_clean"],
                            "requirements": row["requirements_clean"],
                            "year": row["year"],
                        }
                    )
                    mask.append(selected)
                    status = result["status"]
                    counters[status] += 1
                    counters["analysis_rows"] += selected
                    has_bound = any(result[n] is not None for n in ("salary_min", "salary_max"))
                    counters["with_vnd_month_bounds"] += has_bound
                    counters["analysis_with_vnd_month_bounds"] += selected and has_bound
                    by_year[(row["year"], status)] += 1
                    by_industry[(e["job_industry"], status)] += 1
                    eligibility = coverage.setdefault((e["job_industry"], row["year"]), Counter())
                    eligibility["records"] += 1
                    eligibility["numeric_eligible"] += result["salary_numeric_eligible"]
                    eligibility["midpoint_eligible"] += result["salary_midpoint_eligible"]
                    eligibility["analysis_records"] += selected
                    eligibility["analysis_numeric_eligible"] += (
                        selected and result["salary_numeric_eligible"]
                    )
                    eligibility["analysis_midpoint_eligible"] += (
                        selected and result["salary_midpoint_eligible"]
                    )
                    mkey = (
                        row["salary"],
                        row["year"],
                        status,
                        result["kind"],
                        str(result["salary_min"]),
                        str(result["salary_max"]),
                        result["reason"],
                        ";".join(result["flags"]),
                        selected,
                    )
                    mappings[mkey] += 1
                    examples.setdefault(mkey, ident)
                    digest.update((_json(entry) + "\n").encode())
                audit.write_table(pa.Table.from_pylist(audit_rows, schema=AUDIT_SCHEMA))
                table = pa.Table.from_pylist(job_rows, schema=JOBS_SCHEMA)
                jobs.write_table(table)
                chosen.write_table(table.filter(pa.array(mask, type=pa.bool_())))
        if seen != set(enrichment) or len(seen) != cm["partition"]["core"]:
            raise ValueError("Core/S3 population mismatch")
        if counters["analysis_rows"] != selected_expected:
            raise ValueError("Analysis population mismatch")
        # Read all published values back, including Decimal and list serialization.
        audit_back = pq.ParquetFile(stage / "salary_enrichment.parquet")
        jobs_back = pq.ParquetFile(stage / "jobs.parquet")
        subset_back = pq.ParquetFile(stage / "jobs_analysis.parquet")
        read_digest = hashlib.sha256()
        for index in range(audit_back.num_row_groups):
            a = audit_back.read_row_group(index)
            j = jobs_back.read_row_group(index)
            for audit_row in a.to_pylist():
                # JSON tuples/lists have the same representation.
                read_digest.update((_json(audit_row) + "\n").encode())
            for field in ("id", "salary_min", "salary_max"):
                if not a[field].equals(j[field]):
                    raise ValueError("Salary/jobs readback mismatch")
            if not j.filter(a["analysis_selected"]).equals(subset_back.read_row_group(index)):
                raise ValueError("Selected jobs readback mismatch")
        if digest.hexdigest() != read_digest.hexdigest():
            raise ValueError("Salary serialization digest mismatch")
        with (
            (stage / "salary_mapping.csv").open("w", encoding="utf-8", newline="") as all_stream,
            (stage / "salary_review.csv").open("w", encoding="utf-8", newline="") as review_stream,
        ):
            header = [
                "salary",
                "year",
                "status",
                "kind",
                "salary_min",
                "salary_max",
                "reason",
                "flags",
                "analysis_selected",
                "rows",
                "example_id",
            ]
            writers = [csv.writer(all_stream), csv.writer(review_stream)]
            for writer in writers:
                writer.writerow(header)
            for key, n in sorted(mappings.items(), key=lambda item: (-item[1], str(item[0]))):
                values = [*key, n, examples[key]]
                writers[0].writerow(values)
                if (
                    key[2] in {"needs_review", "fx_missing", "owner_unresolved"}
                    or "signal" in key[7]
                ):
                    writers[1].writerow(values)
        report = {
            "core_rows": len(seen),
            "analysis_rows": selected_expected,
            "counts": dict(counters),
            "by_year": [
                {"year": y, "status": s, "rows": n} for (y, s), n in sorted(by_year.items())
            ],
            "by_industry": [
                {"job_industry": y, "status": s, "rows": n}
                for (y, s), n in sorted(by_industry.items())
            ],
            "comparison_coverage_by_industry_year": [
                {"job_industry": industry, "year": year, **dict(counts)}
                for (industry, year), counts in sorted(coverage.items())
            ],
            "readback_passed": True,
            "semantic_validation": "pending_independent_review",
        }
        (stage / "salary_quality_report.json").write_text(_json(report) + "\n")
        (stage / "fx_rates.json").write_text(_json(rate_document) + "\n")
        (stage / "owner_overrides.csv").write_bytes(
            Path(__file__).with_name("owner_overrides.csv").read_bytes()
        )
        if any(file_sha256(p) != h for p, h in {**hashes, **asset_hashes}.items()):
            raise ValueError("Salary inputs or code changed during processing")
        manifest = {
            "status": "salary_normalized_not_db_published",
            "created_at": datetime.now(UTC).isoformat(),
            "salary_version": SALARY_VERSION,
            "policy_version": POLICY_VERSION,
            "source": cm["source"],
            "partition": {"core": len(seen), "analysis": selected_expected},
            "input_hashes": {str(p.resolve()): h for p, h in hashes.items()},
            "asset_hashes": {p.name: h for p, h in asset_hashes.items()},
            "content_digest": digest.hexdigest(),
            "summary": report,
            "fx_complete": counters["fx_missing"] == 0,
            "limits": [
                "No database publish; independent semantic validation pending",
                "Conventional monthly equivalents; actual schedules unknown",
                "Review signals retain source numbers; inspect before BI aggregation",
            ],
            "artifacts": {
                p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in stage.iterdir()
            },
        }
        (stage / "manifest.json").write_text(_json(manifest) + "\n")
        if destination.exists():
            raise ValueError("Output appeared during salary processing")
        os.rename(stage, destination)
    return manifest
