"""
Convert JSON weather data to Markdown.
This implementation provides a custom markdown conversion specifically designed for weather data.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# We'll still try to import MarkItDown for compatibility, but we won't use it
MARKITDOWN_AVAILABLE = False
try:
    from markitdown import MarkItDown
    logger.debug("[JSON-MD] MarkItDown library available, but using custom converter instead")
    MARKITDOWN_AVAILABLE = True
except ImportError:
    logger.debug("[JSON-MD] MarkItDown library not available - using custom converter")

def json_to_markdown_weather_summary(weather_json: dict[str, Any]) -> str:
    """
    Convert weather JSON data to Markdown format.

    Args:
        weather_json: Dictionary containing weather data

    Returns:
        Markdown formatted string representation of the weather data

    """
    logger.debug("[JSON-MD] Converting weather data to markdown, input size: %d bytes",
                len(json.dumps(weather_json)) if weather_json else 0)

    if not weather_json or "all_cities" not in weather_json:
        logger.warning("[JSON-MD] Empty or invalid weather data passed to markdown converter")
        return ""

    logger.debug("[JSON-MD] Converting data with %d cities",
                len(weather_json.get("all_cities", {})))

    # Log sample of the first city data to help diagnose issues
    first_city = next(iter(weather_json.get("all_cities", {}).items()), ("None", {}))
    logger.debug("[JSON-MD] First city: %s, sample data: %s",
                first_city[0],
                json.dumps(first_city[1], ensure_ascii=False)[:100] if first_city[1] else "{}")

    try:
        # Create markdown document
        markdown = "# Weekly Weather Summary\n\n"

        # Add timestamp if available
        if "timestamp" in weather_json:
            markdown += f"**Report Time**: {weather_json['timestamp']}\n\n"

        # Add overall summary intro
        num_cities = len(weather_json.get("all_cities", {}))
        markdown += f"This report covers weather conditions for {num_cities} {'city' if num_cities == 1 else 'cities'} with daily forecasts for the coming week.\n\n"

        # Process each city
        for city, city_data in weather_json["all_cities"].items():
            logger.debug("[JSON-MD] Processing city: %s", city)
            markdown += f"## {city}\n\n"

            # Check if we have the "current" structure from Open-Meteo API
            if "current" in city_data:
                current = city_data["current"]
                markdown += "### Current Conditions\n\n"

                # Temperature
                if "temperature_2m" in current:
                    temp = current["temperature_2m"]
                    markdown += f"- Temperature: {temp}\n"

                # Feels like
                if "apparent_temperature" in current:
                    feels_like = current["apparent_temperature"]
                    markdown += f"- Feels like: {feels_like}\n"

                # Humidity
                if "relative_humidity_2m" in current:
                    humidity = current["relative_humidity_2m"]
                    markdown += f"- Humidity: {humidity}\n"

                # Wind
                if "wind_speed_10m" in current:
                    wind = current["wind_speed_10m"]
                    markdown += f"- Wind: {wind}\n"

                markdown += "\n"
            # Check if we have the simpler structure
            elif any(k in city_data for k in ["temp", "humidity", "conditions"]):
                logger.debug("[JSON-MD] Found simplified city data structure")
                markdown += "### Current Conditions\n\n"

                # Temperature
                if "temp" in city_data:
                    markdown += f"- Temperature: {city_data['temp']}\n"

                # Humidity
                if "humidity" in city_data:
                    markdown += f"- Humidity: {city_data['humidity']}\n"

                # Conditions
                if "conditions" in city_data:
                    markdown += f"- Conditions: {city_data['conditions']}\n"

                markdown += "\n"

            # Daily forecast if available
            if "daily" in city_data:
                daily = city_data["daily"]

                # Check how many days are in the forecast
                num_days = 0
                if "time" in daily and isinstance(daily["time"], list):
                    num_days = len(daily["time"])
                elif "temperature_2m_max" in daily and isinstance(daily["temperature_2m_max"], list):
                    num_days = len(daily["temperature_2m_max"])

                if num_days > 1:
                    markdown += f"### Weekly Forecast ({num_days} days)\n\n"
                else:
                    markdown += "### Forecast\n\n"

                # Get dates if available
                dates = daily.get("time", [])

                # Temperature highs
                if "temperature_2m_max" in daily:
                    highs = daily["temperature_2m_max"]
                    for i, high in enumerate(highs):
                        date = dates[i] if i < len(dates) else f"Day {i+1}"
                        markdown += f"- **{date}**: High {high}"

                        # Add low if available
                        if "temperature_2m_min" in daily and i < len(daily["temperature_2m_min"]):
                            low = daily["temperature_2m_min"][i]
                            markdown += f", Low {low}"

                        # Add precipitation if available
                        if "precipitation_probability_max" in daily and i < len(daily["precipitation_probability_max"]):
                            precip = daily["precipitation_probability_max"][i]
                            markdown += f", Precipitation: {precip}%"

                        # Add weather code if available
                        if "weather_code" in daily and i < len(daily["weather_code"]):
                            weather_code = daily["weather_code"][i]
                            conditions = _get_weather_code_description(weather_code)
                            markdown += f", {conditions}"

                        markdown += "\n"

                markdown += "\n"

                # Add weekly trend analysis if we have multiple days
                if num_days > 2:
                    markdown += "#### Weekly Trend\n\n"

                    # Temperature trend
                    if "temperature_2m_max" in daily and len(daily["temperature_2m_max"]) > 2:
                        temps = daily["temperature_2m_max"]
                        if temps[0] < temps[-1]:
                            markdown += "- Temperatures trending warmer throughout the week\n"
                        elif temps[0] > temps[-1]:
                            markdown += "- Temperatures trending cooler throughout the week\n"
                        else:
                            markdown += "- Temperatures remaining stable throughout the week\n"

                    # Precipitation trend
                    if "precipitation_probability_max" in daily and len(daily["precipitation_probability_max"]) > 2:
                        precip = daily["precipitation_probability_max"]
                        if any(p > 50 for p in precip):
                            markdown += "- Significant precipitation expected during the week\n"
                        elif any(p > 20 for p in precip):
                            markdown += "- Some precipitation possible during the week\n"
                        else:
                            markdown += "- Mostly dry conditions expected throughout the week\n"

                    markdown += "\n"

            # Add a separator between cities
            markdown += "---\n\n"

        logger.debug("[JSON-MD] Generated %d chars of markdown", len(markdown))
        logger.debug("[JSON-MD] Markdown sample: %s",
                    markdown[:200] + ("..." if len(markdown) > 200 else ""))

        return markdown

    except Exception as e:
        logger.exception("[JSON-MD] Error converting JSON to markdown: %s", e)
        return ""

def _get_weather_code_description(code):
    """Convert Open-Meteo weather codes to human-readable descriptions."""
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }

    try:
        code_int = int(code)
        return weather_codes.get(code_int, f"Weather code: {code}")
    except (ValueError, TypeError):
        return f"Weather code: {code}"
