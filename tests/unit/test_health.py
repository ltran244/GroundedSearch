from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
from redis.exceptions import ConnectionError

from app.api.health import health_router


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(health_router)
    return TestClient(test_app)


def test_health_does_not_access_database(client):
    with (
        patch("app.api.health.check_database") as check_database,
        patch("app.api.health.check_queue") as check_queue,
    ):
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    check_database.assert_not_awaited()
    check_queue.assert_not_awaited()


def test_not_ready_when_the_database_is_unavailable(client):
    with patch("app.api.health.check_database", side_effect=PoolTimeout("unavailable")):
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_not_ready_when_the_queue_is_unavailable(client):
    # A job could be created that nothing would ever run.
    with (
        patch("app.api.health.check_database"),
        patch("app.api.health.check_queue", side_effect=ConnectionError("down")),
    ):
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Job queue unavailable"}
