from anyio import CapacityLimiter
from google import genai
from google.genai import types

from app.config import settings
from app.llm.models import SearchQueries
from app.llm.prompts import QUERY_GENERATION_PROMPT

_limiter = CapacityLimiter(settings.llm_max_concurrent_requests)


class QueryGenerationError(Exception):
    """The provider failed or returned unusable search queries."""


def get_client() -> genai.Client:
    """Create a Gemini client; the caller must close it after use."""
    if not settings.google_api_key or not settings.google_api_key.get_secret_value():
        raise ValueError("Set GOOGLE_API_KEY in .env before using the Google API")
    return genai.Client(
        api_key=settings.google_api_key.get_secret_value(),
    )


async def generate_search_queries(question: str) -> SearchQueries:
    async with _limiter:
        try:
            async with get_client().aio as client:
                response = await client.models.generate_content(
                    model=settings.llm_model,
                    contents=question,
                    config=types.GenerateContentConfig(
                        system_instruction=QUERY_GENERATION_PROMPT,
                        response_mime_type="application/json",
                        response_schema=SearchQueries,
                        max_output_tokens=2048,
                        http_options=types.HttpOptions(
                            timeout=30000,
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    ),
                )
            return SearchQueries.model_validate_json(response.text or "")
        except Exception as exc:
            raise QueryGenerationError("Search query generation failed") from exc
