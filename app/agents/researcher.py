from uuid import UUID

import app.db.research as research_db
import app.llm.client as llm_client


def run_research(job_id: UUID) -> None:
    """Run the research pipeline for one job.

    Takes only a job id, reads what it needs from the database, and writes each
    step's result back. It knows nothing about HTTP, so it can also be called
    from a worker, a retry, or an evaluation run.
    """
    research_db.mark_job_running(job_id)
    try:
        job = research_db.get_research(job_id)
        if job is None:
            raise RuntimeError(f"Research job {job_id} no longer exists")

        queries = llm_client.generate_search_query(
            llm_client.get_client(), str(job["query"])
        ).queries
        research_db.save_queries(job_id, queries)
    except Exception as exc:
        if isinstance(exc, llm_client.QueryGenerationError):
            message = "Search query generation failed"
        else:
            message = "Could not save generated queries"
        try:
            research_db.mark_job_failed(job_id, message)
        except Exception:
            # Recording the failure must not replace the original error.
            pass
        raise
