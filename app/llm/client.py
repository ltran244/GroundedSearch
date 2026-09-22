from google import genai

from app.config import settings
from app.llm.models import GeneratedQueries
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


async def check_gemini() -> None:
    """Confirm the API key works and the configured model exists.

    Fetches the model's metadata instead of generating anything, so it uses no
    tokens. Raises if the key is missing or rejected, or the model is retired.
    """
    await get_client().aio.models.get(model=settings.llm_model)


async def generate_search_query(client: genai.Client, query: str) -> GeneratedQueries:
    interaction = await client.aio.interactions.create(
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
    output_text = interaction.output_text  # pyright: ignore[reportAttributeAccessIssue]
    if not output_text:
        raise QueryGenerationError("Gemini returned no search queries")
    generated = GeneratedQueries.model_validate_json(output_text)
    # drop duplicates and blanks queries
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


async def generate_answer(client: genai.Client, question: str, sources: list[str]) -> str:
    """Write an answer to the question from the extracted source texts.

    1. Number the sources [1], [2], ... in the prompt, in the order passed in.
    2. Instruct the model to answer only from those sources and to cite them
       with [n] markers after each claim. That numbering is what ties a claim
       back to a source row.
    3. Needs a synthesis prompt in app/llm/prompts.py next to the query one.
    4. Same guards as generate_search_query: raise QueryGenerationError-style
       errors on an empty or blocked response.
    """
    raise NotImplementedError
