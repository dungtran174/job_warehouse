"""Explicit expansion scopes and text-disjoint samples; preserve the pilot defaults."""

import json
import os
import unicodedata
from collections import Counter
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
from job_warehouse.skills.profile import text_hash

BATCH_SCOPES = {
    "engineering_production": (
        "Điện - Điện tử - Điện lạnh / Vận hành - Bảo trì - Bảo dưỡng",
        "Cơ khí - Ô tô - Tự động hóa / Sản xuất - Lắp ráp - Chế biến",
        "Khoa học - Kỹ thuật",
        "Kỹ thuật",
        "Quản lý tiêu chuẩn và chất lượng",
    ),
    "logistics_transport": (
        "Xuất Nhập Khẩu / Thu mua - Kho Vận - Chuỗi cung ứng",
        "Vận Tải - Lái xe - Giao nhận",
    ),
    "hr_finance_legal": (
        "Nhân sự / Hành chính - Thư ký",
        "Ngân hàng / Tài chính - Đầu tư - Chứng Khoán",
        "Luật - Pháp Lý - Tuân thủ",
    ),
    "real_estate": ("Bất động sản",),
    "sales_customer_service": (
        "Bán hàng - Kinh doanh",
        "Chăm sóc khách hàng",
        "Nhân viên kinh doanh",
        "Phát triển thị trường",
        "Bất động sản",
    ),
}


def batch_scope(name: str) -> tuple[str, ...]:
    if name not in BATCH_SCOPES:
        raise ValueError(f"Unknown skills batch: {name}")
    return BATCH_SCOPES[name]


def normalized_text_hash(text: str) -> str:
    """Grouping only; never change source text or evidence offsets."""
    return text_hash(" ".join(unicodedata.normalize("NFC", text).casefold().split()))


def prepare_batch(
    jobs_run: Path,
    output_dir: Path,
    *,
    batch_name: str,
    tune_per_industry: int = 20,
    holdout_per_industry: int = 50,
    allow_unpinned_fixture: bool = False,
    exclude_samples: tuple[Path, ...] = (),
    exclude_job_ids: tuple[int, ...] = (),
    exclude_industries: tuple[str, ...] = (),
    sample_seed: str = "batch-sample-v1",
) -> dict[str, Any]:
    scope = batch_scope(batch_name)
    if set(scope) & set(exclude_industries):
        raise ValueError("Cannot exclude a target industry from its own samples")
    if tune_per_industry < 1 or holdout_per_industry < 1:
        raise ValueError("Sample sizes must be positive")
    destination = require_new_destination(output_dir)
    source = verify_jobs_run(jobs_run, allow_unpinned_fixture=allow_unpinned_fixture)
    groups: dict[str, dict[str, Any]] = {}
    excluded: set[str] = set()
    exclusion_hashes = {}
    excluded_ids = set(exclude_job_ids)
    for path in exclude_samples:
        exclusion_hashes[str(path.resolve())] = file_sha256(path)
        records = json.loads(path.read_text())
        for record in records:
            excluded.add(normalized_text_hash(record["requirements"]))
    counts: dict[str, Counter[str]] = {label: Counter() for label in scope}
    for batch in source.batches():
        for row in batch:
            industry, text = row["job_industry"], row["requirements"]
            usable = text is not None and text.strip().casefold() not in PLACEHOLDERS
            if industry in (*SCOPE, *exclude_industries) and usable:
                # Superset of all prior pilot tune/review texts, including
                # cross-industry copies. No need to read predictions to exclude them.
                excluded.add(normalized_text_hash(text))
            if row["id"] in excluded_ids and usable:
                excluded.add(normalized_text_hash(text))
            if industry not in scope:
                continue
            counts[industry]["rows"] += 1
            if not usable:
                counts[industry]["missing" if text is None else "unusable"] += 1
                continue
            counts[industry]["usable"] += 1
            group_hash = normalized_text_hash(text)
            if group_hash not in groups:
                groups[group_hash] = {
                    "normalized_text_hash": group_hash,
                    "requirements_text_hash": text_hash(text),
                    "requirements": text,
                    "example_id": row["id"],
                    "industries": set(),
                    "years": set(),
                }
            groups[group_hash]["industries"].add(industry)
            groups[group_hash]["years"].add(row["year"])
    chosen = set(excluded)
    samples: dict[str, list[dict[str, Any]]] = {"tune": [], "holdout": []}
    for split, size in (("tune", tune_per_industry), ("holdout", holdout_per_industry)):
        for industry in scope:
            buckets = {
                year: iter(
                    sorted(
                        (
                            h
                            for h, g in groups.items()
                            if industry in g["industries"] and year in g["years"]
                        ),
                        key=lambda h: text_hash(f"{sample_seed}:{batch_name}:{split}:{h}"),
                    )
                )
                for year in range(2022, 2027)
            }
            selected = 0
            while selected < size:
                previous = selected
                for year, bucket in buckets.items():
                    for hashed in bucket:
                        if hashed in chosen:
                            continue
                        chosen.add(hashed)
                        group = groups[hashed]
                        samples[split].append(
                            {
                                **group,
                                "industries": sorted(group["industries"]),
                                "years": sorted(group["years"]),
                                "sampling_industry": industry,
                                "sampling_year": year,
                            }
                        )
                        selected += 1
                        break
                    if selected == size:
                        break
                if selected == previous:
                    break
            if selected != size:
                raise ValueError(f"Insufficient disjoint {split} texts for {industry}")
    report = {
        "status": "unlabelled_batch_samples",
        "batch": batch_name,
        "scope": list(scope),
        "by_industry": {k: dict(v) for k, v in counts.items()},
        "excluded_pilot_normalized_groups": len(excluded),
        "excluded_batch_groups": len(set(groups) & excluded),
        "sampling": {
            "version": sample_seed,
            "exclusion_inputs": exclusion_hashes,
            "excluded_development_job_ids": sorted(excluded_ids),
            "excluded_prior_industries": list(exclude_industries),
            "tune_texts": len(samples["tune"]),
            "holdout_texts": len(samples["holdout"]),
            "normalization": "NFC, casefold, whitespace collapse; grouping only",
            "design": "unique normalized texts, round-robin years, deterministic hash order",
            "limits": "Not job-weighted or an exhaustive near-duplicate filter",
        },
    }
    with staging_directory(destination) as tmp:
        stage = Path(tmp)
        for split, rows in samples.items():
            (stage / f"{split}_unlabelled.json").write_text(json_text(rows))
        (stage / "requirements_profile.json").write_text(json_text(report))
        source.check_unchanged()
        if any(file_sha256(Path(p)) != sha for p, sha in exclusion_hashes.items()):
            raise ValueError("Exclusion sample changed during preparation")
        (stage / "manifest.json").write_text(
            json_text(
                {
                    **report,
                    "source": source.manifest["source"],
                    "input_hashes": {str(p.resolve()): h for p, h in source.hashes.items()},
                    "code_sha256": file_sha256(Path(__file__)),
                    "artifacts": {p.name: {"sha256": file_sha256(p)} for p in stage.iterdir()},
                }
            )
        )
        if destination.exists():
            raise ValueError("Output appeared during sample preparation")
        os.rename(stage, destination)
    return report
