import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

import app.api.health as health_module
import app.db.pool as pool_module
import app.main as main_module
from app.config import settings


@pytest.fixture
def integration_pool(monkeypatch):
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
