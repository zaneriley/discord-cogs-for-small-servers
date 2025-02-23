import pytest
from cogs.utilities.llm.providers.base import LLMResponse
from cogs.utilities.llm.providers.openai_provider import OpenAIProvider


# We need to simulate aiohttp.ClientSession behavior using monkeypatch.
class DummyResponse:
    def __init__(self, json_data, status=200):
        self._json_data = json_data
        self.status = status

    async def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status >= 400:
            msg = "HTTP error"
            raise Exception(msg)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

class DummySession:
    def __init__(self, json_data, status=200):
        self.json_data = json_data
        self.status = status

    def post(self, url, json, headers, timeout):
        return DummyResponse(self.json_data, status=self.status)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

@pytest.mark.asyncio
async def test_openai_provider_success(monkeypatch):
    # Define dummy JSON response similar to OpenAI API.
    dummy_json = {
        "choices": [{
            "message": {"content": "dummy reply"}
        }],
        "usage": {"total_tokens": 42}
    }

    # Monkeypatch the aiohttp.ClientSession to always return our dummy response.
    async def dummy_client_session(*args, **kwargs):
        return DummySession(dummy_json)

    monkeypatch.setattr("cogs.utilities.llm.providers.openai_provider.aiohttp.ClientSession", lambda *args, **kwargs: DummySession(dummy_json))

    provider = OpenAIProvider()
    response = await provider.send_prompt("Hello")
    assert isinstance(response, LLMResponse)
    assert response.content == "dummy reply"
    assert response.tokens_used == 42
    assert not response.error

@pytest.mark.asyncio
async def test_openai_provider_error(monkeypatch):
    # Simulate an error in the HTTP call.
    async def dummy_client_session_error(*args, **kwargs):
        # Return a DummySession that simulates an HTTP error.
        return DummySession({}, status=500)

    monkeypatch.setattr("cogs.utilities.llm.providers.openai_provider.aiohttp.ClientSession", lambda *args, **kwargs: DummySession({}, status=500))

    provider = OpenAIProvider()
    response = await provider.send_prompt("Hello", timeout=1)
    assert isinstance(response, LLMResponse)
    assert response.error
    assert "HTTP error" in response.error_message
