from pydantic import BaseModel


class GeneratedQueries(BaseModel):
    """Search queries Gemini generates for one research question."""

    queries: list[str]
