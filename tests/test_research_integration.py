from uuid import UUID, uuid4

import pytest
from psycopg import connect

from app.config import settings

pytestmark = pytest.mark.integration


def test_create_and_fetch_research_job(integration_client):
    response = integration_client.post(
        "/api/v1/research", json={"query": "  How do solar panels work?  "}
    )
    assert response.status_code == 201
    job = response.json()
    job_id = UUID(job["id"])
    assert job["query"] == "How do solar panels work?"
    assert job["status"] == "pending"
    assert job["answer"] is None
    assert job["error_message"] is None
    assert job["completed_at"] is None
    assert job["created_at"]

    with connect(settings.test_database_url) as conn:
        assert conn.execute(
            "SELECT query FROM research_jobs WHERE id = %s", (job_id,)
        ).fetchone() == (job["query"],)

    response = integration_client.get(f"/api/v1/research/{job_id}")
    assert response.status_code == 200
    assert response.json() == job


@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": " \n\t "}])
def test_reject_empty_question(integration_client, payload):
    response = integration_client.post("/api/v1/research", json=payload)
    assert response.status_code == 422


def test_missing_job(integration_client):
    response = integration_client.get(f"/api/v1/research/{uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found"}


def test_invalid_job_id(integration_client):
    response = integration_client.get("/api/v1/research/not-a-uuid")
    assert response.status_code == 422


def test_database_unavailable(integration_client, integration_pool):
    integration_pool.close()
    responses = [
        integration_client.post("/api/v1/research", json={"query": "A question"}),
        integration_client.get(f"/api/v1/research/{uuid4()}"),
    ]
    for response in responses:
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
