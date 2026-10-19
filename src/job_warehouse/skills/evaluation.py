"""Validate complete references and score pairs without hiding no-matches or abstentions."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.matcher import SkillMatcher
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.taxonomy import Taxonomy

CONTEXTS = {"required", "preferred", "negated", "mentioned", "ambiguous"}


def read_reference(
    path: Path, samples_path: Path, taxonomy: Taxonomy, *, taxonomy_sha256: str
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    samples = json.loads(samples_path.read_text())
    by_hash = {r["requirements_text_hash"]: r for r in samples}
    if len(by_hash) != len(samples) or any(
        text_hash(r["requirements"]) != h for h, r in by_hash.items()
    ):
        raise ValueError("Duplicate or changed sample text")
    document: dict[str, Any] = json.loads(path.read_text())
    if document.get("input_sha256") != file_sha256(samples_path):
        raise ValueError("Reference input SHA mismatch")
    if document.get("taxonomy_sha256") != taxonomy_sha256:
        raise ValueError("Reference taxonomy SHA mismatch")
    labels: dict[str, dict[str, Any]] = {}
    for record in document["records"]:
        hashed = record["requirements_text_hash"]
        if hashed not in by_hash or hashed in labels:
            raise ValueError("Missing or duplicate reference sample")
        if record["example_id"] != by_hash[hashed]["example_id"]:
            raise ValueError("Reference job ID mismatch")
        for claim in record["claims"]:
            if claim["skill_code"] not in taxonomy.skills or claim["context"] not in CONTEXTS:
                raise ValueError("Reference uses an unknown skill or context")
            if not claim["evidence"] or claim["evidence"] not in by_hash[hashed]["requirements"]:
                raise ValueError("Reference evidence is not an exact source substring")
        labels[hashed] = record
    if set(labels) != set(by_hash):
        raise ValueError("Reference must label every sample, including no-match texts")
    return document, labels


def positive_codes(record: dict[str, Any], contexts: tuple[str, ...]) -> set[str]:
    return {c["skill_code"] for c in record["claims"] if c["context"] in contexts}


def pair_metrics(tp: int, fp: int, fn: int) -> dict[str, Any]:
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def score_reference(
    samples: list[dict[str, Any]], labels: dict[str, dict[str, Any]], matcher: SkillMatcher
) -> dict[str, Any]:
    counters: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    differences = []
    for sample in samples:
        hashed = sample["requirements_text_hash"]
        expected = positive_codes(labels[hashed], matcher.policy.positive_contexts)
        extraction = matcher.extract(sample["requirements"])
        actual = set(extraction.skill_codes)
        increment = [
            len(expected & actual),
            len(actual - expected),
            len(expected - actual),
            1,
            int(extraction.status == "needs_review"),
        ]
        for key in ["all", sample["sampling_industry"]]:
            counters[key] = [a + b for a, b in zip(counters[key], increment, strict=True)]
        if actual != expected:
            differences.append(
                {
                    "requirements_text_hash": hashed,
                    "example_id": sample["example_id"],
                    "job_industry": sample["sampling_industry"],
                    "status": extraction.status,
                    "false_positive": sorted(actual - expected),
                    "false_negative": sorted(expected - actual),
                }
            )
    return {
        "by_industry": {
            key: {**pair_metrics(*v[:3]), "texts": v[3], "abstained_texts": v[4]}
            for key, v in sorted(counters.items())
        },
        "differences": differences,
        "limits": [
            "Recall is within the frozen vocabulary; not every labor-market skill",
            "Abstentions keep reference positives as FN; not silently dropped",
            "AI reference is not human-confirmed ground truth",
            "Tune scores cannot qualify an independent holdout gate",
        ],
    }


def reviewer_disagreements(
    first: dict[str, dict[str, Any]], second: dict[str, dict[str, Any]], contexts: tuple[str, ...]
) -> list[dict[str, Any]]:
    if set(first) != set(second):
        raise ValueError("Reviewer populations differ")
    disagreements = []
    for hashed in first:
        a, b = positive_codes(first[hashed], contexts), positive_codes(second[hashed], contexts)
        if a != b:
            disagreements.append(
                {
                    "requirements_text_hash": hashed,
                    "example_id": first[hashed]["example_id"],
                    "first_only": sorted(a - b),
                    "second_only": sorted(b - a),
                }
            )
    return disagreements
