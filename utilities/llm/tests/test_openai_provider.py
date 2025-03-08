from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Using cogs prefix as it's in PYTHONPATH in Docker
from utilities.llm.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_init():
    """Test OpenAIProvider initialization."""
    # Test with mock environment variables
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
        provider = OpenAIProvider()
        assert provider.api_key == "test-key"
        assert "api.openai.com" in provider.endpoint


@pytest.mark.asyncio
async def test_openai_provider_missing_key():
    """Test OpenAIProvider handles missing API key."""
    # Test with no API key
    with patch.dict("os.environ", {}, clear=True):
        provider = OpenAIProvider()
        response = await provider.send_prompt("Test prompt")

        # Verify error response
        assert response.error
        assert "API key not configured" in response.error_message


@pytest.mark.asyncio
async def test_openai_provider_send_prompt():
    """Test OpenAIProvider.send_prompt builds correct request and parses response."""
    # Create mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Mocked response"}}],
        "usage": {"total_tokens": 10}
    })
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = AsyncMock(return_value=mock_response)

    # Create provider and patch aiohttp.ClientSession
    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
            provider = OpenAIProvider()
            response = await provider.send_prompt("Test prompt", model="test-model")

            # Verify request format
            mock_session.post.assert_called_once()
            args, kwargs = mock_session.post.call_args

            # Check URL
            assert args[0] == "https://api.openai.com/v1/chat/completions"

            # Check headers
            assert kwargs["headers"]["Authorization"] == "Bearer test-key"

            # Check payload
            assert kwargs["json"]["model"] == "test-model"
            assert kwargs["json"]["messages"][0]["role"] == "user"
            assert kwargs["json"]["messages"][0]["content"] == "Test prompt"

            # Verify response parsing
            assert response.content == "Mocked response"
            assert response.tokens_used == 10
            assert not response.error


@pytest.mark.asyncio
async def test_openai_provider_error_handling():
    """Test OpenAIProvider handles API errors correctly."""
    # Create mock session that raises an exception
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Make post method raise an error
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=MagicMock(),
        status=429,
        message="Rate limit exceeded"
    )
    mock_session.post = AsyncMock(side_effect=error)

    # Create provider and patch aiohttp.ClientSession
    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
            provider = OpenAIProvider()
            response = await provider.send_prompt("Test prompt")

            # Verify error handling
            assert response.error
            assert "Rate limit exceeded" in response.error_message
