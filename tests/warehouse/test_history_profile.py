"""Synthetic Parquet tests; no real input, network, database or crawler required."""

# Gate optional dependencies before importing the profiling implementation.
# ruff: noqa: E402

import csv
import json

import pytest

pa = pytest.importorskip(
    "pyarrow", reason="Install the warehouse extra to test historical profiling"
)
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.cli import main
from job_warehouse.history.contract import COLUMNS, HistoryProfileError
from job_warehouse.history.identity import content_fingerprint, file_sha256, record_key
from job_warehouse.history.profile import profile_history, write_profile


@pytest.fixture
def synthetic_rows():
    rows = [
        {
            "id": index + 1,
            "job_title": f"Vị trí thử nghiệm {index + 1}",
            "company_name": "Công ty tổng hợp A",
            "salary": "10.000.000 - 15.000.000 VND",
            "location": "Hà Nội | Hồ Chí Minh",
            "job_type": "Toàn thời gian",
            "job_industry": "IT phần mềm",
            "experience_level": "1–3 năm",
            "education_level": "Không",
            "job_position": "Nhân viên",
            "job_description": "Mô tả tổng hợp, không phải dữ liệu tuyển dụng thật.",
            "benefits": "Phúc lợi tổng hợp.",
            "requirements": "Biết C++, C#, .NET; không yêu cầu Python; ưu tiên SQL.",
            "year": 2025,
        }
        for index in range(32)
    ]
    # Same complete content under another dataset ID; a different year stays distinct.
    rows[1] = {**rows[0], "id": 2}
    rows[2] = {**rows[0], "id": 3, "year": 2024}
    rows[3] = {**rows[0], "id": 4, "requirements": None, "benefits": None}
    rows[4] = {**rows[3], "id": 5, "requirements": ""}
    rows[5] = {**rows[0], "id": 6, "company_name": "Công ty A"}
    rows[6] = {**rows[5], "id": 7, "company_name": " Công ty A "}
    rows[7] = {**rows[0], "id": 8, "requirements": "Yêu cầu khác dù cùng title/company."}
    rows[8]["salary"] = "0 VND"
    rows[9]["job_industry"] = "Chưa xác định"
    rows[10]["job_title"] = None
    rows[11]["company_name"] = None
    rows[12]["requirements"] = " \t\n"
    return rows


def write_parquet(path, rows, *, columns=COLUMNS):
    schema = pa.schema(
        [(column, pa.int64() if column in {"id", "year"} else pa.string()) for column in columns]
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, row_group_size=7)
    return path


@pytest.fixture
def input_file(tmp_path, synthetic_rows):
    return write_parquet(tmp_path / "synthetic.parquet", synthetic_rows)


def test_full_profile_preserves_input_and_original_value_semantics(input_file):
    original_bytes = input_file.read_bytes()
    result = profile_history(
        input_file, batch_size=3, expected_sha256=file_sha256(input_file), expected_rows=32
    )
    assert result.passed
    assert result.summary()["source"]["pinned_artifact_verified"] is False
    assert result.row_count == result.footer_rows == 32
    assert input_file.read_bytes() == original_bytes
    assert result.fields["id"]["distinct_nonnull"] == 32
    assert result.fields["job_title"]["null_count"] == 1
    assert result.fields["requirements"]["null_count"] == 1
    assert result.fields["requirements"]["blank_string_count"] == 2
    assert result.fields["education_level"]["null_count"] == 0
    assert result.fields["education_level"]["literal_sentinels"] == {"Không": 32}
    assert result.value_counts["salary"]["0 VND"] == 1
    assert result.value_counts["job_industry"]["Chưa xác định"] == 1
    assert len(result.duplicate_candidates) == 1
    assert [r.row_index for r in result.duplicate_candidates[0].members] == [0, 1]
    assert result.summary()["scope_policy"]["applied"] is False


def test_batch_size_does_not_change_counts_fingerprints_or_physical_identity(input_file):
    one = profile_history(input_file, batch_size=1)
    many = profile_history(input_file, batch_size=17)
    assert one.fields == many.fields
    assert one.duplicate_candidates == many.duplicate_candidates
    assert one.identity_examples == many.identity_examples
    assert one.value_counts == many.value_counts
    assert one.industry_year_counts == many.industry_year_counts
    assert one.identity_examples[1]["record_key"] == record_key(one.sha256, 1)


def test_signature_keeps_year_null_whitespace_and_unicode(synthetic_rows):
    base = synthetic_rows[0]
    assert content_fingerprint(base) == content_fingerprint({**base, "id": 999})
    for column, value in [
        ("year", 2024),
        ("requirements", None),
        ("requirements", ""),
        ("job_title", base["job_title"] + " "),
        ("company_name", "Công ty tổng hợp A"),
        ("salary", "0 VND"),
    ]:
        assert content_fingerprint(base) != content_fingerprint({**base, column: value})


def test_column_order_is_not_part_of_content_signature(tmp_path, synthetic_rows):
    path = write_parquet(tmp_path / "reordered.parquet", synthetic_rows, columns=COLUMNS[::-1])
    result = profile_history(path)
    assert result.passed
    assert result.duplicate_candidates[0].fingerprint == content_fingerprint(synthetic_rows[0])


def test_invalid_ids_years_and_expected_count_report_failure_without_removing_rows(
    tmp_path, synthetic_rows
):
    synthetic_rows[1]["id"] = 1
    synthetic_rows[2]["id"] = None
    synthetic_rows[3]["id"] = -1
    synthetic_rows[4]["year"] = None
    synthetic_rows[5]["year"] = 2027
    path = write_parquet(tmp_path / "invalid_values.parquet", synthetic_rows)
    result = profile_history(path, expected_rows=33)
    assert not result.passed
    assert result.row_count == 32
    assert result.invalid_id_count == result.invalid_year_count == 2
    assert result.duplicate_ids == {1: 2}
    assert len(result.validation_errors) == 4
    assert result.summary()["validation"]["passed"] is False


@pytest.mark.parametrize("mutation", ["missing", "extra", "float_id", "float_year"])
def test_schema_conflicts_are_rejected(tmp_path, synthetic_rows, mutation):
    schema = pa.schema(
        [(column, pa.int64() if column in {"id", "year"} else pa.string()) for column in COLUMNS]
    )
    table = pa.Table.from_pylist(synthetic_rows, schema=schema)
    if mutation == "missing":
        table = table.drop(["requirements"])
    elif mutation == "extra":
        table = table.append_column("source_url", pa.array(["synthetic"] * 32))
    else:
        column = mutation.removeprefix("float_")
        index = table.schema.get_field_index(column)
        table = table.set_column(index, column, table[column].cast(pa.float64()))
    path = tmp_path / "bad_schema.parquet"
    pq.write_table(table, path)
    with pytest.raises(HistoryProfileError):
        profile_history(path)


@pytest.mark.parametrize("batch_size", [0, -1])
def test_invalid_batch_sizes_rejected(input_file, batch_size):
    with pytest.raises(HistoryProfileError):
        profile_history(input_file, batch_size=batch_size)


def test_sha_mismatch_and_mid_read_change_are_rejected(input_file, monkeypatch):
    with pytest.raises(HistoryProfileError, match="SHA256"):
        profile_history(input_file, expected_sha256="0" * 64)
    digests = iter([file_sha256(input_file), "1" * 64])
    monkeypatch.setattr("job_warehouse.history.profile.file_sha256", lambda _: next(digests))
    with pytest.raises(HistoryProfileError, match="changed during"):
        profile_history(input_file)


def test_report_keeps_raw_json_values_and_never_overwrites_existing_report(input_file, tmp_path):
    result = profile_history(input_file)
    directory = tmp_path / "report"
    write_profile(result, directory)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    summary = json.loads((directory / "profile.json").read_text())
    assert summary["input"]["rows_decoded"] == 32
    assert summary["validation"]["passed"] is True
    with (directory / "scalar_value_counts.csv").open(newline="") as stream:
        values = list(csv.DictReader(stream))
    assert any(row["raw_value_json"] == '"Không"' for row in values)
    assert any(row["raw_value_json"] == '"0 VND"' for row in values)
    candidate = json.loads((directory / "duplicate_candidates.jsonl").read_text())
    assert candidate["members"] == [
        {"row_index": 0, "source_dataset_id": 1},
        {"row_index": 1, "source_dataset_id": 2},
    ]
    assert "requirements" not in candidate
    with pytest.raises(HistoryProfileError, match="already exists"):
        write_profile(result, directory)
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_cli_pinned_validation_and_existing_report_guard(input_file, tmp_path, capsys):
    report_dir = tmp_path / "cli_report"
    args = [
        "profile",
        "--input",
        str(input_file),
        "--report-dir",
        str(report_dir),
        "--expected-sha256",
        file_sha256(input_file),
        "--expected-rows",
        "32",
    ]
    assert main(args) == 0
    assert "validation=passed" in capsys.readouterr().out
    assert main(args) == 2
    assert "already exists" in capsys.readouterr().err
    args[-1] = "33"
    args[4] = str(tmp_path / "failed_report")
    assert main(args) == 2
    assert (
        json.loads((tmp_path / "failed_report" / "profile.json").read_text())["validation"][
            "passed"
        ]
        is False
    )


def test_cli_wrong_sha_or_corrupt_input_does_not_publish_report(input_file, tmp_path):
    report_dir = tmp_path / "not_created"
    args = ["profile", "--input", str(input_file), "--report-dir", str(report_dir)]
    assert main(args) == 2  # Defaults require the pinned source, not this fixture.
    assert not report_dir.exists()
    input_file.write_bytes(b"not parquet")
    assert main([*args, "--expected-sha256", file_sha256(input_file)]) == 2
    assert not report_dir.exists()


@pytest.mark.parametrize("hash_value,index", [("bad", 0), ("a" * 64, -1), ("A" * 64, 0)])
def test_invalid_physical_identity_inputs_rejected(hash_value, index):
    with pytest.raises(ValueError):
        record_key(hash_value, index)


def test_more_than_100_duplicate_groups_produce_bounded_deterministic_review_sample(tmp_path):
    rows = []
    for index in range(105):
        base = {column: "synthetic" for column in COLUMNS}
        base.update(id=index * 2 + 1, year=2025, job_title=f"Synthetic role {index}")
        rows.extend([base, {**base, "id": index * 2 + 2}])
    path = write_parquet(tmp_path / "many_groups.parquet", rows)
    result = profile_history(path)
    assert len(result.duplicate_candidates) == 105
    sample = result.summary()["content_duplicates"]["review_sample"]
    assert len(sample) == len({item["fingerprint"] for item in sample}) == 100
    assert (
        sample
        == profile_history(path, batch_size=2).summary()["content_duplicates"]["review_sample"]
    )
