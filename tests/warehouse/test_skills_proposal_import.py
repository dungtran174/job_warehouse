"""Positive-only external review does not turn unmentioned jobs into no-skill facts."""

import csv
import json

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.history.identity import file_sha256  # noqa: E402
from job_warehouse.skills.input import SCOPE  # noqa: E402
from job_warehouse.skills.profile import text_hash  # noqa: E402
from job_warehouse.skills.review_import import apply_review, read_csv  # noqa: E402
from job_warehouse.skills.runner import run_skills  # noqa: E402


def write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def seal(bundle, baseline):
    (bundle / "bundle.json").write_text(
        json.dumps(
            {
                "kind": "no_match_proposals",
                "baseline_manifest_sha256": file_sha256(baseline / "manifest.json"),
                "taxonomy_version": "fixture-proposal-catalogue",
                "policy_version": "fixture-policy",
                "files": {
                    p.name: file_sha256(p) for p in bundle.iterdir() if p.name != "bundle.json"
                },
            }
        )
    )


@pytest.fixture
def proposal_input(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    texts = ["Biết Python", "Biết UML", "Office", "Biết BPMN"]
    rows = [
        {"id": i, "job_industry": SCOPE[0], "year": 2026, "requirements": req}
        for i, req in enumerate(texts, 1)
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
                "partition": {"analysis": 4},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
            }
        )
    )
    baseline = tmp_path / "baseline"
    run_skills(jobs, baseline, allow_unpinned_fixture=True)
    previous = baseline / "review_bundle"
    previous.mkdir()
    (previous / "catalogue.csv").write_bytes(
        (baseline / "taxonomy_snapshot/taxonomy.csv").read_bytes()
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write(bundle / "source.csv", [r for r in rows if r["id"] in {2, 4}])
    write(
        bundle / "details.csv",
        [
            {
                "id": "2",
                "tên kỹ năng đề xuất": "UML",
                "trích dẫn nguyên văn làm bằng chứng": "UML",
            }
        ],
    )
    write(
        bundle / "claims.csv",
        [
            {
                "claim_id": "csv:2",
                "job_id": "2",
                "source_skill_name": "UML",
                "source_decision": "proposed",
                "source_evidence": "UML",
                "decision": "accept",
                "skill_code": "uml",
                "skill_name": "UML",
                "evidence": "UML",
                "reason": "fixture review",
                "condition": "",
                "requirements_text_hash": text_hash("Biết UML"),
            }
        ],
    )
    catalogue = read_csv(previous / "catalogue.csv")
    catalogue.append(
        {
            "skill_code": "uml",
            "skill_name": "UML",
            "skill_group": "domain",
            "definition": "UML fixture",
        }
    )
    write(bundle / "catalogue.csv", catalogue)
    (bundle / "policy.json").write_text('{"version":"fixture-policy"}')
    seal(bundle, baseline)
    return jobs, baseline, bundle


def run(proposal_input, output):
    return apply_review(*proposal_input, output, allow_unpinned_fixture=True)


def test_proposals_preserve_prior_jobs_and_distinguish_no_proposal(proposal_input, tmp_path):
    report = run(proposal_input, tmp_path / "out")
    assert report["target_jobs"] == 2 and report["added_pairs"] == 1
    assert report["status"] == "curated_proposals_applied_offline_not_db_published"
    assert report["status_counts"] == {
        "processed_match": 1,
        "reviewed_match": 1,
        "needs_review": 1,
        "review_no_proposal": 1,
    }
    old = pq.read_table(proposal_input[1] / "job_skill_status.parquet").to_pylist()
    new = pq.read_table(tmp_path / "out/job_skill_status.parquet").to_pylist()
    assert old[0] == new[0] and old[2] == new[2]
    assert new[3]["reasons"] == ["no_submitted_proposal_not_proof_of_absence"]
    assert new[3]["positive_skill_count"] == 0
    assert (tmp_path / "out/review_bundle/details.csv").read_bytes() == (
        proposal_input[2] / "details.csv"
    ).read_bytes()
    replay = run(proposal_input, tmp_path / "replay")
    assert report["artifacts"] == replay["artifacts"]


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("missing_population", "Review IDs differ"),
        ("foreign_proposal", "Detailed review population mismatch"),
        ("quote", "Original proposal evidence"),
        ("original_decision", "Original claim was changed"),
        ("unknown_kind", "Unknown review bundle kind"),
    ],
)
def test_proposal_tampering_rejected(proposal_input, tmp_path, mutation, error):
    jobs, baseline, bundle = proposal_input
    if mutation == "missing_population":
        rows = read_csv(bundle / "source.csv")
        write(bundle / "source.csv", rows[:1])
    if mutation in {"foreign_proposal", "quote"}:
        rows = read_csv(bundle / "details.csv")
        rows[0][
            "id" if mutation == "foreign_proposal" else "trích dẫn nguyên văn làm bằng chứng"
        ] = "1" if mutation == "foreign_proposal" else "invented"
        write(bundle / "details.csv", rows)
    if mutation == "original_decision":
        rows = read_csv(bundle / "claims.csv")
        rows[0]["source_decision"] = "approved"
        write(bundle / "claims.csv", rows)
    seal(bundle, baseline)
    if mutation == "unknown_kind":
        path = bundle / "bundle.json"
        document = json.loads(path.read_text())
        document["kind"] = "anything"
        path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match=error):
        run(proposal_input, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()


def test_rejected_proposal_is_different_from_no_proposal(proposal_input, tmp_path):
    jobs, baseline, bundle = proposal_input
    rows = read_csv(bundle / "claims.csv")
    rows[0]["decision"] = "reject"
    write(bundle / "claims.csv", rows)
    seal(bundle, baseline)
    report = run(proposal_input, tmp_path / "out")
    assert report["status_counts"]["reviewed_no_match"] == 1
    assert report["status_counts"]["review_no_proposal"] == 1
    assert report["added_pairs"] == 0


@pytest.fixture
def followup_input(proposal_input, tmp_path):
    jobs, _, _ = proposal_input
    baseline = tmp_path / "first_review"
    run(proposal_input, baseline)
    bundle = tmp_path / "followup_bundle"
    bundle.mkdir()
    write(
        bundle / "source.csv",
        [{"id": 4, "job_industry": SCOPE[0], "year": 2026, "requirements": "Biết BPMN"}],
    )
    write(
        bundle / "details.csv",
        [{"id": 4, "tên kỹ năng đề xuất": "BPMN", "trích dẫn nguyên văn làm bằng chứng": "BPMN"}],
    )
    write(
        bundle / "claims.csv",
        [
            {
                "claim_id": "csv:2",
                "job_id": 4,
                "source_skill_name": "BPMN",
                "source_decision": "proposed",
                "source_evidence": "BPMN",
                "decision": "accept",
                "skill_code": "bpmn",
                "skill_name": "BPMN",
                "evidence": "BPMN",
                "reason": "Explicit tool capability in the same requirements",
                "condition": "",
                "requirements_text_hash": text_hash("Biết BPMN"),
            }
        ],
    )
    catalogue = read_csv(baseline / "review_bundle/catalogue.csv")
    catalogue.append(
        {"skill_code": "bpmn", "skill_name": "BPMN", "skill_group": "domain", "definition": "BPMN"}
    )
    write(bundle / "catalogue.csv", catalogue)
    (bundle / "policy.json").write_text('{"version":"fixture-policy"}')
    seal_followup(bundle, baseline)
    return jobs, baseline, bundle


def seal_followup(bundle, baseline):
    seal(bundle, baseline)
    path = bundle / "bundle.json"
    document = json.loads(path.read_text())
    document["kind"] = "no_proposal_followup"
    path.write_text(json.dumps(document))


def test_followup_adds_only_reviewed_no_proposal_pairs(followup_input, tmp_path):
    jobs, baseline, bundle = followup_input
    before = pq.read_table(baseline / "job_skill_status.parquet").to_pylist()
    output = tmp_path / "followup_output"
    report = apply_review(jobs, baseline, bundle, output, allow_unpinned_fixture=True)
    assert report["target_jobs"] == 1 and report["added_pairs"] == 1
    assert report["bundle_kind"] == "no_proposal_followup"
    after = pq.read_table(output / "job_skill_status.parquet").to_pylist()
    assert before[:3] == after[:3]
    assert after[3]["status"] == "reviewed_match"
    assert after[3]["positive_skill_count"] == 1
    old_pairs = pq.read_table(baseline / "job_skill_match.parquet").to_pylist()
    new_pairs = pq.read_table(output / "job_skill_match.parquet").to_pylist()
    assert new_pairs[: len(old_pairs)] == old_pairs
    old_evidence = pq.read_table(baseline / "job_skill_evidence.parquet").to_pylist()
    new_evidence = pq.read_table(output / "job_skill_evidence.parquet").to_pylist()
    assert new_evidence[: len(old_evidence)] == old_evidence
    replay = apply_review(jobs, baseline, bundle, tmp_path / "replay", allow_unpinned_fixture=True)
    assert report["artifacts"] == replay["artifacts"]


@pytest.mark.parametrize(
    "decision,status", [("reject", "reviewed_no_match"), ("unclear", "needs_review")]
)
def test_followup_never_turns_unclear_or_rejected_into_a_pair(
    followup_input, tmp_path, decision, status
):
    jobs, baseline, bundle = followup_input
    claims = read_csv(bundle / "claims.csv")
    claims[0]["decision"] = decision
    write(bundle / "claims.csv", claims)
    seal_followup(bundle, baseline)
    report = apply_review(jobs, baseline, bundle, tmp_path / "out", allow_unpinned_fixture=True)
    assert report["added_pairs"] == 0
    assert report["status_counts"][status] >= 1


def test_followup_cannot_rewrite_a_job_already_with_skills(followup_input, tmp_path):
    jobs, baseline, bundle = followup_input
    source = read_csv(bundle / "source.csv")
    source[0].update(id="2", requirements="Biết UML")
    write(bundle / "source.csv", source)
    seal_followup(bundle, baseline)
    with pytest.raises(ValueError, match="Review IDs differ"):
        apply_review(jobs, baseline, bundle, tmp_path / "out", allow_unpinned_fixture=True)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("bad_receipt", [False, True])
def test_followup_requires_matching_completed_review(
    followup_input, tmp_path, monkeypatch, bad_receipt
):
    import job_warehouse.skills.review_import as importer

    jobs, baseline, bundle = followup_input
    verifier = importer.verify_jobs_run
    monkeypatch.setattr(
        importer,
        "verify_jobs_run",
        lambda path, **kwargs: verifier(path, allow_unpinned_fixture=True),
    )
    audit = baseline / "technical_audit.json"
    audit.write_text('{"fixture":"passed"}')
    completion = baseline / "review_completion.json"
    completion.write_text(
        json.dumps(
            {
                "status": "reviewed_proposals_offline_not_db_published",
                "manifest_sha256": file_sha256(baseline / "manifest.json"),
                "technical_audit_sha256": file_sha256(audit),
            }
        )
    )
    path = bundle / "bundle.json"
    document = json.loads(path.read_text())
    document["baseline_acceptance_sha256"] = file_sha256(completion)
    path.write_text(json.dumps(document))
    if bad_receipt:
        completion.write_text('{"status":"not_completed"}')
        with pytest.raises(ValueError, match="Baseline acceptance mismatch"):
            apply_review(jobs, baseline, bundle, tmp_path / "out")
    else:
        assert apply_review(jobs, baseline, bundle, tmp_path / "out")["added_pairs"] == 1
