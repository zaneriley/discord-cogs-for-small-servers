from unittest.mock import MagicMock

import aiohttp
import pytest

# Using cogs prefix as it's in PYTHONPATH in Docker
from utilities.llm.providers.base import BaseLLMProvider, LLMResponse


class MockResponse:

    """Mock HTTP response for testing."""

    def __init__(self, json_data, status=200):
        self.json_data = json_data
        self.status = status

    async def json(self):
        return self.json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=MagicMock(),
                status=self.status,
                message=f"HTTP Error {self.status}"
            )


class MockClientSession:

    """Mock aiohttp ClientSession for testing."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def post(self, url, json=None, headers=None, **kwargs):
        self.requests.append({
            "url": url,
            "json": json,
            "headers": headers,
            "kwargs": kwargs
        })

        for pattern, (response_json, status) in self.responses.items():
            if pattern in url:
                return MockResponse(response_json, status)

        # Default response
        return MockResponse({"choices": [{"message": {"content": "Default response"}}]})


class MockLLMProvider(BaseLLMProvider):

    """Mock LLM provider for testing LLMChain."""

    def __init__(self, response_content="Mock response", tokens_used=10, error=False, error_message=""):
        self.response_content = response_content
        self.tokens_used = tokens_used
        self.error = error
        self.error_message = error_message
        self.prompts = []

    async def send_prompt(self, prompt, **kwargs):
        self.prompts.append((prompt, kwargs))
        return LLMResponse(
            content=self.response_content,
            tokens_used=self.tokens_used,
            error=self.error,
            error_message=self.error_message
        )


@pytest.fixture
def mock_client_session():
    """Fixture to create a mock client session."""
    def _create_session(responses=None):
        return MockClientSession(responses)
    return _create_session


@pytest.fixture
def mock_llm_provider():
    """Fixture to create a mock LLM provider."""
    def _create_provider(response_content="Mock response", tokens_used=10, error=False, error_message=""):
        return MockLLMProvider(response_content, tokens_used, error, error_message)
    return _create_provider
