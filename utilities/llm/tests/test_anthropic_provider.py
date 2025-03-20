from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Using cogs prefix as it's in PYTHONPATH in Docker
from utilities.llm.providers.anthropic_provider import AnthropicProvider


@pytest.mark.asyncio
async def test_anthropic_provider_init():
    """Test AnthropicProvider initialization."""
    # Test with mock environment variables
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        provider = AnthropicProvider()
        assert provider.api_key == "test-key"
        assert "api.anthropic.com" in provider.endpoint
        assert provider.api_version == "2023-06-01"


@pytest.mark.asyncio
async def test_anthropic_provider_missing_key():
    """Test AnthropicProvider handles missing API key."""
    # Test with no API key
    with patch.dict("os.environ", {}, clear=True):
        provider = AnthropicProvider()
        response = await provider.send_prompt("Test prompt")

        # Verify error response
        assert response.error
        assert "API key not configured" in response.error_message


@pytest.mark.asyncio
async def test_anthropic_provider_send_prompt():
    """Test AnthropicProvider.send_prompt builds correct request and parses response."""
    # Create mock response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "content": [{"type": "text", "text": "Mocked Claude response"}],
        "usage": {"input_tokens": 5, "output_tokens": 10}
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
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            provider = AnthropicProvider()
            response = await provider.send_prompt(
                "Test prompt",
                model="claude-3-opus-20240229",
                system="You are a helpful assistant."
            )

            # Verify request format
            mock_session.post.assert_called_once()
            args, kwargs = mock_session.post.call_args

            # Check URL
            assert args[0] == "https://api.anthropic.com/v1/messages"

            # Check headers
            assert kwargs["headers"]["x-api-key"] == "test-key"
            assert kwargs["headers"]["anthropic-version"] == "2023-06-01"

            # Check payload
            assert kwargs["json"]["model"] == "claude-3-opus-20240229"
            assert kwargs["json"]["messages"][0]["role"] == "user"
            assert kwargs["json"]["messages"][0]["content"] == "Test prompt"
            assert kwargs["json"]["system"] == "You are a helpful assistant."

            # Verify response parsing
            assert response.content == "Mocked Claude response"
            assert response.tokens_used == 15  # input + output tokens
            assert not response.error


@pytest.mark.asyncio
async def test_anthropic_provider_empty_response():
    """Test AnthropicProvider handles empty response correctly."""
    # Create mock response with empty content
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "content": [],
        "usage": {"input_tokens": 5, "output_tokens": 0}
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
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            provider = AnthropicProvider()
            response = await provider.send_prompt("Test prompt")

            # Verify request was made
            mock_session.post.assert_called_once()

            # Verify empty response handling
            assert response.content == ""
            assert response.tokens_used == 5  # Only input tokens
            assert not response.error


@pytest.mark.asyncio
async def test_anthropic_provider_error_handling():
    """Test AnthropicProvider handles API errors correctly."""
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
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            provider = AnthropicProvider()
            response = await provider.send_prompt("Test prompt")

            # Verify error handling
            assert response.error
            assert "Rate limit exceeded" in response.error_message
