import asyncio
import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(name)s:%(message)s"
)
logger = logging.getLogger("test")

# Add parent directory to path so we can import modules directly
parent_dir = str(Path(__file__).parent.parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

async def test_weather_report():
    """Test the WeatherReportService's ability to generate reports."""
    try:
        # Import modules within the function to avoid circular imports
        from cogs.weatherchannel.weather_report import WeatherReportService
        
        # Create a mock weather service
        class MockWeatherService:
            async def fetch_weather(self, api_type, coords, city_name):
                if city_name == "New York":
                    return {
                        "city": "New York",
                        "current": {
                            "temperature": 15,
                            "feels_like": 14,
                            "humidity": 65,
                            "condition": {
                                "description": "Partly Cloudy",
                                "icon": "⛅"
                            }
                        },
                        "forecast": [
                            {
                                "date": "2025-03-20",
                                "temperature": {
                                    "high": 18,
                                    "low": 8,
                                    "unit": "°C"
                                },
                                "condition": {
                                    "description": "Partly Cloudy",
                                    "icon": "⛅"
                                },
                                "precipitation": {
                                    "probability": 20,
                                    "unit": "%"
                                }
                            },
                            {
                                "date": "2025-03-21",
                                "temperature": {
                                    "high": 20,
                                    "low": 10,
                                    "unit": "°C"
                                },
                                "condition": {
                                    "description": "Sunny",
                                    "icon": "☀️"
                                },
                                "precipitation": {
                                    "probability": 5,
                                    "unit": "%"
                                }
                            }
                        ]
                    }
                elif city_name == "Tokyo":
                    return {
                        "city": "Tokyo",
                        "current": {
                            "temperature": 22,
                            "feels_like": 21,
                            "humidity": 70,
                            "condition": {
                                "description": "Clear",
                                "icon": "☀️"
                            }
                        },
                        "forecast": [
                            {
                                "date": "2025-03-20",
                                "temperature": {
                                    "high": 25,
                                    "low": 15,
                                    "unit": "°C"
                                },
                                "condition": {
                                    "description": "Clear",
                                    "icon": "☀️"
                                },
                                "precipitation": {
                                    "probability": 0,
                                    "unit": "%"
                                }
                            },
                            {
                                "date": "2025-03-21",
                                "temperature": {
                                    "high": 24,
                                    "low": 14,
                                    "unit": "°C"
                                },
                                "condition": {
                                    "description": "Rain",
                                    "icon": "🌧️"
                                },
                                "precipitation": {
                                    "probability": 80,
                                    "unit": "%"
                                }
                            }
                        ]
                    }
                else:
                    return {"error": f"Unknown city: {city_name}"}
        
        # Create instances
        mock_service = MockWeatherService()
        report_service = WeatherReportService(mock_service)
        
        # Define test locations
        locations_data = {
            "New York": ("openmeteo", (40.7128, -74.006)),
            "Tokyo": ("openmeteo", (35.6762, 139.6503)),
        }
        
        # Test the consolidated data function
        logger.info("Testing consolidated data function...")
        consolidated_data = await report_service.get_consolidated_weather_data(locations_data)
        
        # Check the results
        assert "all_cities" in consolidated_data
        assert "timestamp" in consolidated_data
        assert "New York" in consolidated_data["all_cities"]
        assert "Tokyo" in consolidated_data["all_cities"]
        
        nyc_data = consolidated_data["all_cities"]["New York"]
        assert nyc_data["current"]["temperature"] == 15
        assert len(nyc_data["forecast"]) == 2
        
        tokyo_data = consolidated_data["all_cities"]["Tokyo"]
        assert tokyo_data["current"]["temperature"] == 22
        assert tokyo_data["forecast"][1]["condition"]["description"] == "Rain"
        
        logger.info("✅ Consolidated data test passed!")
        
        # Test with an error city
        error_locations = {
            "New York": ("openmeteo", (40.7128, -74.006)),
            "Error City": ("openmeteo", (0, 0)),
        }
        
        error_data = await report_service.get_consolidated_weather_data(error_locations)
        assert "New York" in error_data["all_cities"]
        assert "Error City" not in error_data["all_cities"]
        
        logger.info("✅ Error handling test passed!")
        
        # Save consolidated data for inspection
        with open("weather_consolidated_data.json", "w") as f:
            json.dump(consolidated_data, f, indent=2)
            
        logger.info("✅ All tests passed! See weather_consolidated_data.json for the data.")
        return True
        
    except Exception as e:
        logger.exception("Error in test_weather_report")
        return False

if __name__ == "__main__":
    asyncio.run(test_weather_report()) 