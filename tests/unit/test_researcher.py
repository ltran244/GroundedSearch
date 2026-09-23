import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agents.researcher import run_research
from app.llm.client import AnswerGenerationError, QueryGenerationError
from app.search.brave import BraveSearchError
from app.web.fetcher import FetchError

JOB_ID = uuid4()
JOB = {
    "id": JOB_ID,
    "query": "Why is the sky blue?",
    "status": "running",
    "answer": None,
    "error_message": None,
}


def run_with_failure(failing_target: str, error: Exception):
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
        patch("app.db.sources.save_sources", return_value={"https://x/a": uuid4()}),
        patch("app.web.fetcher.fetch_pages", return_value={"https://x/a": "text"}),
        patch("app.db.sources.save_contents"),
        patch("app.llm.client.generate_answer", return_value="An answer [1]"),
        patch("app.db.research.complete_job"),
        patch("app.db.research.mark_job_failed") as mark_job_failed,
        patch(failing_target, side_effect=error),
    ):
        with pytest.raises(type(error)):
            asyncio.run(run_research(JOB_ID))
    return mark_job_failed


@pytest.mark.parametrize(
    ("target", "error", "message"),
    [
        (
            "app.llm.client.generate_search_query",
            QueryGenerationError("no queries"),
            "Search query generation failed",
        ),
        (
            "app.search.brave.search_all",
            BraveSearchError("brave down"),
            "Brave search failed",
        ),
        (
            "app.web.fetcher.fetch_pages",
            FetchError("nothing readable"),
            "No readable sources",
        ),
        (
            "app.llm.client.generate_answer",
            AnswerGenerationError("no answer"),
            "Answer generation failed",
        ),
        (
            "app.db.sources.save_sources",
            RuntimeError("something else"),
            "Unknown error",
        ),
    ],
)
def test_each_failing_step_records_its_own_message(target, error, message):
    mark_job_failed = run_with_failure(target, error)

    mark_job_failed.assert_awaited_once_with(JOB_ID, message)


def test_a_failure_to_record_the_failure_does_not_hide_the_original_error():
    # When the database is down, mark_job_failed cannot write either. The
    # caller must still see why the job actually failed.
    with (
        patch("app.db.research.mark_job_running"),
        patch("app.db.research.get_research", return_value=JOB),
        patch("app.llm.client.get_client"),
        patch(
            "app.llm.client.generate_search_query",
            side_effect=QueryGenerationError("no queries"),
        ),
        patch(
            "app.db.research.mark_job_failed",
            side_effect=RuntimeError("database unreachable"),
        ),
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
