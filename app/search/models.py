from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    description: str = ""


class QuerySearchResults(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)


class BraveWebResults(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)


class BraveSearchResponse(BaseModel):
    web: BraveWebResults | None = None
