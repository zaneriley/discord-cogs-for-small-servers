"""
Tests for the JSON to Markdown converter for weather data.
"""

from cogs.utilities.llm.json_to_markdown import json_to_markdown_weather_summary


def test_json_to_markdown_skeleton():
    """Test the basic skeleton function returns an empty string."""
    assert json_to_markdown_weather_summary({}) == ""


def test_json_to_markdown_city_headers():
    """Test extraction of city names and formatting as Markdown headers."""
    # Create a simplified test fixture with just the city structure
    test_data = {
        "all_cities": {
            "New York": {},
            "Los Angeles": {},
            "Chicago": {}
        }
    }
    expected_output = "## New York\n\n## Los Angeles\n\n## Chicago\n"
    result = json_to_markdown_weather_summary(test_data)
    assert result == expected_output


def test_json_to_markdown_current_temp():
    """Test extraction and formatting of current temperature and feels like."""
    # Create a simplified test fixture with temperature data
    test_data = {
        "all_cities": {
            "New York": {
                "current_units": {
                    "temperature_2m": "°C",
                    "apparent_temperature": "°C"
                },
                "current": {
                    "temperature_2m": 5.7,
                    "apparent_temperature": 0.1
                }
            }
        }
    }

    expected_output = "## New York\n\n**Current Weather:**\n\n* Temperature: 5.7°C\n\n* Feels like: 0.1°C\n"
    result = json_to_markdown_weather_summary(test_data)
    assert result == expected_output


def test_json_to_markdown_current_humidity_wind():
    """Test extraction and formatting of humidity and wind data."""
    # Create a simplified test fixture with humidity and wind data
    test_data = {
        "all_cities": {
            "New York": {
                "current_units": {
                    "relative_humidity_2m": "%",
                    "wind_speed_10m": "km/h",
                    "wind_direction_10m": "°"
                },
                "current": {
                    "relative_humidity_2m": 51,
                    "wind_speed_10m": 20.2,
                    "wind_direction_10m": 272
                }
            }
        }
    }
    expected_output = "## New York\n\n**Current Weather:**\n\n* Humidity: 51%\n\n* Wind: 20.2 km/h from 272°\n"
    result = json_to_markdown_weather_summary(test_data)
    assert result == expected_output
