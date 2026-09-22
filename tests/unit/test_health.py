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
    with patch("app.api.health.check_database") as check_database:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    check_database.assert_not_awaited()


def test_ready_when_database_responds(client):
    with patch("app.api.health.check_database"):
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_when_database_is_unavailable(client):
    with patch("app.api.health.check_database", side_effect=PoolTimeout("unavailable")):
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
