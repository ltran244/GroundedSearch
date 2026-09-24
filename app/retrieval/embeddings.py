from google import genai
from google.genai import types

from app.config import settings

# The API rejects more than 100 texts in one request.
BATCH_LIMIT = 100


class EmbeddingError(RuntimeError):
    """Raised when the embedding model returns nothing usable."""


async def embed(client: genai.Client, texts: list[str]) -> list[list[float]]:
    """Turn each text into a vector, in the same order as `texts`."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_LIMIT):
        batch = texts[start : start + BATCH_LIMIT]
        try:
            response = await client.aio.models.embed_content(
                model=settings.embedding_model,
                contents=batch,  # pyright: ignore[reportArgumentType]
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.embedding_dimensions
                ),
            )
        except Exception as exc:
            raise EmbeddingError("Gemini embedding request failed") from exc
        returned = response.embeddings or []
        if len(returned) != len(batch):
            raise EmbeddingError(
                f"Asked for {len(batch)} embeddings, got {len(returned)}"
            )
        for embedding in returned:
            if not embedding.values:
                raise EmbeddingError("Embedding model returned an empty vector")
            vectors.append(list(embedding.values))
    return vectors
