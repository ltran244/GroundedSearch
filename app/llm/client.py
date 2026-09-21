from google import genai
from pydantic import BaseModel

from app.config import settings
from app.llm.prompts import QUERY_GENERATION_PROMPT

MIN_QUERIES = 3
MAX_QUERIES = 5


class QueryGenerationError(RuntimeError):
    """Raised when Gemini does not return usable search queries."""


def get_client() -> genai.Client:
    """Create a Gemini client; the caller must close it after use."""
    if not settings.google_api_key or not settings.google_api_key.get_secret_value():
        raise ValueError("Set GOOGLE_API_KEY in .env before using the Google API")
    return genai.Client(
        api_key=settings.google_api_key.get_secret_value(),
    )


class GeneratedQueries(BaseModel):
    queries: list[str]


def generate_search_query(client: genai.Client, query: str) -> GeneratedQueries:
    interaction = client.interactions.create(
        model=settings.llm_model,
        input=query,
        system_instruction=QUERY_GENERATION_PROMPT,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": GeneratedQueries.model_json_schema(),
        },
        stream=False,
    )
    # stream=False always returns an Interaction, but the SDK types create() as
    # returning Interaction | Stream, and Stream has no output_text.
    output_text = interaction.output_text  # pyright: ignore[reportAttributeAccessIssue]
    if not output_text:
        raise QueryGenerationError("Gemini returned no search queries")
    generated = GeneratedQueries.model_validate_json(output_text)

    # Drop blanks and repeats before counting: two queries differing only in
    # case or spacing would break search_queries' UNIQUE (research_job_id, query).
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in generated.queries:
        candidate = " ".join(candidate.split())
        if not candidate or candidate.casefold() in seen:
            continue
        seen.add(candidate.casefold())
        unique.append(candidate)

    if len(unique) < MIN_QUERIES:
        raise QueryGenerationError(
            f"Gemini returned {len(unique)} usable queries, need at least {MIN_QUERIES}"
        )
    return GeneratedQueries(queries=unique[:MAX_QUERIES])
