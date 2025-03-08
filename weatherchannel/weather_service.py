import asyncio
import logging
import json
from typing import Any, Optional

from .config import ConfigManager
from .weather_api import WeatherAPIFactory
from .weather_formatter import (
    OpenMeteoFormatter,
    WeatherFormatter,
    WeatherGovFormatter,
)

logger = logging.getLogger(__name__)


class WeatherService:
    def __init__(self, strings, config: Optional[ConfigManager] = None):
        self.api_handlers = {}
        self.strings = strings
        self.config = config
        # Remove the service-level formatter initialization
        # We'll create formatters per API type as needed

    def _create_formatter(self, api_type: str) -> WeatherFormatter:
        """Create appropriate formatter based on API type."""
        if api_type == "open-meteo":
            formatter = OpenMeteoFormatter()
        elif api_type == "weather-gov":
            formatter = WeatherGovFormatter(self.strings)
        else:
            error_msg = f"Unsupported API type: {api_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        return WeatherFormatter(formatter=formatter)

    async def fetch_weather(self, api_type: str, coords, city: str):
        """Fetch and format weather data for given coordinates."""
        logger.info(f"Fetching weather for {city} using {api_type}")
        
        if api_type not in self.api_handlers:
            self.api_handlers[api_type] = WeatherAPIFactory.create_weather_api_handler(api_type)

        try:
            # Create formatter for this API type
            weather_formatter = self._create_formatter(api_type)

            # Validate coordinates
            if not isinstance(coords, tuple) or len(coords) != 2:
                logger.error("Invalid coordinates format: %s", coords)
                return {
                    "error": self.strings["errors"]["service"]["invalid_coords_format"].format(
                        city=city
                    )
                }

            # Convert coordinates to string format
            try:
                coords_str = ",".join(map(str, map(float, coords)))
            except ValueError:
                logger.exception("Error converting coordinates to float for %s:", city)
                return {
                    "error": self.strings["errors"]["service"]["coords_conversion_error"].format(
                        city=city
                    )
                }

            # Fetch and format weather data
            weather_data = await self.api_handlers[api_type].get_forecast(coords_str)
            if city == "Tokyo":
                logger.debug(f"Tokyo raw data structure: {json.dumps(weather_data)[:1000]}...")

            # Handle different formatter types and extract data
            if api_type == "open-meteo":
                # For OpenMeteo API, we need to use the _extract_forecast_data method
                if hasattr(weather_formatter.formatter, "_extract_forecast_data"):
                    result = weather_formatter.formatter._extract_forecast_data(weather_data, city)
                    if city == "Tokyo":
                        logger.info(f"Tokyo formatted data: {result}")
                    return result
                else:
                    logger.warning(f"OpenMeteo formatter doesn't have _extract_forecast_data method!")

            # Default formatting for other APIs
            return weather_formatter.format_individual_forecast(weather_data, city)

        except ValueError as e:
            logger.exception("Formatter creation failed: %s", str(e))
            return {"error": str(e)}
        except Exception:
            logger.exception("Error processing forecast for %s:", city)
            return {
                "error": self.strings["errors"]["service"]["weather_fetch_error"].format(
                    city=city
                )
            }

    async def fetch_all_locations_weather(self, locations_data: dict[str, tuple[str, tuple[float, float]]]) -> list[dict[str, Any]]:
        """
        Fetch weather data for multiple locations and format as individual forecasts.

        Args:
            locations_data: Dictionary mapping city names to (api_type, coords) tuples

        Returns:
            List of formatted forecast dictionaries, filtering out error responses

        """
        forecasts = await asyncio.gather(
            *[self.fetch_weather(api_type, coords, city_name)
              for city_name, (api_type, coords) in locations_data.items()]
        )

        # Filter out error responses for display
        return [f for f in forecasts if isinstance(f, str) or (isinstance(f, dict) and "error" not in f)]

    async def fetch_city_weather(self, city: str, locations_data: dict[str, tuple[str, tuple[float, float]]]) -> Optional[dict[str, Any]]:
        """
        Fetch weather data for a specific city.

        Args:
            city: Name of the city to fetch weather for
            locations_data: Dictionary mapping city names to (api_type, coords) tuples

        Returns:
            Formatted forecast dictionary or None if city not found

        """
        # Case-insensitive city lookup
        for location_name, (api_type, coords) in locations_data.items():
            if location_name.lower() == city.lower():
                return await self.fetch_weather(api_type, coords, location_name)

        return None

    async def get_weather_summary(self, forecasts: list) -> str:
        """Get AI-generated weather summary"""
        try:
            first_api_type = next(iter(self.api_handlers))  # Get first handler type
            formatter = self._create_formatter(first_api_type)

            # The generate_llm_summary method is directly on the formatter.formatter object
            if hasattr(formatter.formatter, "generate_llm_summary"):
                return await formatter.formatter.generate_llm_summary(forecasts)
            logger.error("Formatter does not support LLM summaries")
            return ""
        except Exception as e:
            logger.exception(f"Weather summary error: {e!s}")
            return ""

    async def format_forecast_table(self, forecasts: list[dict[str, Any]], include_condition: bool = False) -> str:
        """
        Format a list of forecasts into a table string.

        Args:
            forecasts: List of formatted forecast dictionaries
            include_condition: Whether to include the condition column

        Returns:
            Formatted table string

        """
        if not forecasts:
            return self.strings["errors"]["service"]["no_weather_data"]

        # Get the formatter for the first API type we have a handler for
        try:
            first_api_type = next(iter(self.api_handlers))
            formatter = self._create_formatter(first_api_type)
            return formatter.format_forecast_table(forecasts, include_condition)
        except (StopIteration, ValueError):
            logger.exception("No API handlers available to create a formatter")
            return self.strings["errors"]["service"]["no_formatter_available"]

    async def fetch_raw_weather_data(self, city: str, locations_data: dict[str, tuple[str, tuple[float, float]]]) -> dict[str, Any]:
        """
        Fetch raw, unformatted weather data for debugging.

        Args:
            city: Name of the city to fetch data for, or "Everywhere" for all cities
            locations_data: Dictionary mapping city names to (api_type, coords) tuples

        Returns:
            Raw weather data dictionary

        """
        raw_data = {}

        if city == "Everywhere":
            # Fetch raw weather data for all locations
            for city_name, (api_type, coords) in locations_data.items():
                # Get the handler
                if api_type not in self.api_handlers:
                    self.api_handlers[api_type] = WeatherAPIFactory.create_weather_api_handler(api_type)

                # Get raw forecast
                try:
                    coords_str = ",".join(map(str, coords))
                    handler = self.api_handlers[api_type]
                    raw_forecast = await handler.get_forecast(coords_str)
                    raw_data[city_name] = raw_forecast
                except Exception as e:
                    logger.exception("Error retrieving raw forecast data for %s: %s", city_name, str(e))
                    raw_data[city_name] = {"error": str(e)}
        else:
            # Try to match the city name (case-insensitive)
            matched_city = None
            for loc in locations_data:
                if loc.lower() == city.lower():
                    matched_city = loc
                    break

            if matched_city:
                api_type, coords = locations_data[matched_city]

                # Get the handler
                if api_type not in self.api_handlers:
                    self.api_handlers[api_type] = WeatherAPIFactory.create_weather_api_handler(api_type)

                # Get raw forecast
                try:
                    coords_str = ",".join(map(str, coords))
                    handler = self.api_handlers[api_type]
                    raw_data = await handler.get_forecast(coords_str)
                except Exception as e:
                    logger.exception("Error retrieving raw forecast data for %s: %s", city, str(e))
                    raw_data = {"error": str(e)}
            else:
                raw_data = {"error": f"City '{city}' not found in configured locations"}

        return raw_data
