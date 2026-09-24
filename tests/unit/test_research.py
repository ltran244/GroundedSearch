from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from app.main import app

URL = "https://a.test/"
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


def test_post_queues_the_job_and_returns_its_id(client):
    with (
        patch("app.db.research.post_research", return_value=JOB_ID),
        patch("app.queue.enqueue_research") as enqueue,
    ):
        response = client.post("/api/v1/research", json={"query": "question"})

    # POST hands the work to the worker; it never runs the pipeline itself.
    assert response.status_code == 201
    assert response.json() == {"id": str(JOB_ID), "status": "pending"}
    assert response.headers["Location"] == f"/api/v1/research/{JOB_ID}"
    enqueue.assert_awaited_once_with(JOB_ID)


def test_post_marks_the_job_failed_if_it_cannot_be_queued(client):
    # Otherwise the row sits at 'pending' forever: nothing will run it, and the
    # age-based cleanup only looks at jobs that started.
    with (
        patch("app.db.research.post_research", return_value=JOB_ID),
        patch("app.queue.enqueue_research", side_effect=ConnectionError("down")),
        patch("app.db.research.mark_job_failed") as mark_job_failed,
    ):
        response = client.post("/api/v1/research", json={"query": "question"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Job queue unavailable"}
    mark_job_failed.assert_awaited_once_with(JOB_ID, "Could not queue job")


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
