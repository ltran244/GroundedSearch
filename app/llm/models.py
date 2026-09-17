from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator


class SearchQueries(BaseModel):
    queries: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    ] = Field(min_length=3, max_length=5)

    @field_validator("queries")
    @classmethod
    def distinct_queries(cls, queries: list[str]) -> list[str]:
        if len({" ".join(query.casefold().split()) for query in queries}) != len(queries):
            raise ValueError("Search queries must be distinct")
        return queries
