from unittest.mock import AsyncMock, MagicMock

import pytest
from cogs.llm.llm_cog import LLMCog


@pytest.fixture
def mock_interaction():
    # Create a mock interaction object that simulates Discord interactions
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_ask_command_success(mock_interaction):
    mock_bot = AsyncMock()
    cog = LLMCog(mock_bot)
    # Test successful response
    cog.chain.run = AsyncMock(return_value=MagicMock(content="Test response", error=False))
    await cog.ask(mock_interaction, "test prompt")
    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_with("🤖 **Response**\nTest response")


@pytest.mark.asyncio
async def test_ask_command_error(mock_interaction):
    mock_bot = AsyncMock()
    cog = LLMCog(mock_bot)
    # Test error response
    cog.chain.run = AsyncMock(return_value=MagicMock(error=True, error_message="Simulated error"))
    await cog.ask(mock_interaction, "test prompt")
    mock_interaction.response.defer.assert_awaited_once()
    mock_interaction.followup.send.assert_awaited_with("⚠️ Error processing your request. Please try again later.")
