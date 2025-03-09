"""Tests for the WeatherTokenReducer."""

import json
import os
import sys
import unittest
from pathlib import Path

import pytest
from typing import Dict, Any

# Add the parent directory to sys.path to enable imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Import the WeatherTokenReducer directly
sys.path.insert(0, str(current_dir.parent))
from weather_token_reducer import WeatherTokenReducer
from cogs.utilities.llm.token_utils import estimate_tokens


# The fixture is now in conftest.py, so we don't need to define it here

def test_reduce_forecasts(weather_test_data):
    """Test conversion from weather data JSON to plain text."""
    # Get the reducer instance
    reducer = WeatherTokenReducer()
    
    # Process the weather data
    result = reducer.reduce_forecasts(weather_test_data)
    
    # Validate it works
    assert "New York" in result
    assert "temperature" not in result  # Should not contain raw JSON fields
    assert "°" in result  # Should include degree symbol
    
    # Now print for reference
    print(f"\nSample output:\n{result[:200]}...")


def test_reduce_weather_dict(weather_test_data):
    """Test reducing a weather dictionary."""
    # Get the reducer instance
    reducer = WeatherTokenReducer()
    
    # Process the weather data
    result = reducer.reduce_weather_dict(weather_test_data)
    
    # Check structure is simplified
    assert "New York" in result
    assert "periods" in result["New York"]
    
    # Verify we still have essential data elements
    first_city = next(iter(result.keys()))
    assert "periods" in result[first_city]
    assert len(result[first_city]["periods"]) > 0


def test_get_daily_summary(weather_test_data):
    """Test creating a concise daily summary."""
    # Get the reducer instance
    reducer = WeatherTokenReducer()
    
    # Process the weather data
    result = reducer.get_daily_summary(weather_test_data)
    
    # Check it includes basic forecast
    assert "New York" in result 
    assert "°" in result  # Should include degree symbols
    assert len(result) < len(json.dumps(weather_test_data))  # Should be shorter than raw JSON


@pytest.mark.asyncio
async def test_token_reduction(weather_test_data):
    """Test that token reduction is significant."""
    reducer = WeatherTokenReducer()

    # Get both formats
    json_str = json.dumps(weather_test_data)
    plain_text = reducer.reduce_forecasts(weather_test_data)
    
    # Estimate tokens
    json_tokens = await estimate_tokens(json_str)
    text_tokens = await estimate_tokens(plain_text)

    # Calculate reduction
    reduction = (json_tokens["token_count"] - text_tokens["token_count"]) / json_tokens["token_count"] * 100

    # Should have significant reduction (>70%)
    assert reduction > 70, f"Token reduction was only {reduction:.1f}%, expected >70%"

    # Print the results for reference
    print(f"\nOriginal tokens: {json_tokens['token_count']}")
    print(f"Reduced tokens: {text_tokens['token_count']}")
    print(f"Reduction: {reduction:.1f}%")


def test_weather_gov_conversion():
    """Test converting Weather.gov JSON to plain text."""
    # Create a sample structure matching Weather.gov format
    weather_gov_data = {
        "properties": {
            "periods": [
                {
                    "name": "Tonight",
                    "temperature": 75,
                    "temperatureUnit": "F",
                    "shortForecast": "Partly Cloudy",
                    "probabilityOfPrecipitation": {"value": 20}
                },
                {
                    "name": "Tomorrow",
                    "temperature": 85,
                    "temperatureUnit": "F",
                    "shortForecast": "Sunny",
                    "probabilityOfPrecipitation": {"value": 0}
                }
            ]
        }
    }
    
    # Create a dictionary with this test data
    test_data = {"New York": weather_gov_data}
    
    # Get the reducer instance and convert to text
    reducer = WeatherTokenReducer()
    result = reducer.reduce_forecasts(test_data)
    
    # Check that the result contains expected values
    assert "New York:" in result
    assert "Tonight: 75°F, Partly Cloudy, 20% chance of precipitation" in result
    assert "Tomorrow: 85°F, Sunny, 0% chance of precipitation" in result
    
    # Explicitly check the temperature format includes the proper degree symbol
    assert "75°F" in result


def test_open_meteo_conversion():
    """Test converting OpenMeteo JSON to plain text."""
    # Create a sample structure matching OpenMeteo format
    open_meteo_data = {
        "temperature_unit": "°C",
        "daily": {
            "time": ["2023-05-01", "2023-05-02"],
            "temperature_2m_max": [22, 24],
            "temperature_2m_min": [15, 17],
            "weather_code": [1, 2],
            "precipitation_probability_max": [10, 30]
        }
    }
    
    # Create a dictionary with this test data
    test_data = {"London": open_meteo_data}
    
    # Get the reducer instance and convert to text
    reducer = WeatherTokenReducer()
    result = reducer.reduce_forecasts(test_data)
    
    # Check that the result contains expected values
    assert "London:" in result
    assert "05/01: High 22°C, Low 15°C, Mainly clear, 10% chance of precipitation" in result
    assert "05/02: High 24°C, Low 17°C, Partly cloudy, 30% chance of precipitation" in result


def test_handle_missing_precipitation():
    """Test handling missing precipitation data."""
    # Create a sample with missing precipitation data
    weather_gov_data = {
        "properties": {
            "periods": [
                {
                    "name": "Tonight",
                    "temperature": 70,
                    "temperatureUnit": "F",
                    "shortForecast": "Clear",
                    # No probabilityOfPrecipitation field
                }
            ]
        }
    }
    
    test_data = {"Chicago": weather_gov_data}
    reducer = WeatherTokenReducer()
    result = reducer.reduce_forecasts(test_data)
    
    # Check that it defaults to 0% instead of N/A
    assert "0% chance of precipitation" in result
    assert "N/A chance of precipitation" not in result


def test_format_for_llm_prompt(weather_test_data):
    """Test the format_for_llm_prompt method."""
    # Get the reducer instance
    reducer = WeatherTokenReducer()
    
    # Test with alerts included
    result_with_alerts = reducer.format_for_llm_prompt(weather_test_data, include_alerts=True)
    assert "New York:" in result_with_alerts
    
    # Test without alerts 
    result_no_alerts = reducer.format_for_llm_prompt(weather_test_data, include_alerts=False)
    assert "ALERTS:" not in result_no_alerts


def test_character_encoding():
    """Test that character encoding is handled properly, especially for degree symbols."""
    # Create test data with temperature values
    test_data = {
        "New York": {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 48,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "probabilityOfPrecipitation": {"value": 0}
                    }
                ]
            }
        }
    }
    
    reducer = WeatherTokenReducer()
    result = reducer.reduce_forecasts(test_data)
    
    # Check for proper degree symbol (°) encoding
    assert "48°F" in result
    
    # The bad encoding that would appear as "" in output
    bad_encoding = b'\xef\xbf\xbd\xef\xbf\xbd'.decode('utf-8')
    assert bad_encoding not in result


def test_city_data_handling(all_cities_fixture):
    """Test handling data for all configured cities."""
    if not all_cities_fixture:
        pytest.skip("No all_cities fixture available")
        
    reducer = WeatherTokenReducer()
    result = reducer.reduce_forecasts(all_cities_fixture)
    
    # Check that all expected cities are included
    for city in all_cities_fixture.keys():
        if isinstance(all_cities_fixture[city], dict) and "error" not in all_cities_fixture[city]:
            assert f"{city}:" in result
    
    # Check for encoding issues and precipitation formatting
    bad_encoding = b'\xef\xbf\xbd\xef\xbf\xbd'.decode('utf-8')
    assert bad_encoding not in result
    assert "N/A chance of precipitation" not in result


def test_tokyo_data_handling(all_cities_fixture):
    """Test specifically that Tokyo data is properly handled."""
    if 'Tokyo' not in all_cities_fixture:
        pytest.skip("Tokyo data not available in fixture")
        
    tokyo_data = {"Tokyo": all_cities_fixture["Tokyo"]}
    
    reducer = WeatherTokenReducer()
    result = reducer.reduce_forecasts(tokyo_data)
    
    # Check that Tokyo data is included with proper formatting
    assert "Tokyo:" in result
    
    # Check for proper temperature format and precipitation
    bad_encoding = b'\xef\xbf\xbd\xef\xbf\xbd'.decode('utf-8')
    assert bad_encoding not in result
    assert "N/A chance of precipitation" not in result


class TestWeatherTokenReducer(unittest.TestCase):
    """Test the WeatherTokenReducer class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.reducer = WeatherTokenReducer()
        
        # Load test data
        fixtures_path = Path(__file__).parent / "fixtures" / "weather-test-data.json"
        with open(fixtures_path, 'r', encoding='utf-8') as f:
            self.test_data = json.load(f)

    def test_weather_gov_conversion(self):
        """Test converting Weather.gov JSON to plain text."""
        # Create a sample structure matching Weather.gov format
        weather_gov_data = {
            "properties": {
                "periods": [
                    {
                        "name": "Tonight",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Partly Cloudy",
                        "probabilityOfPrecipitation": {"value": 20}
                    },
                    {
                        "name": "Tomorrow",
                        "temperature": 85,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "probabilityOfPrecipitation": {"value": 0}
                    }
                ]
            }
        }
        
        # Create a dictionary with this test data
        test_data = {"New York": weather_gov_data}
        
        # Convert to text
        result = self.reducer.reduce_forecasts(test_data)
        
        # Check that the result contains expected values
        self.assertIn("New York:", result)
        self.assertIn("Tonight: 75°F, Partly Cloudy, 20% chance of precipitation", result)
        self.assertIn("Tomorrow: 85°F, Sunny, 0% chance of precipitation", result)
        
        # Explicitly check the temperature format includes the proper degree symbol
        self.assertIn("75°F", result)
        
    def test_open_meteo_conversion(self):
        """Test converting OpenMeteo JSON to plain text."""
        # Create a sample structure matching OpenMeteo format
        open_meteo_data = {
            "temperature_unit": "°C",
            "daily": {
                "time": ["2023-05-01", "2023-05-02"],
                "temperature_2m_max": [22, 24],
                "temperature_2m_min": [15, 17],
                "weather_code": [1, 2],
                "precipitation_probability_max": [10, 30]
            }
        }
        
        # Create a dictionary with this test data
        test_data = {"London": open_meteo_data}
        
        # Convert to text
        result = self.reducer.reduce_forecasts(test_data)
        
        # Check that the result contains expected values
        self.assertIn("London:", result)
        self.assertIn("05/01: High 22°C, Low 15°C, Mainly clear, 10% chance of precipitation", result)
        self.assertIn("05/02: High 24°C, Low 17°C, Partly cloudy, 30% chance of precipitation", result)
        
    def test_handle_missing_precipitation(self):
        """Test handling missing precipitation data."""
        # Create a sample with missing precipitation data
        weather_gov_data = {
            "properties": {
                "periods": [
                    {
                        "name": "Tonight",
                        "temperature": 70,
                        "temperatureUnit": "F",
                        "shortForecast": "Clear",
                        # No probabilityOfPrecipitation field
                    }
                ]
            }
        }
        
        test_data = {"Chicago": weather_gov_data}
        result = self.reducer.reduce_forecasts(test_data)
        
        # Check that it defaults to 0% instead of N/A
        self.assertIn("0% chance of precipitation", result)
        self.assertNotIn("N/A chance of precipitation", result)
        
    def test_reduce_weather_dict(self):
        """Test reducing a weather dictionary."""
        # Use sample data
        weather_gov_data = {
            "properties": {
                "periods": [
                    {
                        "name": "Tonight",
                        "temperature": 65,
                        "temperatureUnit": "F",
                        "shortForecast": "Cloudy",
                        "probabilityOfPrecipitation": {"value": 40}
                    }
                ]
            }
        }
        
        test_data = {"Houston": weather_gov_data}
        result = self.reducer.reduce_weather_dict(test_data)
        
        # Check the structure has been simplified
        self.assertIn("Houston", result)
        self.assertIn("periods", result["Houston"])
        
        period = result["Houston"]["periods"][0]
        self.assertEqual(period["name"], "Tonight")
        self.assertEqual(period["temp"], 65)
        self.assertEqual(period["unit"], "F")
        self.assertEqual(period["forecast"], "Cloudy")
        self.assertEqual(period["precip"], 40)
        
    def test_daily_summary(self):
        """Test creating a daily summary."""
        # Use sample data
        weather_gov_data = {
            "properties": {
                "periods": [
                    {
                        "name": "Monday",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "isDaytime": True
                    },
                    {
                        "name": "Monday Night",
                        "temperature": 60,
                        "temperatureUnit": "F",
                        "shortForecast": "Clear",
                        "isDaytime": False
                    },
                    {
                        "name": "Tuesday",
                        "temperature": 80,
                        "temperatureUnit": "F",
                        "shortForecast": "Partly Cloudy",
                        "isDaytime": True
                    }
                ]
            }
        }
        
        test_data = {"Austin": weather_gov_data}
        result = self.reducer.get_daily_summary(test_data)
        
        # Check that it only includes daytime periods
        self.assertIn("Austin:", result)
        self.assertIn("Monday: 75°", result)
        self.assertIn("Tuesday: 80°", result)
        self.assertNotIn("Monday Night", result)  # Night periods should be excluded
        
    def test_llm_prompt_format(self):
        """Test formatting for LLM prompt."""
        # Use sample data with alerts
        weather_data = {
            "Miami": {
                "properties": {
                    "periods": [
                        {
                            "name": "Today",
                            "temperature": 90,
                            "temperatureUnit": "F",
                            "shortForecast": "Hot and Humid",
                            "probabilityOfPrecipitation": {"value": 30}
                        }
                    ]
                },
                "alerts": [
                    {
                        "headline": "Heat Advisory",
                        "severity": "Moderate"
                    }
                ]
            }
        }
        
        # Test with alerts
        result_with_alerts = self.reducer.format_for_llm_prompt(weather_data, include_alerts=True)
        self.assertIn("Miami:", result_with_alerts)
        self.assertIn("Today: 90°F", result_with_alerts)
        self.assertIn("ALERTS:", result_with_alerts)
        self.assertIn("Heat Advisory", result_with_alerts)
        
        # Test without alerts
        result_without_alerts = self.reducer.format_for_llm_prompt(weather_data, include_alerts=False)
        self.assertIn("Miami:", result_without_alerts)
        self.assertIn("Today: 90°F", result_without_alerts)
        self.assertNotIn("ALERTS:", result_without_alerts)
        
    def test_tokyo_data_handling(self):
        """Test specifically that Tokyo data is properly handled."""
        # Check if Tokyo data exists in test_data
        if 'Tokyo' in self.test_data:
            tokyo_data = {"Tokyo": self.test_data["Tokyo"]}
            result = self.reducer.reduce_forecasts(tokyo_data)
            
            # Print the result for debugging
            print("\nTokyo forecast output:")
            print(result)
            
            # Check that Tokyo data is included
            self.assertIn("Tokyo:", result)
            
            # Check that temperature format is correct (has proper degree symbol)
            self.assertNotIn("", result)  # Should not have encoding issues
            
            # Check that it correctly formats precipitation
            self.assertNotIn("N/A chance of precipitation", result)
    
    def test_handling_all_cities(self):
        """Test handling all cities in test data to ensure proper encoding and formatting."""
        # Process all cities
        result = self.reducer.reduce_forecasts(self.test_data)
        
        # Print first 500 characters for debugging
        print("\nSample of all forecasts (first 500 chars):")
        print(result[:500])
        
        # Check that all expected cities are included
        for city in self.test_data.keys():
            if isinstance(self.test_data[city], dict) and "error" not in self.test_data[city]:
                self.assertIn(f"{city}:", result)
        
        # Check for encoding issues
        self.assertNotIn("", result)
        
        # Check that precipitation is properly handled
        self.assertNotIn("N/A chance of precipitation", result)


if __name__ == "__main__":
    unittest.main()
