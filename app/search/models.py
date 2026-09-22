from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """One web result, using Brave's field names."""

    title: str
    url: str
    # Brave's snippet. Absent on some results, so it defaults to empty.
    description: str = ""
    extra_snippets: list[str] | None = None


class QueryResults(BaseModel):
    """What one search query found, in Brave's rank order.

    Kept grouped by query so every source can be traced back to the search
    that found it. Flattening is easy later; the link can't be recovered.
    """

    query: str
    results: list[SearchResult] = Field(default_factory=list)


class BraveWebResults(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)


class BraveSearchResponse(BaseModel):
    """The parts of a GET web/search response we read.

    Brave returns many other top-level sections (news, videos, discussions...);
    Pydantic ignores fields that aren't declared, so only `web` is parsed.
    `web` is missing entirely when a query has no web results.
    """

    web: BraveWebResults | None = None
