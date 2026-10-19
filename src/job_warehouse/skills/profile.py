"""Requirements profile and deterministic, text-disjoint annotation samples."""

import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.input import (
    PLACEHOLDERS,
    SCOPE,
    json_text,
    require_new_destination,
    staging_directory,
    verify_jobs_run,
)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prepare_skills(
    jobs_run: Path,
    output_dir: Path,
    *,
    tune_per_industry: int = 30,
    holdout_per_industry: int = 100,
    batch_size: int = 2048,
    allow_unpinned_fixture: bool = False,
) -> dict[str, Any]:
    if tune_per_industry < 1 or holdout_per_industry < 1:
        raise ValueError("Sample sizes must be positive")
    destination = require_new_destination(output_dir)
    source = verify_jobs_run(jobs_run, allow_unpinned_fixture=allow_unpinned_fixture)
    counts: Counter[str] = Counter()
    by_industry: dict[str, Counter[str]] = defaultdict(Counter)
    by_year: Counter[tuple[str, int]] = Counter()
    groups: dict[str, dict[str, Any]] = {}
    for batch in source.batches(batch_size):
        for row in batch:
            industry, text = row["job_industry"], row["requirements"]
            counts["input_rows"] += 1
            if industry not in SCOPE:
                counts["outside_scope"] += 1
                continue
            counts["scope_rows"] += 1
            by_industry[industry]["rows"] += 1
            by_year[(industry, row["year"])] += 1
            if text is None or text.strip().casefold() in PLACEHOLDERS:
                state = "missing" if text is None else "unusable"
                counts[state] += 1
                by_industry[industry][state] += 1
                continue
            counts["usable"] += 1
            by_industry[industry]["usable"] += 1
            digest = text_hash(text)
            if digest not in groups:
                groups[digest] = {
                    "requirements_text_hash": digest,
                    "requirements": text,
                    "example_id": row["id"],
                    "rows": 0,
                    "industries": set(),
                    "years": set(),
                }
            group = groups[digest]
            group["rows"] += 1
            group["industries"].add(industry)
            group["years"].add(row["year"])
    # Global text hashes, including cross-industry duplicates, belong to one split.
    # Round-robin over source years gives each year a chance without consulting matches.
    chosen: set[str] = set()
    samples: dict[str, list[dict[str, Any]]] = {"tune": [], "holdout": []}
    for split, target in [("tune", tune_per_industry), ("holdout", holdout_per_industry)]:
        for industry in SCOPE:
            selected: list[str] = []
            buckets = {
                year: iter(
                    sorted(
                        (
                            h
                            for h, g in groups.items()
                            if industry in g["industries"] and year in g["years"]
                        ),
                        key=lambda h: text_hash(f"skills-sample-v1:{split}:{h}"),
                    )
                )
                for year in range(2022, 2027)
            }
            while len(selected) < target:
                before = len(selected)
                for year, bucket in buckets.items():
                    for digest in bucket:
                        if digest not in chosen:
                            chosen.add(digest)
                            selected.append(digest)
                            group = groups[digest]
                            samples[split].append(
                                {
                                    **group,
                                    "industries": sorted(group["industries"]),
                                    "years": sorted(group["years"]),
                                    "sampling_industry": industry,
                                    "sampling_year": year,
                                }
                            )
                            break
                    if len(selected) == target:
                        break
                if len(selected) == before:
                    break
            by_industry[industry][f"{split}_texts"] = len(selected)
    report = {
        "status": "profile_and_unlabelled_samples_only",
        "counts": dict(counts),
        "distinct_usable_texts_in_scope": len(groups),
        "by_industry": {label: dict(c) for label, c in sorted(by_industry.items())},
        "by_industry_year": [
            {"job_industry": label, "year": year, "rows": n}
            for (label, year), n in sorted(by_year.items())
        ],
        "sampling": {
            "version": "skills-sample-v1",
            "group_key": "exact requirements SHA256 across all three industries",
            "design": "deterministic equal-year stratification, unique texts, not job weighting",
            "tune_texts": len(samples["tune"]),
            "holdout_texts": len(samples["holdout"]),
            "limitations": [
                "Not a simple random sample of job rows; report per industry/year "
                "and text coverage",
                "No predictions, annotation or skill-quality measurement at preparation time",
            ],
        },
    }
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        for split, records in samples.items():
            (stage / f"{split}_unlabelled.json").write_text(json_text(records))
        (stage / "requirements_profile.json").write_text(json_text(report))
        source.check_unchanged()
        manifest = {
            "status": report["status"],
            "source": source.manifest["source"],
            "input_hashes": {str(p.resolve()): h for p, h in source.hashes.items()},
            "scope": list(SCOPE),
            "sampling": report["sampling"],
            "artifacts": {
                p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in stage.iterdir()
            },
        }
        (stage / "manifest.json").write_text(json_text(manifest))
        if destination.exists():
            raise ValueError("Output appeared during skill preparation")
        os.rename(stage, destination)
    return report
