import sys
from unittest.mock import MagicMock


# Create a mock Red class
class MockRed:
    def __init__(self):
        self.add_cog = MagicMock()


# Mock the redbot module
mock_redbot = MagicMock()
mock_redbot.core.bot.Red = MockRed

# Add the mock to sys.modules
sys.modules["redbot"] = mock_redbot
sys.modules["redbot.core"] = mock_redbot.core
sys.modules["redbot.core.bot"] = mock_redbot.core.bot
