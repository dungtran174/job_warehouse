"""Immutable input, full accounting, traceable evidence and stable candidate runs."""

import json

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.history.identity import file_sha256  # noqa: E402
from job_warehouse.skills.input import SCOPE  # noqa: E402
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS, run_skills  # noqa: E402


@pytest.fixture
def input_jobs(tmp_path):
    directory = tmp_path / "s4"
    directory.mkdir()
    texts = [
        "Biết Python và Python; ưu tiên Excel",
        "IELTS 6.5",
        None,
        "KHÔNG",
        "Synthetic requirement without any mapped skill",
        "Biết Java",
        "Office",
        "Biết Python và Python; ưu tiên Excel",
    ]
    rows = [
        {"id": i + 1, "job_industry": SCOPE[i % 3], "year": 2026, "requirements": text}
        for i, text in enumerate(texts)
    ]
    rows[5]["job_industry"] = "Other industry"
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("job_industry", pa.string()),
            ("year", pa.int16()),
            ("requirements", pa.string()),
        ]
    )
    path = directory / "jobs_analysis.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture", "pinned_artifact_verified": False},
                "partition": {"analysis": len(rows)},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
            }
        )
    )
    return directory


def run(source, destination, **kwargs):
    return run_skills(source, destination, allow_unpinned_fixture=True, **kwargs)


def test_replay_status_partition_and_pair_evidence(input_jobs, tmp_path):
    hashes = {p: file_sha256(p) for p in input_jobs.iterdir()}
    one = run(input_jobs, tmp_path / "one", batch_size=1)
    many = run(input_jobs, tmp_path / "many", batch_size=7)
    assert one["artifacts"] == many["artifacts"]
    assert one["status"] == "candidate_skills_not_semantically_accepted"
    assert one["counts"] == {
        "input_rows": 8,
        "scope_rows": 7,
        "scope_eligible": 5,
        "scope_missing_requirements": 1,
        "scope_unusable_requirements": 1,
        "processed_match": 3,
        "missing_requirements": 1,
        "unusable_requirements": 1,
        "processed_no_match": 1,
        "out_of_scope": 1,
        "needs_review": 1,
    }
    assert one["coverage"]["fraction_in_scope"] == 4 / 5
    pairs = pq.read_table(tmp_path / "one/job_skill_match.parquet").to_pylist()
    assert [(p["job_id"], p["skill_code"]) for p in pairs] == [
        (1, "excel"),
        (1, "python"),
        (2, "english"),
        (8, "excel"),
        (8, "python"),
    ]
    assert set(pairs[0]) == {"job_id", "skill_code", "skill_name"}
    statuses = pq.read_table(tmp_path / "one/job_skill_status.parquet").to_pylist()
    assert len(statuses) == len({r["job_id"] for r in statuses}) == 8
    evidence = pq.read_table(tmp_path / "one/job_skill_evidence.parquet").to_pylist()
    assert len([e for e in evidence if e["job_id"] == 1]) == 3
    assert any(e["rule_id"].startswith("certificate_to_language:") for e in evidence)
    assert not any(e["positive_pair_included"] for e in evidence if e["job_id"] == 7)
    for name, schema in ARTIFACT_SCHEMAS.items():
        assert pq.read_schema(tmp_path / "one" / name) == schema
    manifest = json.loads((tmp_path / "one/manifest.json").read_text())
    for name, detail in manifest["artifacts"].items():
        assert file_sha256(tmp_path / "one" / name) == detail["sha256"]
    assert all(file_sha256(p) == sha for p, sha in hashes.items())
    assert not (tmp_path / "one/acceptance.json").exists()


def test_changed_input_refused_before_publishing(input_jobs, tmp_path):
    with (input_jobs / "jobs_analysis.parquet").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="SHA mismatch"):
        run(input_jobs, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()


def test_processing_error_does_not_publish_partial_run(input_jobs, tmp_path, monkeypatch):
    from job_warehouse.skills import runner

    def fail(*args):
        raise ValueError("Synthetic processing failure")

    monkeypatch.setattr(runner.SkillMatcher, "extract", fail)
    with pytest.raises(ValueError, match="Synthetic processing failure"):
        run(input_jobs, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".skills-*"))


def test_real_runner_never_exposes_fixture_bypass_on_cli(input_jobs, tmp_path):
    with pytest.raises(ValueError, match="Unpinned"):
        run_skills(input_jobs, tmp_path / "failed")


def test_upstream_changes_during_processing_are_rejected(input_jobs, tmp_path, monkeypatch):
    from job_warehouse.skills import runner

    original = runner.SkillMatcher.extract

    def mutate(self, text):
        (input_jobs / "manifest.json").write_text("changed during run")
        return original(self, text)

    monkeypatch.setattr(runner.SkillMatcher, "extract", mutate)
    with pytest.raises(ValueError, match="input changed"):
        run(input_jobs, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
