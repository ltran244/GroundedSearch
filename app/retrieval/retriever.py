from uuid import UUID

from google import genai

import app.db.chunks as chunks_db
from app.retrieval import embeddings


async def retrieve(
    client: genai.Client, job_id: UUID, question: str, limit: int
) -> list[dict[str, object]]:
    """Find the passages of a job's sources closest to the question embedded."""
    query_embedding = (await embeddings.embed(client, [question]))[0]
    return await chunks_db.get_nearest_chunks(job_id, query_embedding, limit)
