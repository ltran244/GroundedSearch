from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """One web result, using Brave's field names."""

    title: str
    url: str
    # Brave's snippet. Absent on some results, so it defaults to empty.
    description: str = ""
    extra_snippets: list[str] | None = None


class QueryResults(BaseModel):
    """What one search query found, in Brave's rank order."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)


class BraveWebResults(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)


class BraveSearchResponse(BaseModel):
    """The parts of a GET web/search response needed."""

    web: BraveWebResults | None = None
