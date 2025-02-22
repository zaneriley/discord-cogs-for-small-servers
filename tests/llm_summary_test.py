#!/usr/bin/env python3
import asyncio
import json
import logging
import os
from pathlib import Path

from cogs.weatherchannel.weather_service import WeatherService
from cogs.weatherchannel.config import ConfigManager
from cogs.weatherchannel.weather_formatter import WeatherGovFormatter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main(test_data_path: str = None):
    """Test harness for LLM weather summaries
    
    Args:
        test_data_path (str, optional): Path to JSON file with sample forecast data
    """
    # Load environment config
    guild_id = int(os.getenv("GUILD_ID"))
    strings_path = Path(__file__).parent.parent / "cogs/weatherchannel/strings.json"
    with open(strings_path) as f:
        strings = json.load(f)

    # Initialize services
    config_manager = ConfigManager(guild_id, None)
    weather_service = WeatherService(strings)
    formatter = WeatherGovFormatter(strings)

    if test_data_path:
        # Load test data from file
        with open(test_data_path) as f:
            test_forecasts = json.load(f)
        logger.info("Using test data from: %s", test_data_path)
    else:
        # Fetch real weather data
        default_locations = await config_manager.get_default_locations(guild_id)
        test_forecasts = await asyncio.gather(*[
            weather_service.fetch_weather(api_type, coords, city)
            for city, (api_type, coords) in default_locations.items()
        ])
        logger.info("Fetched live weather data")

    # Generate and display summary
    summary = await formatter.generate_llm_summary([
        f for f in test_forecasts 
        if isinstance(f, dict) and "error" not in f
    ])
    
    print("\n" + "="*50)
    print("WEATHER SUMMARY TEST OUTPUT")
    print("="*50)
    print(summary or "No summary generated")
    print("="*50 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Test LLM weather summaries')
    parser.add_argument('--test-data', help='Path to JSON test data file')
    args = parser.parse_args()
    
    asyncio.run(main(args.test_data)) 