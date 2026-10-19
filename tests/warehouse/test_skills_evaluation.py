"""Pair metrics must include no-match samples and missing positives on abstention."""

import json

import pytest

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.evaluation import (
    pair_metrics,
    read_reference,
    reviewer_disagreements,
    score_reference,
)
from job_warehouse.skills.matcher import SkillMatcher
from job_warehouse.skills.models import SkillPolicy
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.taxonomy import load_taxonomy


def test_absent_positives_on_review_are_false_negatives():
    texts = ["Biết Python", "Biết Excel; không yêu cầu Excel", "Synthetic no skill"]
    samples = [
        {
            "requirements_text_hash": text_hash(t),
            "requirements": t,
            "sampling_industry": "Synthetic",
            "example_id": i,
        }
        for i, t in enumerate(texts)
    ]
    labels = {
        text_hash(t): {"claims": [{"skill_code": c, "context": "required"} for c in codes]}
        for t, codes in zip(texts, [("python",), ("excel",), ()], strict=True)
    }
    matcher = SkillMatcher(load_taxonomy(), SkillPolicy("test", ("required", "preferred")))
    score = score_reference(samples, labels, matcher)["by_industry"]["all"]
    assert score == {**pair_metrics(1, 0, 1), "texts": 3, "abstained_texts": 1}
    assert score["recall"] == 0.5
    assert pair_metrics(0, 0, 0)["precision"] is None
    assert pair_metrics(0, 0, 0)["recall"] is None


def test_reference_requires_all_samples_and_exact_evidence(tmp_path):
    samples = [
        {
            "requirements": "Biết Python",
            "requirements_text_hash": text_hash("Biết Python"),
            "example_id": 1,
        },
        {
            "requirements": "Nothing mapped",
            "requirements_text_hash": text_hash("Nothing mapped"),
            "example_id": 2,
        },
    ]
    source = tmp_path / "samples.json"
    source.write_text(json.dumps(samples))
    document = {
        "input_sha256": file_sha256(source),
        "taxonomy_sha256": "frozen",
        "records": [
            {
                "requirements_text_hash": samples[0]["requirements_text_hash"],
                "example_id": 1,
                "claims": [{"skill_code": "python", "context": "required", "evidence": "Python"}],
            },
        ],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="every sample"):
        read_reference(path, source, load_taxonomy(), taxonomy_sha256="frozen")
    document["records"].append(
        {
            "requirements_text_hash": samples[1]["requirements_text_hash"],
            "example_id": 2,
            "claims": [],
        }
    )
    path.write_text(json.dumps(document))
    _, labels = read_reference(path, source, load_taxonomy(), taxonomy_sha256="frozen")
    assert len(labels) == 2
    document["records"][0]["claims"][0]["evidence"] = "Imagined evidence"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="exact source substring"):
        read_reference(path, source, load_taxonomy(), taxonomy_sha256="frozen")


def test_disagreement_is_reported_not_silently_dropped():
    a = {"h": {"example_id": 1, "claims": [{"skill_code": "python", "context": "required"}]}}
    b = {"h": {"example_id": 1, "claims": []}}
    assert reviewer_disagreements(a, b, ("required", "preferred")) == [
        {
            "requirements_text_hash": "h",
            "example_id": 1,
            "first_only": ["python"],
            "second_only": [],
        }
    ]
