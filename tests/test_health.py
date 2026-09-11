from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from app.api.health import health_router


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(health_router)
    return TestClient(test_app)


def test_health_does_not_access_database(client):
    with patch("app.api.health.pool") as pool:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    pool.connection.assert_not_called()


def test_ready_when_database_responds(client):
    with patch("app.api.health.pool"):
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_when_database_is_unavailable(client):
    with patch("app.api.health.pool") as pool:
        pool.connection.side_effect = PoolTimeout("unavailable")
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}