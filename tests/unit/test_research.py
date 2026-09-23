from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.llm.models import GeneratedQueries
from app.main import app

URL = "https://a.test/"
SOURCE_ID = uuid4()
JOB_ID = uuid4()
JOB = {
    "id": JOB_ID,
    "query": "question",
    "status": "running",
    "answer": None,
    "error_message": None,
}


@pytest.fixture
def client():
    # Not a context manager, so the lifespan never opens the real pool.
    return TestClient(app)


@pytest.fixture
def pipeline():
    """Patch every step of run_research that leaves the process.

    Any new external call in run_research needs a patch here too, or these
    tests will quietly spend API credits and hit the real database.
    """
    with (
        patch("app.db.research.get_research", return_value=JOB),
        patch("app.llm.client.get_client"),
        patch(
            "app.llm.client.generate_search_query",
            return_value=GeneratedQueries(queries=["a", "b", "c"]),
        ),
        patch("app.search.brave.search_all", return_value=[]),
        patch("app.db.sources.save_sources", return_value={URL: SOURCE_ID}),
        patch("app.web.fetcher.fetch_pages", return_value={URL: "text"}),
        patch("app.llm.client.generate_answer", return_value="answer [1]"),
        patch("app.db.research.mark_job_running"),
        patch("app.db.research.mark_job_failed"),
    ):
        yield


def test_post_returns_the_job_id_immediately(client, pipeline):
    with (
        patch("app.db.research.post_research", return_value=JOB_ID),
        patch("app.db.research.save_queries"),
        patch("app.db.sources.save_contents") as save_contents,
        patch("app.db.research.complete_job") as complete_job,
    ):
        response = client.post("/api/v1/research", json={"query": "question"})

    assert response.status_code == 201
    assert response.json() == {"id": str(JOB_ID), "status": "pending"}
    assert response.headers["Location"] == f"/api/v1/research/{JOB_ID}"

    # TestClient runs background tasks before returning, so the pipeline has
    # already finished here. Against a real server it would still be running.
    save_contents.assert_awaited_once_with([(SOURCE_ID, "text")])
    complete_job.assert_awaited_once_with(JOB_ID, "answer [1]")


def test_post_rejects_a_missing_query(client, pipeline):
    with patch("app.db.research.post_research") as post_research:
        response = client.post("/api/v1/research", json={})

    assert response.status_code == 422
    post_research.assert_not_called()


def test_post_returns_503_when_the_database_is_down(client, pipeline):
    with patch("app.db.research.post_research", side_effect=OperationalError("down")):
        response = client.post("/api/v1/research", json={"query": "question"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_get_returns_the_job_with_its_queries_and_sources(client):
    source = {"number": 1, "title": "T", "url": URL, "snippet": "s"}
    with (
        patch("app.db.research.get_research", return_value=JOB),
        patch("app.db.research.get_queries", return_value=["a"]),
        patch("app.db.sources.get_sources", return_value=[source]),
    ):
        response = client.get(f"/api/v1/research/{JOB_ID}")

    assert response.status_code == 200
    # number is the [n] the answer cites this source by.
    assert response.json() == {
        **JOB,
        "id": str(JOB_ID),
        "search_queries": ["a"],
        "sources": [source],
    }


def test_get_returns_404_for_an_unknown_job(client):
    with patch("app.db.research.get_research", return_value=None):
        response = client.get(f"/api/v1/research/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research job not found"}


def test_get_rejects_an_invalid_id(client):
    with patch("app.db.research.get_research") as get_research:
        response = client.get("/api/v1/research/not-a-uuid")

    assert response.status_code == 422
    get_research.assert_not_called()


def test_get_returns_503_when_the_database_is_down(client):
    with patch("app.db.research.get_research", side_effect=OperationalError("down")):
        response = client.get(f"/api/v1/research/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
