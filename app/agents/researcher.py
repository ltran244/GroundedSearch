from uuid import UUID

import app.db.chunks as chunks_db
import app.db.research as research_db
import app.db.sources as sources_db
import app.llm.client as llm_client
from app.config import settings
from app.llm.models import AnswerSource
from app.retrieval import chunker, embeddings, reranker, retriever
from app.search import brave
from app.web import fetcher


async def run_research(job_id: UUID) -> None:
    """Run the research pipeline for one job."""
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

        titles: dict[str, str] = {}
        for group in results:
            for result in group.results:
                titles.setdefault(result.url, result.title)

        await sources_db.save_contents(
            [(source_ids[url], text) for url, text in pages.items()]
        )

        chunks = [
            (source_ids[url], index, passage)
            for url, text in pages.items()
            for index, passage in enumerate(chunker.chunk(text))
        ]
        vectors = await embeddings.embed(
            llm_client.get_client(), [passage for _, _, passage in chunks]
        )
        await chunks_db.save_chunks(
            [
                (source_id, index, passage, vector)
                # strict: a mismatch means a passage lost its embedding.
                for (source_id, index, passage), vector in zip(
                    chunks, vectors, strict=True
                )
            ]
        )

        # retrieve candidate chunks
        candidates = await retriever.retrieve(
            llm_client.get_client(),
            job_id,
            str(job["query"]),
            settings.retrieval_candidates,
        )
        # pick which chunks to actually use to include evidence from diff sources
        selected = reranker.spread_across_sources(
            candidates,
            settings.retrieval_chunks,
            settings.retrieval_chunks_per_source,
        )

        # group so each source has its passages together
        passages: dict[UUID, list[str]] = {}
        for chunk in selected:
            passages.setdefault(UUID(str(chunk["source_id"])), []).append(
                str(chunk["content"])
            )

        urls = {source_id: url for url, source_id in source_ids.items()}
        evidence = [
            AnswerSource(
                title=titles.get(urls[source_id], ""),
                url=urls[source_id],
                text="\n\n".join(texts),
            )
            for source_id, texts in passages.items()
        ]
        await sources_db.set_citation_numbers(list(passages))

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
        elif isinstance(exc, embeddings.EmbeddingError):
            message = "Embedding failed"
        elif isinstance(exc, llm_client.AnswerGenerationError):
            message = "Answer generation failed"
        else:
            message = "Unknown error"
        try:
            await research_db.mark_job_failed(job_id, message)
        except Exception:
            pass
        raise
