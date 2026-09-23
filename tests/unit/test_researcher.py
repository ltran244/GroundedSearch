import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agents.researcher import run_research
from app.llm.client import AnswerGenerationError, QueryGenerationError
from app.search.brave import BraveSearchError
from app.web.fetcher import FetchError

JOB_ID = uuid4()
JOB = {"id": JOB_ID, "query": "question", "status": "running"}


def run_with_failure(target: str, error: Exception):
    """Run the pipeline with one step raising; return the mark_job_failed mock.

    Every step is patched, so nothing reaches Gemini, Brave, the web or the
    database. The one under test is given a side effect instead.
    """
    with (
        patch("app.db.research.mark_job_running"),
        patch("app.db.research.get_research", return_value=JOB),
        patch("app.llm.client.get_client"),
        patch("app.llm.client.generate_search_query"),
        patch("app.db.research.save_queries"),
        patch("app.search.brave.search_all", return_value=[]),
        patch("app.db.sources.save_sources", return_value={"u": uuid4()}),
        patch("app.web.fetcher.fetch_pages", return_value={"u": "text"}),
        patch("app.db.sources.save_contents"),
        patch("app.llm.client.generate_answer", return_value="answer"),
        patch("app.db.research.complete_job"),
        patch("app.db.research.mark_job_failed") as mark_job_failed,
        patch(target, side_effect=error),
    ):
        with pytest.raises(type(error)):
            asyncio.run(run_research(JOB_ID))
    return mark_job_failed


@pytest.mark.parametrize(
    ("target", "error", "message"),
    [
        (
            "app.llm.client.generate_search_query",
            QueryGenerationError(""),
            "Search query generation failed",
        ),
        ("app.search.brave.search_all", BraveSearchError(""), "Brave search failed"),
        ("app.web.fetcher.fetch_pages", FetchError(""), "No readable sources"),
        (
            "app.llm.client.generate_answer",
            AnswerGenerationError(""),
            "Answer generation failed",
        ),
        ("app.db.sources.save_sources", RuntimeError(""), "Unknown error"),
    ],
)
def test_each_failing_step_records_its_own_message(target, error, message):
    run_with_failure(target, error).assert_awaited_once_with(JOB_ID, message)


def test_a_failure_to_record_the_failure_keeps_the_original_error():
    # When the database is down, mark_job_failed cannot write either.
    with (
        patch("app.db.research.mark_job_running"),
        patch("app.db.research.get_research", return_value=JOB),
        patch("app.llm.client.get_client"),
        patch(
            "app.llm.client.generate_search_query", side_effect=QueryGenerationError("")
        ),
        patch("app.db.research.mark_job_failed", side_effect=RuntimeError("db down")),
    ):
        with pytest.raises(QueryGenerationError):
            asyncio.run(run_research(JOB_ID))


def test_a_deleted_job_stops_the_pipeline():
    with (
        patch("app.db.research.mark_job_running"),
        patch("app.db.research.get_research", return_value=None),
        patch("app.db.research.mark_job_failed") as mark_job_failed,
    ):
        with pytest.raises(RuntimeError):
            asyncio.run(run_research(JOB_ID))

    mark_job_failed.assert_awaited_once_with(JOB_ID, "Unknown error")
