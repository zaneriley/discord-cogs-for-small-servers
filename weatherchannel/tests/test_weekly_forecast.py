"""
Test script to verify that we're fetching and processing weekly forecast data correctly.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("weekly-forecast-test")

# Add root directory to path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

# Import modules
from cogs.utilities.llm.json_to_markdown import json_to_markdown_weather_summary
from cogs.weatherchannel.weather_api import OpenMeteoAPI
from cogs.weatherchannel.weather_formatter import OpenMeteoFormatter


async def test_weekly_forecast():
    """Test fetching and processing weekly forecast data."""
    logger.info("Testing weekly forecast data")

    # Test coordinates (New York City)
    coords = "40.7128,-74.0060"
    city_name = "New York"

    # Create API handler
    api = OpenMeteoAPI()

    try:
        # Fetch weather data
        logger.info(f"Fetching weather data for {city_name}")
        weather_data = await api.get_forecast(coords)

        # Log some basic info about the data
        logger.info(f"Received data with keys: {list(weather_data.keys())}")
        if "daily" in weather_data:
            logger.info(f"Daily data keys: {list(weather_data['daily'].keys())}")
            logger.info(f"Number of forecast days: {len(weather_data['daily']['time'])}")
            logger.info(f"Forecast dates: {weather_data['daily']['time']}")

        # Process the data using the formatter
        logger.info("Processing data with OpenMeteoFormatter")
        formatter = OpenMeteoFormatter()
        processed_data = formatter._extract_forecast_data(weather_data, city_name)

        # Check that we have multiple days of forecast data
        if "daily" in processed_data:
            daily = processed_data["daily"]
            logger.info(f"Processed data has {len(daily.get('time', []))} days of forecast")
            logger.info(f"Daily high temperatures: {daily.get('temperature_2m_max', [])}")
            logger.info(f"Daily low temperatures: {daily.get('temperature_2m_min', [])}")
            logger.info(f"Daily conditions: {daily.get('conditions', [])}")
        else:
            logger.warning("No daily forecast data in processed result")

        # Create a consolidated data structure like what would be used in the weather report
        consolidated_data = {
            "all_cities": {
                city_name: processed_data
            },
            "timestamp": "2023-03-20T12:00:00Z"
        }

        # Convert to markdown
        logger.info("Converting to markdown")
        markdown = json_to_markdown_weather_summary(consolidated_data)

        # Print the markdown
        logger.info(f"Generated markdown ({len(markdown)} chars):")

        return True
    except Exception as e:
        logger.exception(f"Error: {e}")
        return False
    finally:
        # Close API handler session
        if hasattr(api, "session") and api.session:
            await api.session.close()

if __name__ == "__main__":
    success = asyncio.run(test_weekly_forecast())
    sys.exit(0 if success else 1)
