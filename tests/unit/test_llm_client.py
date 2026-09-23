import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.llm.client import (
    AnswerGenerationError,
    QueryGenerationError,
    generate_answer,
    generate_search_query,
)


def fake_client(output_text: str | None) -> Any:
    """A stand-in for genai.Client that answers with a fixed output_text."""
    create = AsyncMock(return_value=SimpleNamespace(output_text=output_text))
    return SimpleNamespace(
        aio=SimpleNamespace(interactions=SimpleNamespace(create=create))
    )


def queries_response(queries: list[str]) -> str:
    return json.dumps({"queries": queries})


def generate(queries: list[str]):
    client = fake_client(queries_response(queries))
    return asyncio.run(generate_search_query(client, "Is Rust replacing C++?"))


def test_returns_the_generated_queries():
    result = generate(["first query", "second query", "third query"])

    assert result.queries == ["first query", "second query", "third query"]


def test_drops_duplicates_ignoring_case_and_spacing():
    # search_queries has UNIQUE (research_job_id, query), so near-duplicates
    # would fail the insert for the whole job.
    result = generate(["Rust  adoption", "rust adoption", "second query", "third query"])

    assert result.queries == ["Rust adoption", "second query", "third query"]


def test_keeps_at_most_five_queries():
    result = generate([f"query {n}" for n in range(1, 9)])

    assert len(result.queries) == 5


def test_rejects_fewer_than_three_usable_queries():
    with pytest.raises(QueryGenerationError):
        generate(["only one", "only one", "  "])


def test_rejects_an_empty_response():
    # output_text is None when the response was blocked or empty.
    client = fake_client(None)

    with pytest.raises(QueryGenerationError):
        asyncio.run(generate_search_query(client, "a question"))


def answer(sources: list[str], output_text: str | None = "An answer [1]"):
    client = fake_client(output_text)
    result = asyncio.run(generate_answer(client, "Why is the sky blue?", sources))
    return result, client.aio.interactions.create


def test_numbers_the_sources_and_includes_the_question():
    result, create = answer(["First source text", "Second source text"])

    assert result == "An answer [1]"
    sent = create.await_args.kwargs["input"]
    assert "Why is the sky blue?" in sent
    # The [n] numbering is what ties a citation back to a source row.
    assert "[1] First source text" in sent
    assert "[2] Second source text" in sent


def test_rejects_an_empty_answer():
    with pytest.raises(AnswerGenerationError):
        answer(["A source"], output_text="   ")


def test_refuses_to_answer_without_sources():
    # Answering with no sources would be ungrounded by definition.
    with pytest.raises(QueryGenerationError):
        answer([])
