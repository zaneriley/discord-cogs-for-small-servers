import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import asyncio
import aiohttp
from discord.ext import commands

# Add the project root to the Python path to ensure imports work correctly
sys.path.insert(0, str(Path(__file__).parents[3]))

# Import these modules to address linter errors
from cogs.weatherchannel.weather_service import WeatherService
from cogs.weatherchannel.weather_config import WeatherConfig

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
            },
            "Los Angeles": {
                "api_type": "open-meteo",
                "coordinates": [34.0522, -118.2437],
                "display_name": "Los Angeles"
            },
            "Chicago": {
                "api_type": "weather-gov",
                "coordinates": [41.8781, -87.6298],
                "display_name": "Chicago"
            }
        },
        "special_options": {
            "Everywhere": {
                "display_name": "Everywhere",
                "description": "All configured cities"
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

@pytest.fixture
def weather_test_data():
    """Provides test weather data."""
    fixtures_path = Path(__file__).parent / "fixtures" / "weather-test-data.json"
    with open(fixtures_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@pytest.fixture
def all_cities_fixture(weather_test_data):
    """Provides the all_cities test data for test cases."""
    if 'all_cities' in weather_test_data:
        return weather_test_data['all_cities']
    return {}

@pytest.fixture
def weather_config():
    """Creates a test weather configuration."""
    return WeatherConfig(
        api_type="open-meteo",
        locations={
            "New York": {"latitude": 40.7128, "longitude": -74.0060},
            "Berlin": {"latitude": 52.5200, "longitude": 13.4050},
            "Tokyo": {"latitude": 35.6762, "longitude": 139.6503},
            "Sydney": {"latitude": -33.8688, "longitude": 151.2093},
        },
        units="metric",
        update_interval=30,
        cache_ttl=60,
        channel_id="123456789",
        enabled=True,
    )

@pytest.fixture
def weather_service(weather_config):
    """Creates a weather service for testing."""
    service = WeatherService(weather_config)
    return service

@pytest.fixture
def mock_bot():
    """Creates a mock bot instance for testing."""
    bot = commands.Bot(command_prefix="!")
    return bot

@pytest.fixture
def mock_ctx(mock_bot):
    """Creates a mock context for command testing."""
    ctx = type("Context", (), {
        "bot": mock_bot,
        "send": lambda *args, **kwargs: asyncio.sleep(0),
        "defer": lambda *args, **kwargs: asyncio.sleep(0),
        "channel": type("Channel", (), {"id": "123456789"})
    })
    return ctx

@pytest.fixture
def mock_session():
    """Creates a mock session for API calls."""
    class MockResponse:
        def __init__(self, data, status=200):
            self.data = data
            self.status = status
            
        async def json(self):
            return self.data
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    class MockClientSession:
        def __init__(self):
            self.closed = False
            self.responses = []
            
        def add_response(self, url, data, status=200):
            self.responses.append((url, data, status))
            
        async def get(self, url, **kwargs):
            for r_url, data, status in self.responses:
                if url == r_url:
                    return MockResponse(data, status)
            return MockResponse({"error": "Not found"}, 404)
            
        async def close(self):
            self.closed = True
            
    return MockClientSession()

@pytest.fixture
def mock_weather_data():
    """Provides mock weather data for API response simulation."""
    return {
        "latitude": 40.7143,
        "longitude": -74.006,
        "generationtime_ms": 0.2510547637939453,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 47.0,
        "current_weather": {
            "temperature": 15.3,
            "windspeed": 9.3,
            "winddirection": 289,
            "weathercode": 0,
            "time": "2023-04-26T12:00"
        },
        "daily_units": {
            "time": "iso8601",
            "weathercode": "wmo code",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C"
        },
        "daily": {
            "time": [
                "2023-04-26", "2023-04-27", "2023-04-28"
            ],
            "weathercode": [3, 3, 3],
            "temperature_2m_max": [15.8, 16.2, 15.7],
            "temperature_2m_min": [9.3, 9.7, 9.1]
        }
    }
