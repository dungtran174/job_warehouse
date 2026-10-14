"""Synthetic source mapping, selection and atomic publication checks."""

# ruff: noqa: E402
import json

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.cli import main
from job_warehouse.history.identity import file_sha256, record_key
from job_warehouse.silver.industry_runner import read_policy, run_industry


def prepare(tmp_path, labels=None):
    labels = (
        labels
        if labels is not None
        else [
            "IT Phần mềm",
            "IT phần mềm",
            "CNTT - Phần mềm",
            "Giáo dục - Đào tạo",
            "Chăm sóc khách hàng",
            "Tư vấn Chăm sóc khách hàng",
            "Nghề nghiệp khác",
            "Nghề nghiệp khác",
            "rare",
        ]
    )
    bronze = tmp_path / "bronze.parquet"
    pq.write_table(
        pa.table(
            {
                "id": pa.array(range(len(labels)), type=pa.int64()),
                "job_industry": pa.array(labels, type=pa.string()),
            }
        ),
        bronze,
    )
    digest = file_sha256(bronze)
    base = tmp_path / "base"
    base.mkdir()
    table = pa.table(
        {
            "source_row_index": pa.array(range(len(labels)), type=pa.int64()),
            "source_dataset_id": pa.array(range(len(labels)), type=pa.int64()),
            "record_key": pa.array(
                [record_key(digest, i) for i in range(len(labels))], type=pa.string()
            ),
            "location": pa.array(["Hà Nội"] * len(labels), type=pa.string()),
        }
    )
    pq.write_table(table, base / "enrichment.parquet")
    (base / "manifest.json").write_text(
        json.dumps(
            {
                "partition": {"enrichment": len(labels)},
                "artifacts": {
                    "enrichment.parquet": {"sha256": file_sha256(base / "enrichment.parquet")}
                },
            }
        )
    )
    return bronze, base


def test_published_owner_policy_keeps_latest_decisions():
    decisions, rows = read_policy()
    assert len(decisions) == 253
    assert "Giáo dục - Đào tạo" not in decisions
    assert "Chăm sóc khách hàng" not in decisions
    assert "Nhân viên kinh doanh" not in decisions
    assert decisions["Tư vấn chăm sóc khách hàng"] == "Chăm sóc khách hàng"
    assert sum(r["decision_code"].startswith("C") for r in rows) == 204


def test_counts_after_alias_and_rollup_selection_replay_and_preservation(tmp_path):
    bronze, base = prepare(tmp_path)
    original = file_sha256(bronze), file_sha256(base / "enrichment.parquet")
    a = run_industry(
        bronze, base, tmp_path / "one", threshold=2, batch_size=2, allow_unpinned_fixture=True
    )
    b = run_industry(
        bronze, base, tmp_path / "two", threshold=2, batch_size=4, allow_unpinned_fixture=True
    )
    assert a["partition"] == b["partition"] == {"enrichment": 9, "analysis": 7}
    full = pq.read_table(tmp_path / "one/enrichment.parquet")
    assert full.equals(pq.read_table(tmp_path / "two/enrichment.parquet"))
    assert full["job_industry"].to_pylist()[:3] == ["Công nghệ thông tin"] * 3
    assert full["job_industry"].to_pylist()[3:6] == [
        "Giáo dục - Đào tạo",
        "Chăm sóc khách hàng",
        "Chăm sóc khách hàng",
    ]
    assert full.select(pq.read_schema(base / "enrichment.parquet").names).equals(
        pq.read_table(base / "enrichment.parquet")
    )
    assert original == (file_sha256(bronze), file_sha256(base / "enrichment.parquet"))
    for name, info in a["artifacts"].items():
        assert file_sha256(tmp_path / "one" / name) == info["sha256"]
    # A second run on an already labelled base recomputes only industry fields.
    run_industry(
        bronze, tmp_path / "one", tmp_path / "three", threshold=2, allow_unpinned_fixture=True
    )
    assert full.equals(pq.read_table(tmp_path / "three/enrichment.parquet"))


def test_empty_and_all_below_threshold_keep_typed_full_data(tmp_path):
    bronze, base = prepare(tmp_path, [])
    result = run_industry(bronze, base, tmp_path / "empty", allow_unpinned_fixture=True)
    assert result["partition"] == {"enrichment": 0, "analysis": 0}
    assert pq.read_schema(tmp_path / "empty/jobs_analysis.parquet") == pq.read_schema(
        tmp_path / "empty/enrichment.parquet"
    )


def test_rejects_tampered_base_without_publishing(tmp_path):
    bronze, base = prepare(tmp_path)
    with (base / "enrichment.parquet").open("ab") as f:
        f.write(b"tampered")
    with pytest.raises(ValueError, match="SHA"):
        run_industry(bronze, base, tmp_path / "out", allow_unpinned_fixture=True)
    assert not (tmp_path / "out").exists()


def test_rejects_wrong_source_identity(tmp_path):
    bronze, base = prepare(tmp_path)
    p = base / "enrichment.parquet"
    table = pq.read_table(p)
    table = table.set_column(1, "source_dataset_id", pa.array([999] * table.num_rows))
    pq.write_table(table, p)
    m = json.loads((base / "manifest.json").read_text())
    m["artifacts"]["enrichment.parquet"]["sha256"] = file_sha256(p)
    (base / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="identity"):
        run_industry(bronze, base, tmp_path / "out", allow_unpinned_fixture=True)
    assert not (tmp_path / "out").exists()


def test_cli_requires_pinned_input(tmp_path, capsys):
    bronze, base = prepare(tmp_path)
    assert (
        main(
            [
                "silver",
                "industry",
                "--bronze",
                str(bronze),
                "--base-run",
                str(base),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    assert "pinned" in capsys.readouterr().err
