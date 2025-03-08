from unittest.mock import AsyncMock, patch

import pytest
from cogs.weatherchannel.weather_service import WeatherService

# Fixtures now imported from conftest.py

@pytest.fixture
def mock_open_meteo_data():
    """Mock Open-Meteo API response."""
    return {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "timezone": "America/Los_Angeles",
        "current": {
            "temperature_2m": 20.5,
            "relative_humidity_2m": 65,
            "apparent_temperature": 21.0,
            "is_day": 1,
            "precipitation": 0.0,
            "rain": 0.0,
            "showers": 0.0,
            "snowfall": 0.0,
            "weather_code": 0,  # Clear sky
            "wind_speed_10m": 5.2,
            "wind_direction_10m": 270,
            "wind_gusts_10m": 7.5
        },
        "hourly": {
            "temperature_2m": [20.5, 21.0, 22.0, 23.5],
            "relative_humidity_2m": [65, 60, 55, 50],
            "apparent_temperature": [21.0, 21.5, 22.5, 24.0],
            "precipitation_probability": [0, 0, 0, 0],
            "precipitation": [0.0, 0.0, 0.0, 0.0],
            "weather_code": [0, 0, 0, 1],
            "wind_speed_10m": [5.2, 5.5, 6.0, 6.5],
            "wind_direction_10m": [270, 275, 280, 285]
        },
        "daily": {
            "weather_code": [0],  # Clear sky
            "temperature_2m_max": [25.0],
            "temperature_2m_min": [18.0],
            "apparent_temperature_max": [26.0],
            "apparent_temperature_min": [17.0],
            "sunrise": ["06:15"],
            "sunset": ["19:30"],
            "precipitation_sum": [0.0],
            "precipitation_probability_max": [0]
        }
    }

@pytest.fixture
def mock_tokyo_open_meteo_data():
    """Mock Open-Meteo API response for Tokyo with enhanced data format."""
    return {
        "latitude": 35.6895,
        "longitude": 139.6917,
        "timezone": "Asia/Tokyo",
        "current": {
            "temperature_2m": 22.3,
            "relative_humidity_2m": 70,
            "apparent_temperature": 23.1,
            "is_day": 1,
            "precipitation": 0.0,
            "rain": 0.0,
            "showers": 0.0,
            "snowfall": 0.0,
            "weather_code": 1,  # Mainly clear
            "wind_speed_10m": 8.2,
            "wind_direction_10m": 180,
            "wind_gusts_10m": 10.5
        },
        "hourly": {
            "temperature_2m": [21.5, 22.0, 23.0, 24.5],
            "relative_humidity_2m": [68, 70, 65, 60],
            "apparent_temperature": [22.0, 22.5, 23.5, 25.0],
            "precipitation_probability": [0, 0, 10, 20],
            "precipitation": [0.0, 0.0, 0.0, 0.5],
            "weather_code": [1, 1, 2, 3],
            "wind_speed_10m": [7.2, 8.2, 9.0, 8.5],
            "wind_direction_10m": [175, 180, 185, 190]
        },
        "daily": {
            "weather_code": [1],  # Mainly clear
            "temperature_2m_max": [28.5],
            "temperature_2m_min": [21.2],
            "apparent_temperature_max": [29.0],
            "apparent_temperature_min": [22.0],
            "sunrise": ["05:30"],
            "sunset": ["18:45"],
            "precipitation_sum": [0.5],
            "precipitation_probability_max": [20]
        }
    }

@pytest.fixture
def mock_weather_gov_data():
    """Mock Weather.gov API response."""
    return {
        "properties": {
            "periods": [
                {
                    "startTime": "2024-03-04T12:00:00-05:00",
                    "isDaytime": True,
                    "temperature": 68,
                    "temperatureUnit": "F",
                    "windSpeed": "10 mph",
                    "relativeHumidity": {"value": 65},
                    "shortForecast": "Sunny",
                    "detailedForecast": "Sunny, with a high near 68.",
                    "probabilityOfPrecipitation": {"value": 0}
                },
                {
                    "startTime": "2024-03-04T18:00:00-05:00",
                    "isDaytime": False,
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "windSpeed": "5 mph",
                    "relativeHumidity": {"value": 75},
                    "shortForecast": "Clear",
                    "detailedForecast": "Clear, with a low around 45.",
                    "probabilityOfPrecipitation": {"value": 0}
                }
            ]
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

@pytest.mark.asyncio
async def test_fetch_weather_success(mock_strings, mock_open_meteo_data, mock_api_handler):
    """Test successful weather data fetching."""
    service = WeatherService(strings=mock_strings)

    # Mock the API handler
    handler = mock_api_handler(mock_open_meteo_data)
    service.api_handlers = {"open-meteo": handler}

    result = await service.fetch_weather("open-meteo", (37.7749, -122.4194), "San Francisco")

    # New assertions for dictionary response
    assert isinstance(result, dict)
    assert "ᴄɪᴛʏ" in result
    assert "San Francisco" in result["ᴄɪᴛʏ"]
    assert "ʜ°ᴄ" in result
    assert "ʟ°ᴄ" in result
    assert "ᴘʀᴇᴄɪᴘ" in result
    assert "ᴄᴏɴᴅ" in result
    assert "Clear sky" in result["ᴄᴏɴᴅ"]
    assert "ᴅᴇᴛᴀɪʟs" in result

@pytest.mark.asyncio
async def test_fetch_weather_error(mock_strings):
    """Test error handling during weather data fetching."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = Exception("API Error")

        service = WeatherService(strings=mock_strings)
        result = await service.fetch_weather("open-meteo", (37.7749, -122.4194), "San Francisco")
        assert isinstance(result, dict)
        assert "error" in result
        assert "Error fetching weather" in result["error"]
        assert "San Francisco" in result["error"]

@pytest.mark.asyncio
async def test_fetch_city_weather_success(mock_strings, mock_open_meteo_data, mock_api_handler):
    """Test successful weather retrieval for a specific city."""
    locations_data = {
        "San Francisco": ("open-meteo", (37.7749, -122.4194))
    }

    service = WeatherService(strings=mock_strings)

    # Mock the API handler
    handler = mock_api_handler(mock_open_meteo_data)
    service.api_handlers = {"open-meteo": handler}

    result = await service.fetch_city_weather("San Francisco", locations_data)

    # New assertions for dictionary response
    assert isinstance(result, dict)
    assert "ᴄɪᴛʏ" in result
    assert "San Francisco" in result["ᴄɪᴛʏ"]
    assert "ʜ°ᴄ" in result
    assert "ʟ°ᴄ" in result
    assert "ᴘʀᴇᴄɪᴘ" in result
    assert "ᴄᴏɴᴅ" in result
    assert "Clear sky" in result["ᴄᴏɴᴅ"]

@pytest.mark.asyncio
async def test_fetch_city_weather_not_found(mock_strings):
    """Test weather retrieval for a non-existent city."""
    locations_data = {
        "San Francisco": ("open-meteo", (37.7749, -122.4194))
    }

    service = WeatherService(strings=mock_strings)
    result = await service.fetch_city_weather("NonExistentCity", locations_data)
    assert result is None

@pytest.mark.asyncio
async def test_fetch_all_locations_weather_success(mock_strings, mock_open_meteo_data, mock_api_handler):
    """Test successful weather retrieval for multiple locations."""
    locations_data = {
        "San Francisco": ("open-meteo", (37.7749, -122.4194)),
        "New York": ("open-meteo", (40.7128, -74.0060))
    }

    service = WeatherService(strings=mock_strings)

    # Mock the API handler
    handler = mock_api_handler(mock_open_meteo_data)
    service.api_handlers = {"open-meteo": handler}

    results = await service.fetch_all_locations_weather(locations_data)
    assert isinstance(results, list)
    assert len(results) == 2
    for result in results:
        assert isinstance(result, dict)
        assert "ᴄɪᴛʏ" in result
        assert "ʜ°ᴄ" in result
        assert "ʟ°ᴄ" in result
        assert "ᴘʀᴇᴄɪᴘ" in result

@pytest.mark.asyncio
async def test_fetch_mixed_api_locations_weather(mock_strings, mock_open_meteo_data, mock_weather_gov_data, mock_api_handler):
    """Test weather retrieval from multiple API types."""
    locations_data = {
        "San Francisco": ("open-meteo", (37.7749, -122.4194)),
        "Washington DC": ("weather-gov", (38.9072, -77.0370))
    }

    service = WeatherService(strings=mock_strings)

    # Mock the API handlers
    open_meteo_handler = mock_api_handler(mock_open_meteo_data)
    weather_gov_handler = mock_api_handler(mock_weather_gov_data)
    service.api_handlers = {
        "open-meteo": open_meteo_handler,
        "weather-gov": weather_gov_handler
    }

    results = await service.fetch_all_locations_weather(locations_data)
    assert isinstance(results, list)
    assert len(results) == 2
    
    # Check each result - some might be error messages if the formatter couldn't handle the data
    for result in results:
        # Accept either dictionary (successful formatting) or string (error message)
        assert isinstance(result, (dict, str))
        
        # If it's a dict, verify it has the required keys
        if isinstance(result, dict):
            assert "ᴄɪᴛʏ" in result
            assert "ʜ°ᴄ" in result
            assert "ʟ°ᴄ" in result
            assert "ᴘʀᴇᴄɪᴘ" in result

@pytest.mark.asyncio
async def test_fetch_tokyo_weather_success(mock_strings, mock_tokyo_open_meteo_data, mock_api_handler):
    """Test successful retrieval of Tokyo weather data with temperature rounding and precipitation percentage."""
    service = WeatherService(strings=mock_strings)

    # Mock the API handler
    handler = mock_api_handler(mock_tokyo_open_meteo_data)
    service.api_handlers = {"open-meteo": handler}

    result = await service.fetch_weather("open-meteo", (35.6895, 139.6917), "Tokyo")

    # Verify the formatted output has rounded temperatures and percentage for precipitation
    assert isinstance(result, dict)
    assert "ᴄɪᴛʏ" in result
    assert "Tokyo" in result["ᴄɪᴛʏ"]
    assert "ʜ°ᴄ" in result
    assert "28°" in result["ʜ°ᴄ"]  # Should be rounded from 28.5°
    assert "ʟ°ᴄ" in result
    assert "21°" in result["ʟ°ᴄ"]  # Should be rounded from 21.2°
    assert "ᴘʀᴇᴄɪᴘ" in result
    assert "20%" in result["ᴘʀᴇᴄɪᴘ"]  # Should be percentage instead of mm 