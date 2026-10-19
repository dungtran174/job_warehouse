"""Reviewed claims cannot overwrite source text, lose claims or alter other jobs."""

import csv
import json

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.history.identity import file_sha256  # noqa: E402
from job_warehouse.skills.input import SCOPE  # noqa: E402
from job_warehouse.skills.profile import text_hash  # noqa: E402
from job_warehouse.skills.review_import import apply_review, evidence_start, read_csv  # noqa: E402
from job_warehouse.skills.runner import run_skills  # noqa: E402


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def seal(bundle, baseline):
    (bundle / "bundle.json").write_text(
        json.dumps(
            {
                "baseline_manifest_sha256": file_sha256(baseline / "manifest.json"),
                "taxonomy_version": "fixture-reviewed",
                "policy_version": "fixture-policy",
                "files": {
                    p.name: file_sha256(p) for p in bundle.iterdir() if p.name != "bundle.json"
                },
            }
        )
    )


@pytest.fixture
def review_input(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    text = "Biết Python. Office"
    rows = [
        {"id": i, "job_industry": SCOPE[0], "year": 2026, "requirements": req}
        for i, req in enumerate([text, "unmapped synthetic text", "Biết Java"], 1)
    ]
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("job_industry", pa.string()),
            ("year", pa.int16()),
            ("requirements", pa.string()),
        ]
    )
    path = jobs / "jobs_analysis.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    (jobs / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture"},
                "partition": {"analysis": 3},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
            }
        )
    )
    baseline = tmp_path / "baseline"
    run_skills(jobs, baseline, allow_unpinned_fixture=True)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_csv(
        bundle / "source.csv",
        [
            {
                "job_id": "1",
                "job_industry": SCOPE[0],
                "year": "2026",
                "requirements": text,
                "số kỹ năng lấy": "1",
                "tên kỹ năng chuẩn được lấy": "Python",
                "số kỹ năng không lấy": "0",
                "số kỹ năng chưa rõ": "1",
            }
        ],
    )
    details = [
        {
            "job_id": "1",
            "tên kỹ năng chuẩn": name,
            "trích dẫn nguyên văn": name,
            "kết luận": decision,
            "lý do ngắn": "fixture",
        }
        for name, decision in [("Python", "lấy"), ("Office", "chưa rõ")]
    ]
    write_csv(bundle / "details.csv", details)
    claims = [
        {
            "claim_id": f"csv:{i}",
            "job_id": "1",
            "source_skill_name": r["tên kỹ năng chuẩn"],
            "source_decision": r["kết luận"],
            "source_evidence": r["trích dẫn nguyên văn"],
            "decision": "accept" if i == 2 else "unclear",
            "skill_code": "python" if i == 2 else "",
            "skill_name": r["tên kỹ năng chuẩn"],
            "evidence": r["trích dẫn nguyên văn"],
            "reason": "fixture semantic decision",
            "condition": "",
            "requirements_text_hash": text_hash(text),
        }
        for i, r in enumerate(details, 2)
    ]
    write_csv(bundle / "claims.csv", claims)
    (bundle / "catalogue.csv").write_bytes(
        (baseline / "taxonomy_snapshot/taxonomy.csv").read_bytes()
    )
    (bundle / "policy.json").write_text('{"version":"fixture-policy","method":"synthetic fixture"}')
    seal(bundle, baseline)
    return jobs, baseline, bundle


def run(review_input, output):
    return apply_review(*review_input, output, allow_unpinned_fixture=True)


def test_review_replay_preserves_other_jobs_and_partial_known_skills(review_input, tmp_path):
    jobs, baseline, bundle = review_input
    original_hashes = {
        p: file_sha256(p) for directory in review_input for p in directory.rglob("*") if p.is_file()
    }
    report = run(review_input, tmp_path / "one")
    replay = run(review_input, tmp_path / "two")
    assert report["artifacts"] == replay["artifacts"]
    assert report["added_pairs"] == 1
    assert report["total_pairs"] == 2
    assert report["status_counts"] == {
        "reviewed_partial_match": 1,
        "processed_no_match": 1,
        "processed_match": 1,
    }
    before = pq.read_table(baseline / "job_skill_status.parquet").to_pylist()
    after = pq.read_table(tmp_path / "one/job_skill_status.parquet").to_pylist()
    assert before[1:] == after[1:]
    assert after[0]["positive_skill_count"] == 1
    evidence = pq.read_table(tmp_path / "one/job_skill_evidence.parquet").to_pylist()
    old = pq.read_table(baseline / "job_skill_evidence.parquet").to_pylist()
    assert evidence[:-1] == old
    assert evidence[-1]["text"] == "Python" and evidence[-1]["positive_pair_included"]
    assert all(file_sha256(p) == sha for p, sha in original_hashes.items())
    assert (tmp_path / "one/review_bundle/details.csv").read_bytes() == (
        bundle / "details.csv"
    ).read_bytes()


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("omit", "omitted"),
        ("duplicate", "Duplicate review claim"),
        ("original", "Original claim was changed"),
        ("evidence", "Invalid adjudicated evidence"),
        ("hash", "requirements hash mismatch"),
        ("foreign", "Invalid review claim population"),
        ("canonical", "Canonical name/code mismatch"),
        ("source", "Review source differs"),
        ("soft", "out-of-scope review catalogue"),
        ("baseline_taxonomy", "Baseline taxonomy"),
        ("aggregate", "Aggregate and detailed review disagree"),
    ],
)
def test_malformed_review_does_not_publish(review_input, tmp_path, mutation, message):
    jobs, baseline, bundle = review_input
    path = bundle / "claims.csv"
    rows = read_csv(path)
    if mutation == "omit":
        rows.pop()
    if mutation == "duplicate":
        rows.append(rows[0])
    if mutation == "original":
        rows[0]["source_evidence"] = "altered source"
    if mutation == "evidence":
        rows[0]["evidence"] = "invented quote"
    if mutation == "hash":
        rows[0]["requirements_text_hash"] = "wrong"
    if mutation == "foreign":
        rows[0]["job_id"] = "9"
    if mutation == "canonical":
        rows[0]["skill_name"] = "Java"
    write_csv(path, rows)
    if mutation in {"soft", "baseline_taxonomy"}:
        path = bundle / "catalogue.csv"
        rows = read_csv(path)
        rows[0]["skill_name"] = "Teamwork (kỹ năng mềm)" if mutation == "soft" else "Altered Python"
        write_csv(path, rows)
    if mutation in {"source", "aggregate"}:
        path = bundle / "source.csv"
        rows = read_csv(path)
        rows[0]["requirements" if mutation == "source" else "số kỹ năng lấy"] = (
            "wrong" if mutation == "source" else "9"
        )
        write_csv(path, rows)
    seal(bundle, baseline)
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match=message):
        run(review_input, output)
    assert not output.exists()


def test_bundle_and_baseline_tampering_are_rejected(review_input, tmp_path):
    jobs, baseline, bundle = review_input
    with (bundle / "claims.csv").open("a") as stream:
        stream.write("tampered")
    with pytest.raises(ValueError, match="bundle SHA mismatch"):
        run(review_input, tmp_path / "failed")
    seal(bundle, baseline)
    with (baseline / "job_skill_match.parquet").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="Baseline artifact SHA mismatch"):
        run(review_input, tmp_path / "failed")


def test_duplicate_accepted_evidence_deduplicates_pair_and_keeps_claims(review_input, tmp_path):
    jobs, baseline, bundle = review_input
    rows = read_csv(bundle / "claims.csv")
    duplicate = rows[0] | {
        "claim_id": "extra:1",
        "source_skill_name": "",
        "source_evidence": "",
        "source_decision": "",
    }
    rows.append(duplicate)
    rows[1]["decision"] = "reject"
    write_csv(bundle / "claims.csv", rows)
    seal(bundle, baseline)
    report = run(review_input, tmp_path / "out")
    assert report["added_pairs"] == 1
    assert report["status_counts"]["reviewed_match"] == 1
    assert report["decisions"] == {"accept": 2, "reject": 1}


def test_fixture_bypass_not_exposed_by_cli_or_default(review_input, tmp_path):
    with pytest.raises(ValueError, match="Unpinned"):
        apply_review(*review_input, tmp_path / "out")


def test_existing_destination_is_preserved(review_input, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(ValueError, match="new output directory"):
        run(review_input, output)


def test_selected_evidence_occurrence_is_preserved_and_checked():
    text = "Tốt nghiệp Python. Biết Python"
    row = {"evidence": "Python", "evidence_start": str(text.rindex("Python"))}
    assert evidence_start(row, text) == text.rindex("Python")
    assert evidence_start({"evidence": "Python"}, text) == text.index("Python")
    with pytest.raises(ValueError, match="evidence start"):
        evidence_start(row | {"evidence_start": "0"}, text)
