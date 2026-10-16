"""Reproducible publication, upstream identity validation and business projection."""

import json

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.history.identity import file_sha256, record_key  # noqa: E402
from job_warehouse.silver.salary.runner import CORE_COLUMNS, run_salary  # noqa: E402


@pytest.fixture
def salary_inputs(tmp_path):
    core, industry = tmp_path / "core", tmp_path / "industry"
    core.mkdir()
    industry.mkdir()
    sha = "a" * 64
    ids = [1, 2, 6653, 3, 3199]
    salaries = ["10 - 15 triệu", "1000 USD", "10 triệu/giờ", "100", "5 triệu/ngày"]
    core_rows, enrichment = [], []
    for index, (ident, salary) in enumerate(zip(ids, salaries, strict=True)):
        row = dict.fromkeys(CORE_COLUMNS)
        row.update(
            id=ident,
            record_key=record_key(sha, index),
            source_row_index=index,
            source_content_hash="synthetic",
            salary=salary,
            year=2026,
            job_title_clean="Synthetic developer",
            company_name_clean="Synthetic Company",
            education_label_clean="Cử nhân",
            job_type_label_clean="Toàn thời gian, Remote",
            position_label_clean="Nhân viên",
            requirements_clean="Synthetic requirement",
        )
        core_rows.append(row)
        enrichment.append(
            dict(
                record_key=row["record_key"],
                source_dataset_id=ident,
                source_row_index=index,
                source_content_hash="synthetic",
                year_value=2026,
                job_industry="Synthetic industry",
                location="Hà Nội; Hồ Chí Minh",
                industry_scope_500=index < 3,
            )
        )
    pq.write_table(pa.Table.from_pylist(core_rows), core / "core.parquet")
    pq.write_table(pa.Table.from_pylist(enrichment), industry / "enrichment.parquet")
    for directory, name, partition in [
        (core, "core.parquet", {"core": 5}),
        (industry, "enrichment.parquet", {"enrichment": 5, "analysis": 3}),
    ]:
        manifest = {
            "partition": partition,
            "input": {"sha256": sha},
            "source": {"revision": "fixture", "pinned_artifact_verified": False},
            "artifacts": {name: {"sha256": file_sha256(directory / name)}},
        }
        (directory / "manifest.json").write_text(json.dumps(manifest))
    return core, industry


def run(inputs, destination, **kwargs):
    return run_salary(*inputs, destination, allow_unpinned_fixture=True, **kwargs)


def test_replay_keeps_keys_selection_source_fields_and_expected_measures(salary_inputs, tmp_path):
    hashes = {p: file_sha256(p) for d in salary_inputs for p in d.iterdir()}
    first = run(salary_inputs, tmp_path / "one", batch_size=1)
    second = run(salary_inputs, tmp_path / "many", batch_size=4)
    assert first["content_digest"] == second["content_digest"]
    assert first["partition"] == {"core": 5, "analysis": 3}
    assert not first["fx_complete"]
    assert first["summary"]["comparison_coverage_by_industry_year"] == [
        {
            "job_industry": "Synthetic industry",
            "year": 2026,
            "records": 5,
            "numeric_eligible": 2,
            "midpoint_eligible": 2,
            "analysis_records": 3,
            "analysis_numeric_eligible": 2,
            "analysis_midpoint_eligible": 2,
        }
    ]
    jobs = pq.read_table(tmp_path / "one/jobs.parquet").to_pylist()
    assert len(jobs) == 5
    assert jobs[0]["salary_min"] == 10_000_000
    assert jobs[0]["salary_max"] == 15_000_000
    assert jobs[1]["salary_min"] is None  # No silent conversion of USD to VND.
    assert jobs[2]["salary_min"] == jobs[2]["salary_max"] == 10_000_000
    assert jobs[3]["salary_min"] is None
    assert jobs[4]["salary_min"] is None
    assert jobs[0]["location"] == ["Hà Nội", "Hồ Chí Minh"]
    assert jobs[0]["education_level"] == "Cử nhân"
    assert jobs[0]["job_type"] == "Toàn thời gian, Remote"
    assert pq.read_table(tmp_path / "one/jobs_analysis.parquet").to_pylist() == jobs[:3]
    assert jobs == pq.read_table(tmp_path / "many/jobs.parquet").to_pylist()
    audit = pq.read_table(tmp_path / "one/salary_enrichment.parquet").to_pylist()
    assert [r["salary_midpoint_eligible"] for r in audit] == [True, False, True, False, False]
    assert [r["salary"] for r in audit] == [
        "10 - 15 triệu",
        "1000 USD",
        "10 triệu/giờ",
        "100",
        "5 triệu/ngày",
    ]
    for name, details in first["artifacts"].items():
        assert file_sha256(tmp_path / "one" / name) == details["sha256"]
    assert all(file_sha256(p) == h for p, h in hashes.items())
    with pytest.raises(ValueError, match="new output"):
        run(salary_inputs, tmp_path / "one")


def test_hash_tampering_is_rejected_before_output(salary_inputs, tmp_path):
    with (salary_inputs[0] / "core.parquet").open("ab") as stream:
        stream.write(b"tampered")
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="SHA mismatch"):
        run(salary_inputs, destination)
    assert not destination.exists()


def test_identity_disagreement_cleans_partial_publication(salary_inputs, tmp_path):
    path = salary_inputs[1] / "enrichment.parquet"
    rows = pq.read_table(path).to_pylist()
    rows[2]["source_content_hash"] = "different content"
    pq.write_table(pa.Table.from_pylist(rows), path)
    manifest = salary_inputs[1] / "manifest.json"
    document = json.loads(manifest.read_text())
    document["artifacts"][path.name]["sha256"] = file_sha256(path)
    manifest.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="content mismatch"):
        run(salary_inputs, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".salary-*"))


def test_real_cli_never_accepts_unpinned_inputs(salary_inputs, tmp_path):
    with pytest.raises(ValueError, match="Unpinned"):
        run_salary(*salary_inputs, tmp_path / "failed")


def test_runner_checks_reviewed_benefits_hash_before_assigning_salary(
    salary_inputs, tmp_path, monkeypatch
):
    from dataclasses import replace
    from hashlib import sha256

    from job_warehouse.silver.salary import policy, runner

    benefits = "Synthetic reviewed base salary"
    decisions = dict(policy.owner_overrides())
    decisions[653] = replace(
        decisions[653], expected_raw="100", evidence_sha256=sha256(benefits.encode()).hexdigest()
    )
    monkeypatch.setattr(policy, "owner_overrides", lambda: decisions)
    monkeypatch.setattr(runner, "owner_overrides", lambda: decisions)
    path = salary_inputs[0] / "core.parquet"
    records = pq.read_table(path).to_pylist()
    records[3]["id"] = 653
    records[3]["benefits"] = benefits
    pq.write_table(pa.Table.from_pylist(records), path)
    manifest = salary_inputs[0] / "manifest.json"
    data = json.loads(manifest.read_text())
    data["artifacts"][path.name]["sha256"] = file_sha256(path)
    manifest.write_text(json.dumps(data))
    epath = salary_inputs[1] / "enrichment.parquet"
    erows = pq.read_table(epath).to_pylist()
    erows[3]["source_dataset_id"] = 653
    pq.write_table(pa.Table.from_pylist(erows), epath)
    emanifest = salary_inputs[1] / "manifest.json"
    data = json.loads(emanifest.read_text())
    data["artifacts"][epath.name]["sha256"] = file_sha256(epath)
    emanifest.write_text(json.dumps(data))
    run(salary_inputs, tmp_path / "reviewed")
    published = pq.read_table(tmp_path / "reviewed/jobs.parquet").to_pylist()[3]
    assert (published["salary_min"], published["salary_max"]) == (3_000_000, 5_000_000)
    records[3]["benefits"] = "Different benefits not reviewed"
    pq.write_table(pa.Table.from_pylist(records), path)
    data = json.loads(manifest.read_text())
    data["artifacts"][path.name]["sha256"] = file_sha256(path)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="benefits evidence mismatch"):
        run(salary_inputs, tmp_path / "changed")
    assert not (tmp_path / "changed").exists()
