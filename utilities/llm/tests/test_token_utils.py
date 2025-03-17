"""Tests for the token utility functions."""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

from utilities.llm.token_utils import (
    AnthropicTokenCounter,
    compare_token_counts,
    count_tokens,
    count_tokens_batch,
    estimate_tokens,
)

# Add path to find the weatherchannel tests
weather_tests_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "weatherchannel", "tests")
if weather_tests_path not in sys.path:
    sys.path.append(weather_tests_path)

# Import the fixture from weatherchannel tests conftest

# Convert JSON to plain text format
def convert_to_plain_text(weather_data):
    """Convert weather JSON to plain text format."""
    text_lines = []

    for city, data in weather_data.items():
        text_lines.append(f"{city}:")

        # Skip metadata and focus on forecast periods
        if "properties" in data and "periods" in data["properties"]:
            periods = data["properties"]["periods"]

            for period in periods:
                # Extract the essential information
                name = period.get("name", "Unknown")
                temp = period.get("temperature", "N/A")
                temp_unit = period.get("temperatureUnit", "")
                forecast = period.get("shortForecast", "")

                # Get precipitation probability if available
                precip = "N/A"
                if "probabilityOfPrecipitation" in period and period["probabilityOfPrecipitation"].get("value") is not None:
                    precip = f"{period['probabilityOfPrecipitation']['value']}%"

                # Add this period's data
                text_lines.append(f"  {name}: {temp}°{temp_unit}, {forecast}, {precip} chance of precipitation")

    return "\n".join(text_lines)


# Test the estimation function
@pytest.mark.asyncio
async def test_estimate_tokens():
    """Test the token estimation function."""
    simple_text = "Hello, world! This is a test message."
    result = await estimate_tokens(simple_text)

    assert "token_count" in result
    assert result["token_count"] > 0
    assert result["provider"] == "anthropic"
    assert result["estimation_method"] == "approximate"


# Test the Anthropic token counter with a mock response
@pytest.mark.asyncio
async def test_anthropic_token_counter():
    """Test the Anthropic token counter with a mock response."""
    mock_response = {
        "input_tokens": 150
    }

    # Create a mock session that returns our predetermined response
    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value.status = 200
    mock_session.post.return_value.__aenter__.return_value.json = AsyncMock(
        return_value=mock_response
    )

    # Patch aiohttp.ClientSession to use our mock
    with patch("aiohttp.ClientSession", return_value=mock_session):
        counter = AnthropicTokenCounter(api_key="test_key")
        result = await counter.count_tokens("Sample text")

        assert result["token_count"] == 150
        assert result["provider"] == "anthropic"


# Test comparison between JSON and plain text
@pytest.mark.asyncio
async def test_compare_formats_with_estimation(weather_test_data):
    """Test comparing token counts between JSON and plain text formats using estimation."""
    # Convert to plain text
    plain_text = convert_to_plain_text(weather_test_data)

    # Compare using estimation (doesn't require API keys)
    with patch("utilities.llm.token_utils.count_tokens", side_effect=estimate_tokens):
        comparison = await compare_token_counts(weather_test_data, plain_text)

        # Verify the comparison has expected fields
        assert "format_a" in comparison
        assert "format_b" in comparison
        assert "difference" in comparison
        assert "percent_reduction" in comparison

        # Verify the token count reduction
        assert comparison["difference"] > 0  # JSON should have more tokens
        assert comparison["percent_reduction"] > 0

        # Print the comparison for reference


# Test with real Anthropic API if key is available
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="Anthropic API key not available")
@pytest.mark.asyncio
async def test_real_anthropic_token_count(weather_test_data):
    """Test token counting with the real Anthropic API."""
    # Convert to plain text
    convert_to_plain_text(weather_test_data)

    # Only run a subset of the data to avoid large API calls
    city_name = next(iter(weather_test_data.keys()))
    sample_json = {city_name: weather_test_data[city_name]}
    sample_text = convert_to_plain_text(sample_json)

    # Count tokens with real API
    json_count = await count_tokens(sample_json)
    text_count = await count_tokens(sample_text)

    # Verify we got real token counts
    assert json_count["token_count"] > 0
    assert text_count["token_count"] > 0

    # Calculate and print the reduction
    (json_count["token_count"] - text_count["token_count"]) / json_count["token_count"] * 100


# Test batch token counting
@pytest.mark.asyncio
async def test_batch_counting():
    """Test batch token counting."""
    texts = [
        "Hello, world!",
        "This is a longer piece of text that should have more tokens.",
        "A third test string with varying content."
    ]

    # Use estimation for batch test
    with patch("utilities.llm.token_utils.count_tokens", side_effect=estimate_tokens):
        results = await count_tokens_batch(texts)

        assert len(results) == len(texts)
        for result in results:
            assert "token_count" in result
            assert result["token_count"] > 0
