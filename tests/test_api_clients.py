from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.config import settings
from app.llm import client as google_client
from app.search import brave


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("key", [None, SecretStr("")])
def test_google_rejects_missing_key(monkeypatch, key):
    monkeypatch.setattr(settings, "google_api_key", key)
    with patch.object(google_client.genai, "Client") as constructor:
        with pytest.raises(ValueError, match="Set GOOGLE_API_KEY"):
            google_client.get_client()
    constructor.assert_not_called()


def test_google_client_configuration(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", SecretStr("test-google-key"))
    with patch.object(google_client.genai, "Client") as constructor:
        client = google_client.get_client()

    assert client is constructor.return_value
    constructor.assert_called_once()
    assert constructor.call_args.kwargs["api_key"] == "test-google-key"
    assert constructor.call_args.kwargs["http_options"].timeout == 30000


@pytest.mark.parametrize("key", [None, SecretStr("")])
def test_brave_rejects_missing_key(monkeypatch, key):
    monkeypatch.setattr(settings, "brave_search_api_key", key)
    with patch.object(brave.httpx, "AsyncClient") as constructor:
        with pytest.raises(ValueError, match="Set BRAVE_SEARCH_API_KEY"):
            brave.get_client()
    constructor.assert_not_called()


@pytest.mark.anyio
async def test_brave_request_configuration(monkeypatch):
    monkeypatch.setattr(settings, "brave_search_api_key", SecretStr("test-brave-key"))
    async with brave.get_client() as client:
        # Building a request checks configuration without sending it to Brave.
        request = client.build_request(
            "GET", "web/search", params={"q": "solar panels & batteries"}
        )
        assert request.method == "GET"
        assert request.url.scheme == "https"
        assert request.url.host == "api.search.brave.com"
        assert request.url.path == "/res/v1/web/search"
        assert request.url.params["q"] == "solar panels & batteries"
        assert request.headers["X-Subscription-Token"] == "test-brave-key"
        assert request.headers["Accept"] == "application/json"
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 30.0
    assert client.is_closed
