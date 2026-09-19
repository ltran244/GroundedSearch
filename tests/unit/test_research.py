from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.main import app


@pytest.fixture
def client():
    # Not used as a context manager, so the lifespan never opens the real pool.
    return TestClient(app)


def test_post_research_creates_pending_job(client):
    job_id = uuid4()
    with patch("app.db.research.post_research", return_value=job_id) as post_research:
        response = client.post("/research", json={"query": "How do solar panels work?"})

    assert response.status_code == 200
    assert response.json() == {
        "id": str(job_id),
        "query": "How do solar panels work?",
        "status": "pending",
        "answer": None,
        "error_message": None,
    }
    post_research.assert_called_once_with("How do solar panels work?")


def test_post_research_requires_query(client):
    with patch("app.db.research.post_research") as post_research:
        response = client.post("/research", json={})

    assert response.status_code == 422
    post_research.assert_not_called()


def test_post_research_database_unavailable(client):
    with patch("app.db.research.post_research", side_effect=OperationalError("down")):
        response = client.post("/research", json={"query": "A question"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_get_research_returns_job(client):
    job_id = uuid4()
    job = {
        "id": job_id,
        "query": "How do solar panels work?",
        "status": "pending",
        "answer": None,
        "error_message": None,
    }
    with patch("app.db.research.get_research", return_value=job) as get_research:
        response = client.get("/research", params={"job_id": str(job_id)})

    assert response.status_code == 200
    assert response.json() == {**job, "id": str(job_id)}
    get_research.assert_called_once_with(job_id)


def test_get_research_not_found(client):
    with patch("app.db.research.get_research", return_value=None):
        response = client.get("/research", params={"job_id": str(uuid4())})

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found"}


def test_get_research_rejects_invalid_id(client):
    with patch("app.db.research.get_research") as get_research:
        response = client.get("/research", params={"job_id": "not-a-uuid"})

    assert response.status_code == 422
    get_research.assert_not_called()


def test_get_research_database_unavailable(client):
    with patch("app.db.research.get_research", side_effect=OperationalError("down")):
        response = client.get("/research", params={"job_id": str(uuid4())})

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
