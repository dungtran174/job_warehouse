"""Independent complete readback catches drift and preserves one read-only snapshot."""

from decimal import Decimal

import psycopg
import pytest
from psycopg.rows import dict_row
from silver_database_fixtures import frozen_runs, job

from job_warehouse.silver.database.loader import load_silver
from job_warehouse.silver.database.migration import migrate_silver
from job_warehouse.silver.database.verification import field_hashes, verify_publication


def test_hash_is_typed_and_never_rounds():
    assert field_hashes((Decimal("0.200000"),)) == field_hashes((Decimal("0.20"),))
    assert field_hashes((None,)) != field_hashes((0,))
    assert field_hashes((Decimal("1.00"),)) != field_hashes(("1.00",))
    assert field_hashes((["Hà Nội", "Huế"],)) != field_hashes((["Huế", "Hà Nội"],))
    with pytest.raises(ValueError, match="cannot round"):
        field_hashes((Decimal("0.083333"),))


@pytest.fixture
def verify_conn(silver_test_database):
    with psycopg.connect(**silver_test_database, autocommit=True, row_factory=dict_row) as conn:
        migrate_silver(conn)
        conn.execute("DELETE FROM silver.job_skill_match")
        conn.execute("DELETE FROM silver.jobs")
        conn.execute("DELETE FROM ops.silver_load_run")
        yield conn


def published(conn, tmp_path, **kwargs):
    runs = frozen_runs(tmp_path, **kwargs)
    load_silver(conn, *runs, allow_unpinned_fixture=True)
    return runs


def verify(conn, runs):
    return verify_publication(conn, *runs, allow_unpinned_fixture=True, batch_size=1)


@pytest.mark.warehouse_db
def test_readback_checks_all_fields_without_writing(verify_conn, tmp_path):
    pairs = [{"job_id": 1, "skill_code": c, "skill_name": c} for c in ["z", "a", "A", "é"]]
    runs = published(verify_conn, tmp_path, jobs=[job(id=10), job(id=2), job(id=1)], pairs=pairs)
    result = verify(verify_conn, runs)
    assert result["status"] == "passed_full_readback"
    assert result["read_only_repeatable_snapshot"]
    assert result["jobs"]["source_content_sha256"] == result["jobs"]["database_content_sha256"]
    assert result["skills"]["source_content_sha256"] == result["skills"]["database_content_sha256"]
    assert verify_conn.execute("SELECT count(*) AS n FROM ops.silver_load_run").fetchone()["n"] == 1


@pytest.mark.warehouse_db
@pytest.mark.parametrize(
    "statement,field",
    [
        ("UPDATE silver.jobs SET company_name='Changed' WHERE id=1", "company_name"),
        ("UPDATE silver.jobs SET location=ARRAY['Bình Dương','Hà Nội'] WHERE id=1", "location"),
        ("UPDATE silver.jobs SET salary_min=0 WHERE id=1", "salary_min"),
        ("UPDATE silver.jobs SET requirements='New text' WHERE id=1", "requirements"),
    ],
)
def test_equal_counts_do_not_hide_different_fields(verify_conn, tmp_path, statement, field):
    runs = published(verify_conn, tmp_path)
    verify_conn.execute(statement)
    result = verify(verify_conn, runs)
    assert result["status"] == "failed_full_readback"
    assert result["jobs"]["modified_rows"] == 1
    assert result["jobs"]["different_field_counts"] == {field: 1}


@pytest.mark.warehouse_db
def test_missing_and_extra_id_are_detected(verify_conn, tmp_path):
    runs = published(verify_conn, tmp_path)
    verify_conn.execute("DELETE FROM silver.jobs WHERE id=2")
    verify_conn.execute(
        "INSERT INTO silver.jobs(id,job_title,location,job_industry,year) "
        "VALUES(3,'Title',ARRAY['Hà Nội'],'Marketing',2026)"
    )
    result = verify(verify_conn, runs)
    assert result["jobs"]["source_rows"] == result["jobs"]["database_rows"]
    assert result["jobs"]["missing_rows"] == result["jobs"]["extra_rows"] == 1
    assert result["status"] == "failed_full_readback"


@pytest.mark.warehouse_db
def test_skill_name_drift_is_detected(verify_conn, tmp_path):
    runs = published(verify_conn, tmp_path)
    verify_conn.execute("UPDATE silver.job_skill_match SET skill_name='Changed'")
    result = verify(verify_conn, runs)
    assert result["status"] == "failed_full_readback"
    assert result["skills"]["different_field_counts"] == {"skill_name": 1}


@pytest.mark.warehouse_db
def test_missing_current_ledger_cannot_pass(verify_conn, tmp_path):
    runs = published(verify_conn, tmp_path)
    verify_conn.execute("UPDATE ops.silver_load_run SET is_current=false")
    result = verify(verify_conn, runs)
    assert result["jobs"]["matches"] and result["skills"]["matches"]
    assert not result["current_ledger_matches"]
    assert result["status"] == "failed_full_readback"


@pytest.mark.warehouse_db
def test_readback_stays_on_one_snapshot(verify_conn, silver_test_database, tmp_path, monkeypatch):
    from job_warehouse.silver.database import verification

    runs = published(verify_conn, tmp_path)
    compare = verification._compare

    def concurrent_change(conn, index, *, skills, batch_size):
        result = compare(conn, index, skills=skills, batch_size=batch_size)
        if not skills:
            with psycopg.connect(**silver_test_database, autocommit=True) as writer:
                writer.execute("UPDATE silver.job_skill_match SET skill_name='Concurrent change'")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(verification, "_compare", concurrent_change)
        assert verify(verify_conn, runs)["status"] == "passed_full_readback"
    assert verify(verify_conn, runs)["status"] == "failed_full_readback"
