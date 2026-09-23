import asyncio
from uuid import uuid4

import pytest
from psycopg_pool import AsyncConnectionPool

import app.db.pool as pool_module
import app.db.research as research_db
import app.db.sources as sources_db
from app.config import settings
from app.search.models import QueryResults, SearchResult

pytestmark = pytest.mark.integration


@pytest.fixture
def db(monkeypatch, clean_test_database):
    """Run an async test body against the test database.

    The pool belongs to whichever event loop opened it, so it is opened and
    closed inside the same asyncio.run as the body.
    """
    pool = AsyncConnectionPool(
        conninfo=settings.test_database_url, min_size=0, max_size=5, open=False
    )
    monkeypatch.setattr(pool_module, "pool", pool)

    def run(body):
        async def main():
            await pool.open()
            try:
                return await body()
            finally:
                await pool.close()

        return asyncio.run(main())

    return run


def results(*pairs: tuple[str, list[str]]) -> list[QueryResults]:
    """Search results as (query, [urls]); title and snippet echo the url."""
    return [
        QueryResults(
            query=query,
            results=[SearchResult(title=url, url=url, description=url) for url in urls],
        )
        for query, urls in pairs
    ]


def test_post_then_get_returns_a_pending_job(db):
    async def body():
        job_id = await research_db.post_research("question")
        return await research_db.get_research(job_id)

    job = db(body)

    assert job is not None
    assert job["query"] == "question"
    assert job["status"] == "pending"
    assert job["answer"] is None


def test_get_returns_none_for_an_unknown_job(db):
    assert db(lambda: research_db.get_research(uuid4())) is None


def test_queries_come_back_in_the_order_they_were_saved(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.save_queries(job_id, ["c", "a", "b"])
        return await research_db.get_queries(job_id)

    assert db(body) == ["c", "a", "b"]


def test_a_url_found_by_two_queries_is_stored_once(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.save_queries(job_id, ["a", "b"])
        source_ids = await sources_db.save_sources(
            job_id, results(("a", ["u1", "u2"]), ("b", ["u2"]))
        )
        return source_ids, await sources_db.get_sources(job_id)

    source_ids, sources = db(body)

    # One row per URL, and every URL maps to an id, including the duplicate.
    assert sorted(source_ids) == ["u1", "u2"]
    assert sorted(source["url"] for source in sources) == ["u1", "u2"]


def test_save_contents_numbers_sources_by_position(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.save_queries(job_id, ["a"])
        source_ids = await sources_db.save_sources(job_id, results(("a", ["u1", "u2"])))
        # u2 first, so it becomes [1] regardless of insertion order.
        await sources_db.save_contents(
            [(source_ids["u2"], "text two"), (source_ids["u1"], "text one")]
        )
        return await sources_db.get_sources(job_id)

    sources = db(body)

    assert [(source["number"], source["url"]) for source in sources] == [
        (1, "u2"),
        (2, "u1"),
    ]


def test_sources_without_content_come_last_without_a_number(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.save_queries(job_id, ["a"])
        source_ids = await sources_db.save_sources(job_id, results(("a", ["u1", "u2"])))
        await sources_db.save_contents([(source_ids["u2"], "text")])
        return await sources_db.get_sources(job_id)

    sources = db(body)

    assert [(source["number"], source["url"]) for source in sources] == [
        (1, "u2"),
        (None, "u1"),
    ]


def test_complete_job_saves_the_answer(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.complete_job(job_id, "answer [1]")
        return await research_db.get_research(job_id)

    job = db(body)

    assert job is not None
    assert job["status"] == "completed"
    assert job["answer"] == "answer [1]"


def test_mark_job_failed_records_the_message(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.mark_job_failed(job_id, "Brave search failed")
        return await research_db.get_research(job_id)

    job = db(body)

    assert job is not None
    assert job["status"] == "failed"
    assert job["error_message"] == "Brave search failed"
