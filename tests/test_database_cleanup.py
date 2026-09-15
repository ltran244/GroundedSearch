from uuid import uuid4

import pytest
from conftest import clear_test_database
from psycopg import connect, sql

from app.config import settings

pytestmark = pytest.mark.integration


def test_cleanup_removes_committed_rows_and_resets_identity():
    parent = sql.Identifier("public", f"cleanup_parent_{uuid4().hex}")
    child = sql.Identifier("public", f"cleanup_child_{uuid4().hex}")
    with connect(settings.test_database_url, autocommit=True) as conn:
        try:
            conn.execute(
                sql.SQL(
                    "CREATE TABLE {} (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY)"
                ).format(parent)
            )
            conn.execute(
                sql.SQL("CREATE TABLE {} (parent_id bigint REFERENCES {} (id))").format(
                    child, parent
                )
            )
            conn.execute(sql.SQL("INSERT INTO {} DEFAULT VALUES").format(parent))
            conn.execute(sql.SQL("INSERT INTO {} VALUES (1)").format(child))
            metadata_tables = conn.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename IN (
                      '_yoyo_migration', '_yoyo_log', '_yoyo_version', 'yoyo_lock'
                  )
                """
            ).fetchall()
            metadata_before = {
                name: conn.execute(
                    sql.SQL("SELECT * FROM {} ORDER BY 1").format(
                        sql.Identifier("public", name)
                    )
                ).fetchall()
                for (name,) in metadata_tables
            }

            clear_test_database()

            for table in (parent, child):
                assert conn.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(table)
                ).fetchone() == (0,)
            assert conn.execute(
                sql.SQL("INSERT INTO {} DEFAULT VALUES RETURNING id").format(parent)
            ).fetchone() == (1,)
            for name, rows in metadata_before.items():
                assert (
                    conn.execute(
                        sql.SQL("SELECT * FROM {} ORDER BY 1").format(
                            sql.Identifier("public", name)
                        )
                    ).fetchall()
                    == rows
                )
        finally:
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(child))
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(parent))
