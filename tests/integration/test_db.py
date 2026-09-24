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


def test_citation_numbers_follow_the_order_they_are_given(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.save_queries(job_id, ["a"])
        ids = await sources_db.save_sources(job_id, results(("a", ["u1", "u2"])))
        await sources_db.save_contents([(ids["u1"], "one"), (ids["u2"], "two")])
        # u2 first, so it becomes [1] whatever order the rows were inserted in.
        await sources_db.set_citation_numbers([ids["u2"], ids["u1"]])
        return await sources_db.get_sources(job_id)

    sources = db(body)

    assert [(s["number"], s["url"]) for s in sources] == [(1, "u2"), (2, "u1")]


def test_sources_left_out_of_the_answer_have_no_number(db):
    async def body():
        job_id = await research_db.post_research("question")
        await research_db.save_queries(job_id, ["a"])
        ids = await sources_db.save_sources(job_id, results(("a", ["u1", "u2"])))
        await sources_db.save_contents([(ids["u1"], "one"), (ids["u2"], "two")])
        await sources_db.set_citation_numbers([ids["u2"]])
        return await sources_db.get_sources(job_id)

    sources = db(body)

    assert [(s["number"], s["url"]) for s in sources] == [(1, "u2"), (None, "u1")]


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


def test_fail_stale_jobs_only_touches_jobs_that_stopped_making_progress(db):
    async def body():
        stranded = await research_db.post_research("stranded")
        fresh = await research_db.post_research("fresh")
        await research_db.mark_job_running(stranded)
        await research_db.mark_job_running(fresh)
        async with pool_module.pool.connection() as conn:
            await conn.execute(
                "UPDATE research_jobs SET started_at = now() - interval '1 day' "
                "WHERE id = %s",
                (stranded,),
            )
        swept = await research_db.fail_stale_jobs()
        return (
            swept,
            await research_db.get_research(stranded),
            await research_db.get_research(fresh),
        )

    swept, stranded, fresh = db(body)

    assert swept == 1
    assert stranded is not None and stranded["status"] == "failed"
    assert stranded["error_message"] == "Timed out"
    assert fresh is not None and fresh["status"] == "running"
