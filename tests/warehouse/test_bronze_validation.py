"""File gates, secret-safe configuration and CLI failure reports."""

# ruff: noqa: E402
import json
from contextlib import contextmanager

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")
psycopg = pytest.importorskip("psycopg")

from job_warehouse.bronze.database import connection_settings
from job_warehouse.bronze.validation import resolve_input, validate_artifact
from job_warehouse.cli import main
from job_warehouse.history.contract import HistoryProfileError
from job_warehouse.history.identity import file_sha256


def test_validate_decodes_all_rows_and_preserves_null_text_and_bytes(bronze_file):
    before = bronze_file.read_bytes()
    for batch_size in [1, 13, 100]:
        artifact = validate_artifact(
            bronze_file.parent,
            bronze_file.name,
            expected_sha256=file_sha256(bronze_file),
            expected_rows=32,
            batch_size=batch_size,
        )
        assert artifact.row_count == 32
        assert artifact.byte_size == len(before)
        assert artifact.relative_path == "history_data.parquet"
        assert len(artifact.schema_json["columns"]) == 14
    assert bronze_file.read_bytes() == before


@pytest.mark.parametrize("relative", ["", "../history_data.parquet", "/tmp/file.parquet"])
def test_input_rejects_absolute_or_traversal_paths(bronze_file, relative):
    with pytest.raises(HistoryProfileError):
        resolve_input(bronze_file.parent, relative)


def test_symlink_cannot_escape_input_root(bronze_file, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "file.parquet").symlink_to(bronze_file)
    with pytest.raises(HistoryProfileError, match="inside input root"):
        resolve_input(root, "file.parquet")


@pytest.mark.parametrize("mutation", ["null_id", "duplicate_id", "negative_id", "year", "schema"])
def test_bad_schema_or_values_are_rejected(bronze_file, mutation):
    table = pq.read_table(bronze_file)
    if mutation == "schema":
        table = table.drop(["benefits"])
    else:
        column = "year" if mutation == "year" else "id"
        values = table[column].to_pylist()
        values[0] = {"null_id": None, "duplicate_id": 2, "negative_id": -1, "year": 2030}[mutation]
        index = table.schema.get_field_index(column)
        table = table.set_column(index, column, pa.array(values, type=pa.int64()))
    pq.write_table(table, bronze_file)
    with pytest.raises(HistoryProfileError):
        validate_artifact(
            bronze_file.parent,
            bronze_file.name,
            expected_sha256=file_sha256(bronze_file),
            expected_rows=32,
        )


def test_bad_hash_count_and_mid_read_change_rejected(bronze_file, monkeypatch):
    actual = file_sha256(bronze_file)
    with pytest.raises(HistoryProfileError, match="SHA256"):
        validate_artifact(bronze_file.parent, bronze_file.name)
    with pytest.raises(HistoryProfileError, match="row count"):
        validate_artifact(bronze_file.parent, bronze_file.name, expected_sha256=actual)
    digests = iter([actual, "a" * 64])
    monkeypatch.setattr("job_warehouse.bronze.validation.file_sha256", lambda _: next(digests))
    with pytest.raises(HistoryProfileError, match="changed during"):
        validate_artifact(
            bronze_file.parent, bronze_file.name, expected_sha256=actual, expected_rows=32
        )


def test_credentials_require_explicit_settings_and_support_secret_file(tmp_path):
    password_file = tmp_path / "password"
    password_file.write_text("synthetic-secret\n")
    env = {
        "WAREHOUSE_DB_HOST": "localhost",
        "WAREHOUSE_DB_USER": "test",
        "WAREHOUSE_DB_NAME": "fixture",
        "WAREHOUSE_DB_PASSWORD_FILE": str(password_file),
    }
    assert connection_settings(env)["password"] == "synthetic-secret"
    assert connection_settings(env)["port"] == 5432
    for change in [
        {"WAREHOUSE_DB_HOST": ""},
        {"WAREHOUSE_DB_PORT": "bad"},
        {"WAREHOUSE_DB_PORT": "65536"},
        {"WAREHOUSE_DB_PASSWORD": "other"},
        {"WAREHOUSE_DB_PASSWORD_FILE": str(tmp_path / "missing")},
        {"WAREHOUSE_DB_PASSWORD_FILE": ""},
    ]:
        with pytest.raises(HistoryProfileError):
            connection_settings({**env, **change})


def test_cli_rejects_unpinned_fixture_before_connecting_and_preserves_old_report(
    bronze_file,
    tmp_path,
    monkeypatch,
):
    def unexpected_connection():
        raise AssertionError("Invalid input must not reach PostgreSQL")

    monkeypatch.setattr("job_warehouse.bronze.commands.connect_registry", unexpected_connection)
    directory = tmp_path / "failed_run"
    args = [
        "bronze",
        "register",
        "--input-root",
        str(bronze_file.parent),
        "--report-dir",
        str(directory),
    ]
    assert main(args) == 2
    report_file = directory / "run.json"
    before = report_file.read_bytes()
    report = json.loads(before)
    assert report["status"] == "failed"
    assert report["run_id"]
    assert "registration" not in report
    assert main(args) == 2
    assert report_file.read_bytes() == before


def test_cli_database_errors_hide_libpq_parameters(tmp_path, monkeypatch, capsys):
    @contextmanager
    def failing_connection():
        raise psycopg.OperationalError("password=DO_NOT_EXPOSE")
        yield  # pragma: no cover

    monkeypatch.setattr("job_warehouse.bronze.commands.connect_registry", failing_connection)
    directory = tmp_path / "database_failure"
    assert main(["bronze", "migrate", "--report-dir", str(directory)]) == 2
    outputs = capsys.readouterr()
    text = outputs.out + outputs.err + (directory / "run.json").read_text()
    assert "DO_NOT_EXPOSE" not in text
    assert "OperationalError" in text
    assert json.loads((directory / "run.json").read_text())["status"] == "failed"


def test_cli_corrupt_parquet_records_failure_without_connecting(tmp_path, monkeypatch):
    def corrupt(*args, **kwargs):
        raise pa.ArrowInvalid("synthetic invalid Parquet")

    monkeypatch.setattr("job_warehouse.bronze.commands.validate_artifact", corrupt)
    directory = tmp_path / "corrupt_run"
    assert (
        main(["bronze", "register", "--input-root", str(tmp_path), "--report-dir", str(directory)])
        == 2
    )
    report = json.loads((directory / "run.json").read_text())
    assert report["status"] == "failed"
    assert "ArrowInvalid" in report["error"]
    assert "registration" not in report
