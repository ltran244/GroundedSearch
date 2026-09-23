from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.llm.models import GeneratedQueries
from app.main import app


@pytest.fixture
def client():
    # Not used as a context manager, so the lifespan never opens the real pool.
    return TestClient(app)


FAKE_URL = "https://example.com/a"
FAKE_SOURCE_ID = uuid4()
FAKE_TEXT = "Panels convert sunlight into electricity."
FAKE_ANSWER = "Solar panels convert sunlight into electricity. [1]"


@pytest.fixture
def generated_queries():
    """Stand in for every step of run_research that leaves the process.

    Any new external call in run_research needs a patch here too, or these
    tests will quietly spend API credits and hit the real database.
    """
    queries = GeneratedQueries(queries=["query one", "query two", "query three"])
    with (
        patch("app.llm.client.get_client"),
        patch("app.llm.client.generate_search_query", return_value=queries) as generate,
        patch("app.search.brave.search_all", return_value=[]),
        patch("app.db.sources.save_sources", return_value={FAKE_URL: FAKE_SOURCE_ID}),
        patch("app.web.fetcher.fetch_pages", return_value={FAKE_URL: FAKE_TEXT}),
        patch("app.db.sources.save_contents"),
        patch("app.llm.client.generate_answer", return_value=FAKE_ANSWER),
        patch("app.db.research.complete_job"),
        patch("app.db.research.mark_job_running"),
        patch("app.db.research.mark_job_failed"),
    ):
        yield generate


def test_post_research_creates_job_and_runs_pipeline(client, generated_queries):
    job_id = uuid4()
    job = {
        "id": job_id,
        "query": "How do solar panels work?",
        "status": "running",
        "answer": None,
        "error_message": None,
    }
    with (
        patch("app.db.research.post_research", return_value=job_id) as post_research,
        patch("app.db.research.get_research", return_value=job),
        patch("app.db.research.save_queries") as save_queries,
        patch("app.db.sources.save_contents") as save_contents,
        patch("app.db.research.complete_job") as complete_job,
    ):
        response = client.post(
            "/api/v1/research", json={"query": "How do solar panels work?"}
        )

    assert response.status_code == 200
    assert response.json() == {**job, "id": str(job_id)}
    post_research.assert_called_once_with("How do solar panels work?")
    save_queries.assert_awaited_once_with(
        job_id, ["query one", "query two", "query three"]
    )
    # The pipeline ran to the end: extracted text saved, answer stored.
    save_contents.assert_awaited_once_with({FAKE_SOURCE_ID: FAKE_TEXT})
    complete_job.assert_awaited_once_with(job_id, FAKE_ANSWER)


def test_post_research_requires_query(client, generated_queries):
    with patch("app.db.research.post_research") as post_research:
        response = client.post("/api/v1/research", json={})

    assert response.status_code == 422
    post_research.assert_not_called()


def test_post_research_database_unavailable(client, generated_queries):
    with patch("app.db.research.post_research", side_effect=OperationalError("down")):
        response = client.post("/api/v1/research", json={"query": "A question"})

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
        response = client.get(f"/api/v1/research/{job_id}")

    assert response.status_code == 200
    assert response.json() == {**job, "id": str(job_id)}
    get_research.assert_called_once_with(job_id)


def test_get_research_not_found(client):
    with patch("app.db.research.get_research", return_value=None):
        response = client.get(f"/api/v1/research/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found"}


def test_get_research_rejects_invalid_id(client):
    with patch("app.db.research.get_research") as get_research:
        response = client.get("/api/v1/research/not-a-uuid")

    assert response.status_code == 422
    get_research.assert_not_called()


def test_get_research_database_unavailable(client):
    with patch("app.db.research.get_research", side_effect=OperationalError("down")):
        response = client.get(f"/api/v1/research/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
