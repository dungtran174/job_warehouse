"""Synthetic full-run checks: partition, replay, serialization and failed publication."""

# Optional Arrow dependency must be gated before importing the runner.
# ruff: noqa: E402

import json
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.cli import main
from job_warehouse.history.contract import COLUMNS
from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.core_runner import run_core
from job_warehouse.silver.schema import core_schema


@pytest.fixture
def silver_file(tmp_path):
    rows = [
        {
            **dict.fromkeys(COLUMNS, "Synthetic"),
            "id": i + 1,
            "year": 2025,
            "job_title": "  Developer C++  ",
            "company_name": None,
            "job_type": "Toàn thời gian, Remote",
            "job_position": "Nhân viên",
            "education_level": "Không",
            "experience_level": "1 tháng",
            "requirements": "Tốt nghiệp Đại học. Có tối thiểu 2 năm kinh nghiệm.",
        }
        for i in range(8)
    ]
    rows[0]["job_title"] = None
    rows[1]["job_title"] = "Không"
    rows[3]["requirements"] = "Ưu tiên có 2 năm kinh nghiệm."
    rows[4]["requirements"] = "Tốt nghiệp Công nghệ tại Đại học; biết C++ &amp; C#."
    rows[5]["requirements"] = None
    rows[6]["requirements"] = "Cao đẳng và 3 năm kinh nghiệm hoặc đại học và 1 năm."
    rows[7]["requirements"] = "Không có kinh nghiệm vẫn được đào tạo."
    path = tmp_path / "input.parquet"
    schema = pa.schema([(c, pa.int64() if c in {"id", "year"} else pa.string()) for c in COLUMNS])
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, row_group_size=3)
    return path


def run(path, output, **kwargs):
    return run_core(
        path,
        output,
        expected_sha256=file_sha256(path),
        expected_rows=8,
        expected_quarantine=2,
        **kwargs,
    )


def test_full_run_roundtrips_raw_and_evidence_and_replays_without_duplicates(silver_file, tmp_path):
    before = silver_file.read_bytes()
    a = run(silver_file, tmp_path / "one", batch_size=1)
    b = run(silver_file, tmp_path / "many", batch_size=7)
    assert a["content_digest"] == b["content_digest"]
    assert a["run_signature"] == b["run_signature"]
    assert a["partition"] == {"core": 6, "quarantine": 2, "keys_unique_complete": True}
    assert not a["source"]["pinned_artifact_verified"]
    assert a["semantic_validation"] == "pending_independent_review"
    raw = pq.read_table(silver_file).to_pylist()
    core = pq.read_table(tmp_path / "one/core.parquet").to_pylist()
    quarantine = pq.read_table(tmp_path / "one/core_quarantine.parquet").to_pylist()
    assert len({r["record_key"] for r in core + quarantine}) == 8
    for row in core + quarantine:
        assert all(row[c] == raw[row["source_row_index"]][c] for c in COLUMNS)
    for row in core:
        assert row["experience_years_rounded"]
        assert row["experience_min_months"] == 1
        for field in ["education", "experience"]:
            for claim in row[field + "_inference_claims"]:
                assert (
                    claim["evidence_text"]
                    == row["requirements_clean"][claim["start_offset"] : claim["end_offset"]]
                )
                assert claim["requirements_text_hash"] == row["requirements_text_hash"]
    assert core == pq.read_table(tmp_path / "many/core.parquet").to_pylist()
    negated = next(r for r in core if r["source_row_index"] == 7)
    claim = negated["experience_inference_claims"][0]
    assert claim["context"] == "negated"
    assert claim["parsed_value"]["experience"] is None
    assert negated["experience_inferred_min_months"] is None
    assert silver_file.read_bytes() == before
    manifest = json.loads((tmp_path / "one/manifest.json").read_text())
    for name, details in manifest["artifacts"].items():
        assert file_sha256(tmp_path / "one" / name) == details["sha256"]
    report = json.loads((tmp_path / "one/core_quality_report.json").read_text())
    assert report["counts"]["quarantine:missing_title"] == 1
    assert report["counts"]["quarantine:title_ambiguous_literal"] == 1
    assert report["counts"]["experience_inference_status:complex"] == 1


def test_existing_output_is_never_overwritten(silver_file, tmp_path):
    output = tmp_path / "good"
    run(silver_file, output)
    saved = (output / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        run(silver_file, output)
    assert (output / "manifest.json").read_bytes() == saved


def test_mixed_units_and_student_policy_survive_parquet_roundtrip(silver_file, tmp_path):
    table = pq.read_table(silver_file)
    rows = table.to_pylist()
    rows[2]["experience_level"] = "6 tháng–1 năm"
    rows[2]["requirements"] = "Có từ 6 tháng–1 năm kinh nghiệm. Ưu tiên sinh viên Đại học."
    pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), silver_file)
    run(silver_file, tmp_path / "mixed")
    row = next(
        r
        for r in pq.read_table(tmp_path / "mixed/core.parquet").to_pylist()
        if r["source_row_index"] == 2
    )
    assert row["experience_level"] == "6 tháng–1 năm"
    assert (row["experience_min_months"], row["experience_max_months"]) == (6, 12)
    assert (row["experience_inferred_min_months"], row["experience_inferred_max_months"]) == (6, 12)
    assert row["experience_source_min"] == "6 tháng"
    assert row["experience_source_max"] == "1 năm"
    student = row["education_inference_claims"][0]
    assert student["context"] == "preferred"
    assert student["parsed_value"]["qualification_state"] == "student"
    assert row["education_inferred_options"] == []


@pytest.mark.parametrize(
    "mutation", ["sha", "count", "quarantine", "duplicate_id", "year", "schema"]
)
def test_bad_input_or_partition_does_not_publish(silver_file, tmp_path, mutation):
    kwargs = {
        "expected_sha256": file_sha256(silver_file),
        "expected_rows": 8,
        "expected_quarantine": 2,
    }
    if mutation == "sha":
        kwargs["expected_sha256"] = "0" * 64
    elif mutation == "count":
        kwargs["expected_rows"] = 9
    elif mutation == "quarantine":
        kwargs["expected_quarantine"] = 1
    else:
        table = pq.read_table(silver_file)
        if mutation == "schema":
            table = table.drop(["requirements"])
        else:
            column = "id" if mutation == "duplicate_id" else "year"
            values = table[column].to_pylist()
            values[2] = values[3] if mutation == "duplicate_id" else 2027
            table = table.set_column(table.schema.get_field_index(column), column, pa.array(values))
        pq.write_table(table, silver_file)
        kwargs["expected_sha256"] = file_sha256(silver_file)
    with pytest.raises(ValueError):
        run_core(silver_file, tmp_path / "bad", **kwargs)
    assert not (tmp_path / "bad").exists()
    assert not list(tmp_path.glob(".silver-core-*"))


@pytest.mark.parametrize("failure", ["normalization", "input_change", "asset_change"])
def test_interrupted_run_cleans_unpublished_staging(silver_file, tmp_path, monkeypatch, failure):
    import job_warehouse.silver.core_runner as runner

    if failure == "normalization":

        def fail(*args, **kwargs):
            raise RuntimeError("synthetic crash")

        monkeypatch.setattr(runner, "normalize_row", fail)
    elif failure == "input_change":
        monkeypatch.setattr(runner, "file_sha256", lambda path: "0" * 64)
    else:
        original = runner.configuration_hashes
        calls = 0

        def changed():
            nonlocal calls
            calls += 1
            return original() if calls == 1 else {"changed": "1"}

        monkeypatch.setattr(runner, "configuration_hashes", changed)
    with pytest.raises((ValueError, RuntimeError)):
        run(silver_file, tmp_path / "incomplete")
    assert not (tmp_path / "incomplete").exists()
    assert not list(tmp_path.glob(".silver-core-*"))


def test_empty_core_has_explicit_schema(silver_file, tmp_path):
    table = pq.read_table(silver_file).slice(0, 2)
    pq.write_table(table, silver_file)
    manifest = run_core(
        silver_file,
        tmp_path / "all-quarantine",
        expected_sha256=file_sha256(silver_file),
        expected_rows=2,
        expected_quarantine=2,
    )
    assert manifest["partition"]["core"] == 0
    assert pq.read_schema(tmp_path / "all-quarantine/core.parquet") == core_schema()


def test_cli_is_pinned_and_outputs_cannot_enter_repository(silver_file, tmp_path, capsys):
    assert (
        main(["silver", "core", "--input", str(silver_file), "--output-dir", str(tmp_path / "cli")])
        == 2
    )
    assert "SHA256" in capsys.readouterr().err
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside the repository"):
        run(silver_file, root / "no-real-outputs")
    assert not (root / "no-real-outputs").exists()


def test_installed_runner_still_rejects_project_output(silver_file, tmp_path, monkeypatch):
    import job_warehouse.silver.core_runner as runner

    monkeypatch.setattr(
        runner,
        "__file__",
        str(tmp_path / "installed/site-packages/job_warehouse/silver/core_runner.py"),
    )
    checkout = tmp_path / "checkout"
    (checkout / "src/job_warehouse").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text("[project]\nname='synthetic'\n")
    with pytest.raises(ValueError, match="outside the repository"):
        run(silver_file, checkout / "data/s2")
    assert not (checkout / "data").exists()
