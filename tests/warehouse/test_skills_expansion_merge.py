"""A uniform rerun must preserve curated decisions and disclose automatic changes."""

import csv
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.expansion_merge import merge_expansion
from job_warehouse.skills.input import SCOPE
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def freeze(run):
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["artifacts"] = {
        str(p.relative_to(run)): {"sha256": file_sha256(p)}
        for p in run.rglob("*")
        if p.is_file() and p.name not in {"manifest.json", "review_completion.json"}
    }
    (run / "manifest.json").write_text(json.dumps(manifest))


@pytest.fixture
def runs(tmp_path):
    auto, baseline, review = [tmp_path / name for name in ("auto", "baseline", "review")]
    texts = {1: "Biết Python", 2: "Không cần Python", 3: "Ưu tiên Python"}
    source = tmp_path / "jobs_analysis.parquet"
    pq.write_table(
        pa.Table.from_pylist([{"id": i, "requirements": text} for i, text in texts.items()]), source
    )
    for run in (auto, baseline, review):
        run.mkdir()
        statuses = [
            {
                "job_id": i,
                "job_industry": SCOPE[0],
                "year": 2026,
                "status": "review_no_proposal",
                "requirements_text_hash": text_hash(texts[i]),
                "positive_skill_count": 0,
                "evidence_count": 0,
                "reasons": [],
            }
            for i in (1, 2, 3)
        ]
        pairs = (
            []
            if run != auto
            else [{"job_id": i, "skill_code": "python", "skill_name": "Python"} for i in (1, 2, 3)]
        )
        for name, rows in zip(ARTIFACT_SCHEMAS, (pairs, statuses, []), strict=True):
            pq.write_table(pa.Table.from_pylist(rows, schema=ARTIFACT_SCHEMAS[name]), run / name)
        (run / "manifest.json").write_text(
            json.dumps(
                {
                    "source": {"dataset": "fixture"},
                    "input_hashes": {str(source): file_sha256(source)},
                    "extractor_version": "requirements-skills-expanded-v1",
                    "artifacts": {},
                }
            )
        )
    taxonomy = auto / "taxonomy_snapshot"
    taxonomy.mkdir()
    write_csv(taxonomy / "taxonomy.csv", [{"skill_code": "python", "skill_name": "Python"}])
    bundle = review / "review_bundle"
    bundle.mkdir()
    write_csv(
        bundle / "claims.csv",
        [
            {
                "job_id": 1,
                "skill_code": "python",
                "skill_name": "Python",
                "decision": "accept",
                "evidence": "Biết Python",
                "requirements_text_hash": text_hash(texts[1]),
            },
            {
                "job_id": 2,
                "skill_code": "python",
                "skill_name": "Python",
                "decision": "reject",
                "evidence": "Không cần Python",
                "requirements_text_hash": text_hash(texts[2]),
            },
        ],
    )
    for name in ("source.csv", "details.csv", "catalogue.csv", "policy.json"):
        (bundle / name).write_text("fixture\n")
    (bundle / "bundle.json").write_text(
        json.dumps({"files": {p.name: file_sha256(p) for p in bundle.iterdir() if p.is_file()}})
    )
    for run in (auto, baseline, review):
        freeze(run)
    (baseline / "review_completion.json").write_text(
        json.dumps({"manifest_sha256": file_sha256(baseline / "manifest.json")})
    )
    return auto, baseline, review


def test_preserve_accept_block_reject_and_account_for_remaining(runs, tmp_path):
    auto, baseline, review = runs
    report = merge_expansion(auto, baseline, [review], tmp_path / "result")
    rows = pq.read_table(tmp_path / "result/job_skill_match.parquet").to_pylist()
    assert {r["job_id"] for r in rows} == {1, 3}
    assert report["reviewed_positive_pairs_preserved"] == 1
    assert report["reviewed_negative_pairs_blocked"] == 1
    assert report["original_no_proposal_now_with_skills"] == 2
    assert report["original_no_proposal_still_no_match"] == 1
    assert json.loads((tmp_path / "result/remaining_no_proposal_ids.json").read_text()) == [2]


def test_artifact_tampering_refused(runs, tmp_path):
    auto, baseline, review = runs
    with (auto / "job_skill_match.parquet").open("ab") as stream:
        stream.write(b"bad")
    with pytest.raises(ValueError, match="SHA mismatch"):
        merge_expansion(auto, baseline, [review], tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_foreign_snapshot_refused(runs, tmp_path):
    auto, baseline, review = runs
    doc = json.loads((review / "manifest.json").read_text())
    source = next(iter(doc["input_hashes"]))
    doc["input_hashes"][source] = "different"
    (review / "manifest.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="different S4"):
        merge_expansion(auto, baseline, [review], tmp_path / "result")


def test_claim_hash_mismatch_refused(runs, tmp_path):
    auto, baseline, review = runs
    bundle = review / "review_bundle"
    path = bundle / "claims.csv"
    path.write_text(path.read_text().replace(text_hash("Biết Python"), "a" * 64))
    doc = json.loads((bundle / "bundle.json").read_text())
    doc["files"][path.name] = file_sha256(path)
    (bundle / "bundle.json").write_text(json.dumps(doc))
    freeze(review)
    with pytest.raises(ValueError, match="ID/hash/scope"):
        merge_expansion(auto, baseline, [review], tmp_path / "result")


def test_same_path_cannot_be_reused(runs, tmp_path):
    auto, baseline, review = runs
    with pytest.raises(ValueError, match="new output"):
        merge_expansion(auto, baseline, [review], baseline)


@pytest.mark.parametrize(
    ("code", "quote", "expected"),
    [
        ("tax_reporting", "Có kinh nghiệm quyết toán thuế", "review_quyet_toan_thue"),
        ("tax_reporting", "Có kinh nghiệm khai báo thuế", "review_ke_khai_thue"),
        ("tax_reporting", "Biết báo cáo thuế và quyết toán thuế", "tax_reporting"),
        ("social_media", "Có kinh nghiệm quản lý Fanpage", "review_quan_tri_fanpage"),
        ("social_media", "Quản lý Fanpage và Social Media", "social_media"),
    ],
)
def test_reviewed_specialist_policy_keeps_explicit_broad_mentions(code, quote, expected):
    from job_warehouse.skills.expansion_merge import reviewed_code_after_policy

    assert reviewed_code_after_policy(code, quote) == expected
