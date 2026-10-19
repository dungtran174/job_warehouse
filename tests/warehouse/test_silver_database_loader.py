"""Publication failures, replay and concurrent readers/writers on disposable PostgreSQL."""

import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import uuid4

import psycopg
import pyarrow.parquet as pq
import pytest
from psycopg.rows import dict_row
from silver_database_fixtures import frozen_runs, job

from job_warehouse.silver.database import loader
from job_warehouse.silver.database.commands import run_load
from job_warehouse.silver.database.migration import migrate_silver

pytestmark = pytest.mark.warehouse_db


@pytest.fixture
def load_conn(silver_test_database):
    with psycopg.connect(**silver_test_database, autocommit=True, row_factory=dict_row) as conn:
        migrate_silver(conn)
        conn.execute("DELETE FROM silver.job_skill_match")
        conn.execute("DELETE FROM silver.jobs")
        conn.execute("DELETE FROM ops.silver_load_run")
        yield conn


def load(conn, runs, **kwargs):
    return loader.load_silver(conn, *runs, allow_unpinned_fixture=True, **kwargs)


def state(conn):
    return [
        conn.execute(statement).fetchall()
        for statement in (
            "SELECT * FROM silver.jobs ORDER BY id",
            "SELECT * FROM silver.job_skill_match ORDER BY job_id,skill_code",
            "SELECT run_id,input_fingerprint FROM ops.silver_load_run WHERE is_current",
        )
    ]


def fresh_runs(tmp_path, name, **kwargs):
    p = tmp_path / name
    p.mkdir()
    return frozen_runs(p, **kwargs)


def test_exact_copy_roundtrip_and_noop_keeps_live_rows(load_conn, tmp_path):
    runs = frozen_runs(
        tmp_path,
        jobs=[
            job(
                company_name='Công ty "A", {B} \\ C 👩‍💻',
                salary_min=Decimal("0"),
                location=["Hà Nội", 'Nơi, có "dấu"', "\\N", "{a,b}"],
                requirements='Dòng 1\n\tDòng 2 \\N "Word"',
            ),
            job(id=2, requirements=None, job_type=None, education_level=None),
        ],
    )
    first = load(load_conn, runs, batch_size=1)
    assert first["status"] == "published"
    actual = state(load_conn)
    assert actual[0] == pq.read_table(runs[0] / "jobs_analysis.parquet").to_pylist()
    assert actual[1] == pq.read_table(runs[1] / "job_skill_match.parquet").to_pylist()
    before = load_conn.execute("SELECT id,xmin::text FROM silver.jobs ORDER BY id").fetchall()
    second = load(load_conn, runs, batch_size=2)
    assert second["status"] == "verified_noop"
    assert second["current_run_id"] == first["current_run_id"]
    assert second["run_id"] != first["run_id"]
    noop = load_conn.execute(
        "SELECT input_manifest FROM ops.silver_load_run WHERE run_id=%s", (second["run_id"],)
    ).fetchone()
    assert noop["input_manifest"]["current_run_id"] == first["current_run_id"]
    assert state(load_conn) == actual
    assert (
        load_conn.execute("SELECT id,xmin::text FROM silver.jobs ORDER BY id").fetchall() == before
    )
    assert load_conn.execute("SELECT count(*) AS n FROM ops.silver_load_run").fetchone()["n"] == 2
    assert load_conn.execute("SELECT to_regclass('pg_temp._s6_jobs') AS t").fetchone()["t"] is None


def test_equal_counts_cannot_hide_manual_content_drift(load_conn, tmp_path):
    runs = frozen_runs(tmp_path)
    first = load(load_conn, runs)
    load_conn.execute("UPDATE silver.jobs SET company_name='Manual change' WHERE id=1")
    result = load(load_conn, runs)
    assert result["status"] == "republished_after_content_drift"
    assert result["current_run_id"] != first["current_run_id"]
    assert state(load_conn)[0] == pq.read_table(runs[0] / "jobs_analysis.parquet").to_pylist()


@pytest.mark.parametrize(
    "event",
    [
        "after_jobs_copy",
        "after_stage",
        "after_delete",
        "after_jobs_insert",
        "before_commit",
    ],
)
def test_failure_preserves_both_tables_and_current_run(load_conn, tmp_path, monkeypatch, event):
    old = fresh_runs(tmp_path, "old")
    load(load_conn, old)
    expected = state(load_conn)
    new = fresh_runs(tmp_path, "new", jobs=[job(company_name="New"), job(id=2), job(id=3)])

    def crash(at, conn):
        if at == event:
            raise RuntimeError("Synthetic interruption")

    with monkeypatch.context() as patch:
        patch.setattr(loader, "_checkpoint", crash)
        with pytest.raises(RuntimeError, match="Synthetic"):
            load(load_conn, new)
    assert state(load_conn) == expected
    counts = load_conn.execute(
        "SELECT status,count(*) AS n FROM ops.silver_load_run GROUP BY status"
    ).fetchall()
    assert {r["status"]: r["n"] for r in counts} == {"published": 1, "failed": 1}
    assert load(load_conn, new)["status"] == "published"


def test_changed_input_after_copy_rolls_back(load_conn, tmp_path, monkeypatch):
    runs = frozen_runs(tmp_path)
    original = (runs[0] / "manifest.json").read_bytes()

    def changed(event, conn):
        if event == "after_jobs_copy":
            (runs[0] / "manifest.json").write_bytes(original + b" ")

    monkeypatch.setattr(loader, "_checkpoint", changed)
    with pytest.raises(ValueError, match="changed after preflight"):
        load(load_conn, runs)
    assert state(load_conn) == [[], [], []]
    assert (
        load_conn.execute("SELECT status FROM ops.silver_load_run").fetchone()["status"] == "failed"
    )


def test_bad_sha_before_attempt_has_no_database_mutation(load_conn, tmp_path):
    runs = frozen_runs(tmp_path)
    load(load_conn, runs)
    before = state(load_conn)
    (runs[1] / "job_skill_match.parquet").write_bytes(b"broken fixture")
    with pytest.raises(ValueError, match="SHA mismatch"):
        load(load_conn, runs)
    assert state(load_conn) == before
    assert load_conn.execute("SELECT count(*) AS n FROM ops.silver_load_run").fetchone()["n"] == 1


def test_reader_sees_previous_complete_version_until_commit(
    load_conn, silver_test_database, tmp_path, monkeypatch
):
    old = fresh_runs(tmp_path, "old")
    load(load_conn, old)
    before = state(load_conn)
    new = fresh_runs(tmp_path, "new", jobs=[job(company_name="New"), job(id=2), job(id=3)])
    observations = []

    def observe(event, conn):
        if event in {"after_delete", "after_jobs_insert", "before_commit"}:
            with psycopg.connect(
                **silver_test_database, autocommit=True, row_factory=dict_row
            ) as reader:
                observations.append(state(reader))

    monkeypatch.setattr(loader, "_checkpoint", observe)
    load(load_conn, new)
    assert len(observations) == 3 and all(s == before for s in observations)
    assert len(state(load_conn)[0]) == 3


def test_second_writer_rejected_until_first_finishes(
    load_conn, silver_test_database, tmp_path, monkeypatch
):
    runs = frozen_runs(tmp_path)
    waiting, release = Event(), Event()

    def pause(event, conn):
        if event == "after_stage":
            waiting.set()
            assert release.wait(10), "Test writer release timed out"

    def writer():
        with psycopg.connect(**silver_test_database, autocommit=True, row_factory=dict_row) as conn:
            return load(conn, runs)

    with monkeypatch.context() as patch, ThreadPoolExecutor(max_workers=1) as pool:
        patch.setattr(loader, "_checkpoint", pause)
        future = pool.submit(writer)
        try:
            assert waiting.wait(10), "Test writer did not reach staging"
            with pytest.raises(ValueError, match="Another Silver writer"):
                load(load_conn, runs)
            assert state(load_conn) == [[], [], []]
        finally:
            release.set()
        assert future.result(timeout=10)["status"] == "published"
    assert load(load_conn, runs)["status"] == "verified_noop"


def test_lost_connection_rolls_back_and_next_run_closes_abandoned_attempt(
    load_conn,
    silver_test_database,
    tmp_path,
    monkeypatch,
):
    old = fresh_runs(tmp_path, "old")
    load(load_conn, old)
    before = state(load_conn)
    new = fresh_runs(tmp_path, "new", jobs=[job(company_name="New"), job(id=2), job(id=3)])

    def disconnect(event, conn):
        if event == "after_jobs_insert":
            conn.close()
            raise RuntimeError("Disconnected")

    with monkeypatch.context() as patch:
        patch.setattr(loader, "_checkpoint", disconnect)
        with (
            psycopg.connect(
                **silver_test_database, autocommit=True, row_factory=dict_row
            ) as writer,
            pytest.raises((RuntimeError, psycopg.Error)),
        ):
            load(writer, new)
    assert state(load_conn) == before
    assert (
        load_conn.execute(
            "SELECT count(*) AS n FROM ops.silver_load_run WHERE status='running'"
        ).fetchone()["n"]
        == 1
    )
    assert load(load_conn, new)["status"] == "published"
    failed = load_conn.execute(
        "SELECT input_manifest FROM ops.silver_load_run WHERE status='failed'"
    ).fetchone()
    assert failed["input_manifest"]["failure_kind"] == "abandoned_session"


def test_error_after_commit_does_not_downgrade_published_ledger(load_conn, tmp_path, monkeypatch):
    runs = frozen_runs(tmp_path)
    ident = uuid4()

    def crash(event, conn):
        if event == "after_commit":
            raise RuntimeError("Lost response after commit")

    with monkeypatch.context() as patch:
        patch.setattr(loader, "_checkpoint", crash)
        with pytest.raises(RuntimeError, match="Lost response"):
            load(load_conn, runs, run_id=ident)
    row = load_conn.execute(
        "SELECT status,is_current FROM ops.silver_load_run WHERE run_id=%s", (ident,)
    ).fetchone()
    assert row == {"status": "published", "is_current": True}
    assert load(load_conn, runs)["status"] == "verified_noop"


def test_cli_report_failure_can_be_recovered_from_saved_run_id(
    load_conn,
    silver_test_database,
    tmp_path,
    monkeypatch,
):
    from job_warehouse.silver.database import commands

    runs = frozen_runs(tmp_path)
    actual_load = loader.load_silver

    def fixture_load(*args, **kwargs):
        return actual_load(*args, **kwargs, allow_unpinned_fixture=True)

    monkeypatch.setattr(loader, "load_silver", fixture_load)
    monkeypatch.setattr(
        commands,
        "connect_registry",
        lambda: psycopg.connect(**silver_test_database, autocommit=True, row_factory=dict_row),
    )
    write = Path.write_text

    def report_failure(path, text, *args, **kwargs):
        if path.name == "load.json":
            raise OSError("Synthetic disk error")
        return write(path, text, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_text", report_failure)
        with pytest.raises(ValueError, match="DB succeeded, local report failed"):
            run_load(*runs, tmp_path / "reports")
    request = json.loads((tmp_path / "reports/request.json").read_text())
    assert (
        load_conn.execute(
            "SELECT status FROM ops.silver_load_run WHERE run_id=%s", (request["run_id"],)
        ).fetchone()["status"]
        == "published"
    )
    run_load(*runs, tmp_path / "replay")
    assert json.loads((tmp_path / "replay/load.json").read_text())["status"] == "verified_noop"


def test_nested_transaction_rejected_and_no_attempt(load_conn, tmp_path):
    runs = frozen_runs(tmp_path)
    with load_conn.transaction(), pytest.raises(ValueError, match="idle autocommit"):
        load(load_conn, runs)
    assert state(load_conn) == [[], [], []]


def test_attempt_removed_during_staging_cannot_publish_without_journal(
    load_conn, tmp_path, monkeypatch
):
    old = fresh_runs(tmp_path, "old")
    load(load_conn, old)
    before = state(load_conn)
    new = fresh_runs(tmp_path, "new", jobs=[job(company_name="New"), job(id=2), job(id=3)])

    def remove(event, conn):
        if event == "after_stage":
            conn.execute("DELETE FROM ops.silver_load_run WHERE status='running'")

    monkeypatch.setattr(loader, "_checkpoint", remove)
    with pytest.raises(ValueError, match="no longer running"):
        load(load_conn, new)
    assert state(load_conn) == before


def test_changed_numeric_type_is_rejected_before_it_can_round(load_conn, tmp_path):
    runs = frozen_runs(tmp_path, jobs=[job(experience_min_years=Decimal("0.25")), job(id=2)])
    load_conn.execute("ALTER TABLE silver.jobs ALTER COLUMN experience_min_years TYPE numeric(6,1)")
    try:
        with pytest.raises(ValueError, match="schema drift"):
            load(load_conn, runs)
        assert state(load_conn) == [[], [], []]
    finally:
        load_conn.execute(
            "ALTER TABLE silver.jobs ALTER COLUMN experience_min_years TYPE numeric(6,2)"
        )
