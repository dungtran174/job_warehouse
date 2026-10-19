"""Real PostgreSQL migration checks, confined to a random disposable database."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from job_warehouse.bronze.database import connection_settings
from job_warehouse.bronze.registry import migrate_registry
from job_warehouse.history.contract import HistoryProfileError
from job_warehouse.silver.database.migration import migrate_silver

pytestmark = pytest.mark.warehouse_db


@pytest.fixture(scope="module")
def silver_test_database():
    if not os.environ.get("WAREHOUSE_TEST_DB_HOST"):
        pytest.skip("Set WAREHOUSE_TEST_DB_HOST for isolated PostgreSQL tests")
    settings = connection_settings(
        {
            f"WAREHOUSE_DB_{name}": os.environ[f"WAREHOUSE_TEST_DB_{name}"]
            for name in ["HOST", "PORT", "NAME", "USER", "PASSWORD", "PASSWORD_FILE"]
            if f"WAREHOUSE_TEST_DB_{name}" in os.environ
        }
    )
    name = f"silver_test_{uuid4().hex}"
    with psycopg.connect(**settings, autocommit=True, row_factory=dict_row) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            yield {**settings, "dbname": name}
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def silver_conn(silver_test_database):
    with psycopg.connect(**silver_test_database, autocommit=True, row_factory=dict_row) as conn:
        migrate_registry(conn)
        conn.execute("DROP SCHEMA IF EXISTS silver CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS ops CASCADE")
        conn.execute("DELETE FROM warehouse_meta.schema_migration WHERE version='002_silver'")
        yield conn


def test_migration_repeatable_preserves_bronze_and_schema(silver_conn):
    assert migrate_silver(silver_conn) is True
    assert migrate_silver(silver_conn) is False
    assert migrate_registry(silver_conn) is False
    columns = silver_conn.execute(
        "SELECT column_name, data_type, numeric_precision, numeric_scale "
        "FROM information_schema.columns WHERE table_schema='silver' "
        "AND table_name='jobs' ORDER BY ordinal_position"
    ).fetchall()
    assert len(columns) == 14
    assert (
        next(c for c in columns if c["column_name"] == "job_type")["data_type"]
        == "character varying"
    )
    experience = next(c for c in columns if c["column_name"] == "experience_min_years")
    assert (experience["numeric_precision"], experience["numeric_scale"]) == (6, 2)
    assert silver_conn.execute("SELECT count(*) AS n FROM silver.jobs").fetchone()["n"] == 0
    assert silver_conn.execute("SELECT count(*) AS n FROM ops.silver_load_run").fetchone()["n"] == 0


def test_checksum_rejected(silver_conn):
    migrate_silver(silver_conn)
    silver_conn.execute(
        "UPDATE warehouse_meta.schema_migration SET sha256=%s WHERE version='002_silver'",
        ("0" * 64,),
    )
    with pytest.raises(HistoryProfileError, match="checksum"):
        migrate_silver(silver_conn)


def test_ddl_failure_rolls_back(silver_conn, monkeypatch):
    monkeypatch.setattr(
        "job_warehouse.silver.database.migration.migration_text",
        lambda: "CREATE SCHEMA silver; CREATE TABLE silver.partial(id int); INVALID;",
    )
    with pytest.raises(psycopg.ProgrammingError):
        migrate_silver(silver_conn)
    assert silver_conn.execute("SELECT to_regnamespace('silver') AS s").fetchone()["s"] is None
    assert (
        silver_conn.execute(
            "SELECT count(*) AS n FROM warehouse_meta.schema_migration WHERE version='002_silver'"
        ).fetchone()["n"]
        == 0
    )
    assert migrate_registry(silver_conn) is False


def test_parallel_migration_serialized(silver_conn, silver_test_database):
    def migrate(_):
        with psycopg.connect(**silver_test_database, autocommit=True, row_factory=dict_row) as conn:
            return migrate_silver(conn)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(migrate, range(2))) == [False, True]


@pytest.mark.parametrize(
    "columns,values",
    [
        ("id,job_title,location,job_industry,year", (1, None, ["Hà Nội"], "Marketing", 2026)),
        ("id,job_title,location,job_industry,year", (1, "Title", [], "Marketing", 2026)),
        ("id,job_title,location,job_industry,year", (1, "Title", [None], "Marketing", 2026)),
        ("id,job_title,location,job_industry,year", (1, "Title", ["Hà Nội"], "Marketing", 2030)),
        (
            "id,job_title,location,job_industry,year,salary_min,salary_max",
            (1, "Title", ["Hà Nội"], "Marketing", 2026, 200, 100),
        ),
        (
            "id,job_title,location,job_industry,year,experience_min_years",
            (1, "Title", ["Hà Nội"], "Marketing", 2026, -1),
        ),
    ],
)
def test_job_constraints(silver_conn, columns, values):
    migrate_silver(silver_conn)
    statement = sql.SQL("INSERT INTO silver.jobs ({}) VALUES ({})").format(
        sql.SQL(",").join(map(sql.Identifier, columns.split(","))),
        sql.SQL(",").join(sql.Placeholder() for _ in values),
    )
    with pytest.raises(psycopg.IntegrityError), silver_conn.transaction():
        silver_conn.execute(statement, values)


def test_pk_fk_and_nullable_one_sided_bounds(silver_conn):
    migrate_silver(silver_conn)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        silver_conn.execute("INSERT INTO silver.job_skill_match VALUES (1,'excel','Excel')")
    silver_conn.execute(
        "INSERT INTO silver.jobs(id,job_title,location,job_type,job_industry,year,"
        "salary_max,experience_min_years) VALUES "
        "(1,'Tiếng Việt 👩‍💻',%s,'Remote','Marketing',2026,20000000,0.2)",
        (["Hà Nội", "Bình Dương"],),
    )
    silver_conn.execute("INSERT INTO silver.job_skill_match VALUES (1,'excel','Excel')")
    with pytest.raises(psycopg.errors.UniqueViolation):
        silver_conn.execute("INSERT INTO silver.job_skill_match VALUES (1,'excel','Excel')")
    row = silver_conn.execute("SELECT * FROM silver.jobs").fetchone()
    assert row["location"] == ["Hà Nội", "Bình Dương"]
    assert row["salary_min"] is None and row["experience_max_years"] is None
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        silver_conn.execute("DELETE FROM silver.jobs")


def insert_run(conn, *, current=False, status="published"):
    conn.execute(
        "INSERT INTO ops.silver_load_run (run_id,input_fingerprint,input_manifest,"
        "loader_version,status,expected_counts,actual_counts,finished_at,is_current) "
        "VALUES (%s,%s,%s,'fixture',%s,%s,%s,CURRENT_TIMESTAMP,%s)",
        (uuid4(), "a" * 64, Jsonb({}), status, Jsonb({}), Jsonb({}), current),
    )


def test_current_run_unique_but_repeated_fingerprint_allowed(silver_conn):
    migrate_silver(silver_conn)
    insert_run(silver_conn)
    insert_run(silver_conn)
    insert_run(silver_conn, current=True)
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_run(silver_conn, current=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_run(silver_conn, current=True, status="failed")
    assert silver_conn.execute("SELECT count(*) AS n FROM ops.silver_load_run").fetchone()["n"] == 3
