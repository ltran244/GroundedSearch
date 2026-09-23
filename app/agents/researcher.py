from uuid import UUID

import app.db.research as research_db
import app.db.sources as sources_db
import app.llm.client as llm_client
from app.llm.models import AnswerSource
from app.search import brave
from app.web import fetcher


async def run_research(job_id: UUID) -> None:
    """Run the research pipeline for one job.
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

        # Titles come from the search results; the first query to find a URL
        # wins, matching how save_sources dedupes.
        titles: dict[str, str] = {}
        for group in results:
            for result in group.results:
                titles.setdefault(result.url, result.title)

        # One ordered list decides both the [n] the model is given and the
        # citation_number stored on each row, so the two cannot disagree.
        evidence = [
            AnswerSource(title=titles.get(url, ""), url=url, text=text)
            for url, text in pages.items()
        ]
        await sources_db.save_contents(
            [(source_ids[source.url], source.text) for source in evidence]
        )

        answer = await llm_client.generate_answer(
            llm_client.get_client(), str(job["query"]), evidence
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
