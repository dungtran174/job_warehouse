"""Source integrity and text-disjoint sampling using entirely synthetic jobs."""

import json
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.cli import main  # noqa: E402
from job_warehouse.history.identity import file_sha256  # noqa: E402
from job_warehouse.skills.input import SCOPE, verify_jobs_run  # noqa: E402
from job_warehouse.skills.profile import prepare_skills  # noqa: E402


@pytest.fixture
def skills_input(tmp_path):
    directory = tmp_path / "s4"
    directory.mkdir()
    rows = [
        {
            "id": index + 1,
            "job_industry": SCOPE[index % 3],
            "year": 2022 + index % 5,
            "requirements": f"Synthetic requirement {index}",
        }
        for index in range(30)
    ]
    rows.extend(
        [
            {**rows[0], "id": 31},
            {**rows[0], "id": 32, "job_industry": SCOPE[1]},
            {**rows[0], "id": 33, "requirements": None},
            {**rows[0], "id": 34, "requirements": " KHÔNG "},
            {**rows[0], "id": 35, "job_industry": "Other industry"},
        ]
    )
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("job_industry", pa.string()),
            ("year", pa.int16()),
            ("requirements", pa.string()),
        ]
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), directory / "jobs_analysis.parquet")
    update_manifest(directory)
    return directory


def update_manifest(directory):
    path = directory / "jobs_analysis.parquet"
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture", "pinned_artifact_verified": False},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
                "partition": {"analysis": pq.ParquetFile(path).metadata.num_rows},
            }
        )
    )


def prepare(source, output, **kwargs):
    return prepare_skills(
        source,
        output,
        tune_per_industry=2,
        holdout_per_industry=2,
        allow_unpinned_fixture=True,
        **kwargs,
    )


def test_sampling_is_global_text_disjoint_and_reproducible(skills_input, tmp_path):
    hashes = {p: file_sha256(p) for p in skills_input.iterdir()}
    first = prepare(skills_input, tmp_path / "first", batch_size=1)
    second = prepare(skills_input, tmp_path / "second", batch_size=13)
    assert first == second
    assert first["counts"] == {
        "input_rows": 35,
        "scope_rows": 34,
        "usable": 32,
        "missing": 1,
        "unusable": 1,
        "outside_scope": 1,
    }
    assert first["distinct_usable_texts_in_scope"] == 30
    splits = []
    for split in ["tune", "holdout"]:
        name = f"{split}_unlabelled.json"
        samples = json.loads((tmp_path / "first" / name).read_text())
        assert len(samples) == 6
        assert len({s["requirements_text_hash"] for s in samples}) == 6
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
        assert all("prediction" not in s for s in samples)
        splits.append({s["requirements_text_hash"] for s in samples})
    assert splits[0].isdisjoint(splits[1])
    assert all(file_sha256(p) == sha for p, sha in hashes.items())


def test_duplicate_ids_abort_and_leave_no_partial_output(skills_input, tmp_path):
    path = skills_input / "jobs_analysis.parquet"
    table = pq.read_table(path)
    rows = table.to_pylist()
    rows[1]["id"] = rows[0]["id"]
    pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), path)
    update_manifest(skills_input)
    with pytest.raises(ValueError, match="duplicate job ID"):
        prepare(skills_input, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_tampering_and_real_cli_reject_unpinned_input(skills_input, tmp_path):
    assert (
        main(
            [
                "silver",
                "skills-prepare",
                "--jobs-run",
                str(skills_input),
                "--output-dir",
                str(tmp_path / "not-created"),
            ]
        )
        == 2
    )
    path = skills_input / "jobs_analysis.parquet"
    with path.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="SHA mismatch"):
        prepare(skills_input, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_acceptance_must_verify_same_run_manifest(skills_input):
    manifest_path = skills_input / "manifest.json"
    data = json.loads(manifest_path.read_text())
    from job_warehouse.history.contract import REVISION

    data["source"] = {
        "revision": REVISION,
        "pinned_artifact_verified": True,
        "dataset": "tinixai/vietnamese-job-descriptions",
    }
    manifest_path.write_text(json.dumps(data))
    acceptance = {"status": "accepted_offline_not_db_published", "run_manifest_sha256": "old"}
    (skills_input / "acceptance.json").write_text(json.dumps(acceptance))
    with pytest.raises(ValueError, match="acceptance"):
        verify_jobs_run(skills_input)


def test_output_must_be_new_and_outside_repo(skills_input, tmp_path):
    prepare(skills_input, tmp_path / "exists")
    with pytest.raises(ValueError, match="new output"):
        prepare(skills_input, tmp_path / "exists")
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside"):
        prepare(skills_input, repo / "forbidden-skills-output")
