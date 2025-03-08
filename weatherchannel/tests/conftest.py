import sys
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord import app_commands

# Add the project root to the Python path to ensure imports work correctly
sys.path.insert(0, str(Path(__file__).parents[3]))

@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {
        "GUILD_ID": "123456789",
        "WX_LOCATIONS": json.dumps({
            "San Francisco": ("open-meteo", "37.7749,-122.4194"),
            "New York": ("open-meteo", "40.7128,-74.0060")
        })
    }):
        yield

@pytest.fixture
def mock_cities_json(tmp_path):
    """Create a temporary cities.json file."""
    cities_file = tmp_path / "cities.json"
    cities_data = {
        "cities": {
            "San Francisco": {
                "api_type": "open-meteo",
                "coordinates": [37.7749, -122.4194],
                "display_name": "San Francisco"
            },
            "New York": {
                "api_type": "open-meteo",
                "coordinates": [40.7128, -74.0060],
                "display_name": "New York"
            }
        }
    }
    cities_file.write_text(json.dumps(cities_data))
    return cities_file

@pytest.fixture
def mock_cog():
    """Create a mock cog instance."""
    cog = MagicMock()
    cog.__class__.__name__ = "WeatherChannelCog"
    return cog

@pytest.fixture
def mock_config():
    """Create a mock Red-DiscordBot Config."""
    config = MagicMock()
    guild_config = MagicMock()
    config.guild_from_id.return_value = guild_config
    return config

@pytest.fixture
def mock_aiohttp_client():
    """Create a mock aiohttp client that returns the specified response data."""
    def _mock_client(response_data):
        mock_get = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = response_data
        mock_get.return_value.__aenter__.return_value = mock_response
        return mock_get
    return _mock_client

@pytest.fixture
def mock_strings():
    """Mock error strings."""
    return {
        "errors": {
            "service": {
                "coords_conversion_error": "Error converting coordinates for {city}",
                "invalid_coords_format": "Invalid coordinates format for {city}",
                "weather_fetch_error": "Error fetching weather for {city}",
                "no_weather_data": "No weather data available",
                "no_formatter_available": "No formatter available"
            }
        }
    }

@pytest.fixture
def mock_api_handler():
    """Create a mock API handler that returns the specified weather data."""
    def _create_handler(weather_data):
        handler = AsyncMock()
        handler.get_forecast.return_value = weather_data
        return handler
    return _create_handler 