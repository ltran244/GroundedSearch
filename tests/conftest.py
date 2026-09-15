import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg import connect, sql
from psycopg_pool import ConnectionPool

import app.api.health as health_module
import app.db.pool as pool_module
import app.main as main_module
from app.config import settings


def clear_test_database():
    with connect(settings.test_database_url, connect_timeout=3) as conn:
        row = conn.execute("SELECT current_database()").fetchone()
        if row != (settings.test_database_name,) or row == (settings.database_name,):
            raise RuntimeError(
                "Refusing to clean a database other than the test database"
            )
        conn.execute("SET LOCAL lock_timeout = '3s'")
        conn.execute("SET LOCAL statement_timeout = '10s'")
        tables = conn.execute(
            """
            SELECT n.nspname, c.relname
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p')
              AND NOT c.relispartition
              AND c.relname NOT IN (
                  '_yoyo_migration', '_yoyo_log', '_yoyo_version', 'yoyo_lock'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM pg_depend AS d
                  WHERE d.classid = 'pg_class'::regclass
                    AND d.objid = c.oid AND d.deptype = 'e'
              )
            """
        ).fetchall()
        if tables:
            # Truncate all application tables together to handle their foreign keys.
            conn.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(
                    sql.SQL(", ").join(
                        sql.Identifier(schema, name) for schema, name in tables
                    )
                )
            )


@pytest.fixture(scope="session")
def migrated_test_database():
    subprocess.run(
        [sys.executable, "-m", "app.db.migrate", "--test", "apply", "--batch"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )


@pytest.fixture
def clean_test_database(migrated_test_database):
    try:
        clear_test_database()
        yield
    finally:
        clear_test_database()


@pytest.fixture
def integration_pool(monkeypatch, clean_test_database):
    pool = ConnectionPool(
        conninfo=settings.test_database_url,
        min_size=0,
        max_size=10,
        open=False,
        kwargs={"connect_timeout": 3},
    )
    # Replace each imported reference with the same real, isolated test pool.
    monkeypatch.setattr(pool_module, "pool", pool)
    monkeypatch.setattr(main_module, "pool", pool)
    monkeypatch.setattr(health_module, "pool", pool)
    try:
        yield pool
    finally:
        pool.close()


@pytest.fixture
def integration_client(integration_pool):
    with TestClient(main_module.app) as client:
        assert not integration_pool.closed
        # Fail early if the configured test database cannot be reached.
        with integration_pool.connection(timeout=5) as conn:
            row = conn.execute("SELECT current_database()").fetchone()
            assert row == (settings.test_database_name,)
        yield client
    assert integration_pool.closed
