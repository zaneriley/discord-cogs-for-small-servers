"""
Simplified test to check if the OpenMeteoAPI is returning 7-day forecasts.
"""
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test")

# Import our markdown converter
sys.path.append("C:/Users/Zane/repos/dev-discord-bot")
try:
    from cogs.utilities.llm.json_to_markdown import json_to_markdown_weather_summary
    logger.info("Successfully imported markdown converter")
except ImportError as e:
    logger.exception(f"Failed to import markdown converter: {e}")
    # Simple fallback if import fails
    def json_to_markdown_weather_summary(data):
        return json.dumps(data, indent=2)

# Simple implementation of the API handler
import aiohttp


async def get_forecast(coords):
    """Fetch weather forecast for the given coordinates."""
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    # Parse location coordinates
    lat, lon = map(float, coords.split(","))
    logger.debug(f"Fetching forecast for coordinates {lat},{lon}")

    # Set up parameters for OpenMeteo API
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m"
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max"
        ],
        "timezone": "auto",
        "forecast_days": 7
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL, params=params) as response:
            response.raise_for_status()
            return await response.json()

def process_weather_data(api_data, city_name):
    """Process raw API data into our internal format."""
    # Weather code map for condition descriptions
    weather_code_map = {
        0: {"condition": "Clear sky", "icon": "☀️"},
        1: {"condition": "Mainly clear", "icon": "🌤️"},
        2: {"condition": "Partly cloudy", "icon": "⛅"},
        3: {"condition": "Overcast", "icon": "☁️"},
        45: {"condition": "Fog", "icon": "🌫️"},
        48: {"condition": "Depositing rime fog", "icon": "🌫️"},
        51: {"condition": "Light drizzle", "icon": "🌦️"},
        53: {"condition": "Moderate drizzle", "icon": "🌦️"},
        55: {"condition": "Dense drizzle", "icon": "🌧️"},
        56: {"condition": "Light freezing drizzle", "icon": "🌨️"},
        57: {"condition": "Dense freezing drizzle", "icon": "🌨️"},
        61: {"condition": "Slight rain", "icon": "🌦️"},
        63: {"condition": "Moderate rain", "icon": "🌧️"},
        65: {"condition": "Heavy rain", "icon": "🌧️"},
        66: {"condition": "Light freezing rain", "icon": "🌨️"},
        67: {"condition": "Heavy freezing rain", "icon": "🌨️"},
        71: {"condition": "Slight snow fall", "icon": "🌨️"},
        73: {"condition": "Moderate snow fall", "icon": "❄️"},
        75: {"condition": "Heavy snow fall", "icon": "❄️"},
        77: {"condition": "Snow grains", "icon": "❄️"},
        80: {"condition": "Slight rain showers", "icon": "🌦️"},
        81: {"condition": "Moderate rain showers", "icon": "🌧️"},
        82: {"condition": "Violent rain showers", "icon": "⛈️"},
        85: {"condition": "Slight snow showers", "icon": "🌨️"},
        86: {"condition": "Heavy snow showers", "icon": "❄️"},
        95: {"condition": "Thunderstorm", "icon": "⛈️"},
        96: {"condition": "Thunderstorm with slight hail", "icon": "⛈️"},
        99: {"condition": "Thunderstorm with heavy hail", "icon": "⛈️"}
    }

    # Initialize result structure
    result = {
        "city": city_name
    }

    # Add current weather data
    if "current" in api_data:
        current = {}
        for key in api_data["current"]:
            current[key] = api_data["current"][key]

        # Add condition description
        if "weather_code" in current:
            code = current["weather_code"]
            weather_info = weather_code_map.get(code, {"condition": "Unknown", "icon": "❓"})
            current["condition"] = weather_info["condition"]
            current["icon"] = weather_info["icon"]

        result["current"] = current

    # Add daily forecast data
    if "daily" in api_data:
        daily = {}

        # Copy all arrays
        for key in api_data["daily"]:
            daily[key] = api_data["daily"][key]

        # Add condition descriptions
        if "weather_code" in daily:
            conditions = []
            icons = []
            for code in daily["weather_code"]:
                weather_info = weather_code_map.get(code, {"condition": "Unknown", "icon": "❓"})
                conditions.append(weather_info["condition"])
                icons.append(weather_info["icon"])
            daily["conditions"] = conditions
            daily["icons"] = icons

        result["daily"] = daily

    # Add legacy fields for backward compatibility
    if "current" in api_data:
        result["temp"] = f"{api_data['current']['temperature_2m']}°C"

        if "weather_code" in api_data["current"]:
            code = api_data["current"]["weather_code"]
            weather_info = weather_code_map.get(code, {"condition": "Unknown", "icon": "❓"})
            result["conditions"] = weather_info["condition"]
            result["icon"] = weather_info["icon"]

    if "daily" in api_data and len(api_data["daily"]["temperature_2m_max"]) > 0:
        result["high"] = api_data["daily"]["temperature_2m_max"][0]
        result["low"] = api_data["daily"]["temperature_2m_min"][0]

        if "precipitation_probability_max" in api_data["daily"]:
            result["precipitation"] = f"{api_data['daily']['precipitation_probability_max'][0]}%"

    return result

async def main():
    """Test script main function."""
    # Focus on New York (US) and Tokyo for comparison
    cities = {
        "New York": "40.7128,-74.0060",
        "Tokyo": "35.6762,139.6503"
    }

    try:
        all_cities_data = {}

        for city_name, coords in cities.items():
            # Fetch weather data
            weather_data = await get_forecast(coords)

            # Process into our format
            processed_data = process_weather_data(weather_data, city_name)
            all_cities_data[city_name] = processed_data

            # Print detailed info about this city's data
            days = len(processed_data["daily"]["time"])

            # Print current conditions

            # Print daily forecast
            for i in range(days):
                processed_data["daily"]["time"][i]
                processed_data["daily"]["temperature_2m_max"][i]
                processed_data["daily"]["temperature_2m_min"][i]
                processed_data["daily"]["precipitation_probability_max"][i]
                processed_data["daily"]["conditions"][i]


        # Create consolidated data structure
        consolidated_data = {
            "all_cities": all_cities_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Save processed data
        with open("processed_weather_data.json", "w") as f:
            json.dump(consolidated_data, f, indent=2)

        # Convert to markdown
        markdown = json_to_markdown_weather_summary(consolidated_data)

        # Save markdown
        with open("weather_report.md", "w") as f:
            f.write(markdown)

        # Print the full markdown - don't truncate

        return True

    except Exception:
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
