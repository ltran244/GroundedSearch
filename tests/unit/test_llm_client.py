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
from app.llm.models import AnswerSource


def fake_client(output_text: str | None) -> Any:
    """Stands in for genai.Client, answering with a fixed output_text."""
    create = AsyncMock(return_value=SimpleNamespace(output_text=output_text))
    return SimpleNamespace(
        aio=SimpleNamespace(interactions=SimpleNamespace(create=create))
    )


def generate(queries: list[str]):
    client = fake_client(json.dumps({"queries": queries}))
    return asyncio.run(generate_search_query(client, "question"))


def test_returns_the_queries():
    assert generate(["a", "b", "c"]).queries == ["a", "b", "c"]


def test_drops_duplicates_ignoring_case_and_spacing():
    # search_queries has UNIQUE (research_job_id, query).
    assert generate(["A  b", "a b", "c", "d"]).queries == ["A b", "c", "d"]


def test_keeps_at_most_five():
    assert len(generate([f"q{n}" for n in range(8)]).queries) == 5


def test_rejects_fewer_than_three():
    with pytest.raises(QueryGenerationError):
        generate(["a", "a", " "])


def test_rejects_an_empty_response():
    # output_text is None when the response was blocked or empty.
    with pytest.raises(QueryGenerationError):
        asyncio.run(generate_search_query(fake_client(None), "question"))


def answer(sources: list[AnswerSource], output_text: str | None = "answer [1]"):
    client = fake_client(output_text)
    result = asyncio.run(generate_answer(client, "question", sources))
    return result, client.aio.interactions.create


def test_numbers_each_source_with_its_title_and_url():
    result, create = answer(
        [
            AnswerSource(title="T1", url="u1", text="text one"),
            AnswerSource(title="T2", url="u2", text="text two"),
        ]
    )

    assert result == "answer [1]"
    sent = create.await_args.kwargs["input"]
    assert "question" in sent
    assert "[1] T1\nURL: u1\ntext one" in sent
    assert "[2] T2\nURL: u2\ntext two" in sent


def test_rejects_an_empty_answer():
    with pytest.raises(AnswerGenerationError):
        answer([AnswerSource(title="T", url="u", text="text")], output_text="  ")


def test_refuses_to_answer_without_sources():
    with pytest.raises(AnswerGenerationError):
        answer([])
