from uuid import UUID

import app.db.research as research_db
import app.db.sources as sources_db
import app.llm.client as llm_client
from app.search import brave
from app.web import fetcher


async def run_research(job_id: UUID) -> None:
    """Run the research pipeline for one job.

    Takes only a job id, reads what it needs from the database, and writes each
    step's result back. It knows nothing about HTTP, so it can also be called
    from a worker, a retry, or an evaluation run.
    """
    await research_db.mark_job_running(job_id)
    try:
        job = await research_db.get_research(job_id)
        if job is None:
            raise RuntimeError(f"Research job {job_id} no longer exists")

        generated = await llm_client.generate_search_query(
            llm_client.get_client(), str(job["query"])
        )
        queries = generated.queries
        await research_db.save_queries(job_id, queries)

        results = await brave.search_all(queries)
        source_ids = await sources_db.save_sources(job_id, results)
        pages = await fetcher.fetch_pages(list(source_ids))
        await sources_db.save_contents(
            {source_ids[url]: text for url, text in pages.items()}
        )
        answer = await llm_client.generate_answer(
            llm_client.get_client(), str(job["query"]), list(pages.values())
        )
        await research_db.complete_job(job_id, answer)
    except Exception as exc:
        if isinstance(exc, llm_client.QueryGenerationError):
            message = "Search query generation failed"
        elif isinstance(exc, brave.BraveSearchError):
            message = "Brave search failed"
        elif isinstance(exc, fetcher.FetchError):
            message = "No readable sources"
        elif isinstance(exc, llm_client.AnswerGenerationError):
            message = "Answer generation failed"
        else:
            message = "Unknown error"
        try:
            await research_db.mark_job_failed(job_id, message)
        except Exception:
            pass
        raise
