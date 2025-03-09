import asyncio
import json
import logging
from datetime import UTC, datetime
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
                logger.warning("OpenMeteo formatter doesn't have _extract_forecast_data method!")

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

    async def get_weather_summary_from_raw(self, raw_forecasts: dict) -> str:
        """
        Generate an AI summary from raw weather data.

        This method uses the raw data format provided by fetch_raw_data_for_summary
        to generate a more detailed and accurate weather summary.

        Args:
            raw_forecasts: Dictionary of city names to their raw weather data

        Returns:
            Generated summary text

        """
        try:
            # Create formatter using the first available API type
            first_api_type = next(iter(self.api_handlers))
            formatter = self._create_formatter(first_api_type)

            # Check if formatter supports raw data summaries
            if hasattr(formatter.formatter, "generate_llm_summary_from_raw"):
                return await formatter.formatter.generate_llm_summary_from_raw(raw_forecasts)

            # Fall back to converting raw data to the format expected by the existing method
            logger.warning("Formatter doesn't support raw data summaries, converting to compatible format")

            # Convert raw data to compatible format
            compatible_forecasts = self._convert_raw_to_compatible_format(raw_forecasts)

            # Use existing summary method
            if hasattr(formatter.formatter, "generate_llm_summary"):
                return await formatter.formatter.generate_llm_summary(compatible_forecasts)

            logger.error("Formatter does not support any LLM summaries")
            return ""

        except Exception as e:
            logger.exception(f"Weather summary from raw data error: {e!s}")
            return ""

    def _convert_raw_to_compatible_format(self, raw_forecasts: dict) -> list:
        """
        Convert raw weather data to a format compatible with the existing summary method.

        Args:
            raw_forecasts: Dictionary of city names to their raw weather data

        Returns:
            List of formatted forecast dictionaries as expected by generate_llm_summary

        """
        compatible_forecasts = []

        for city_name, raw_data in raw_forecasts.items():
            # Skip entries with errors
            if "error" in raw_data:
                continue

            # Get API type from metadata
            api_type = raw_data.get("_meta", {}).get("api_type")
            if not api_type:
                logger.warning(f"Missing API type in raw data for {city_name}, skipping")
                continue

            # Extract relevant data based on API type
            if api_type == "open-meteo":
                try:
                    # Extract data similar to what _extract_forecast_data would produce
                    temp_max = round(raw_data["daily"]["temperature_2m_max"][0])
                    temp_min = round(raw_data["daily"]["temperature_2m_min"][0])

                    # Get weather code for condition
                    weather_code = raw_data["daily"]["weather_code"][0]

                    # Create a simplified detailed data object
                    current = raw_data.get("current", {})

                    detailed_data = {
                        "current_temp": round(current.get("temperature_2m", temp_max)),
                        "feels_like": round(current.get("apparent_temperature", temp_max)),
                        "conditions": f"Weather code: {weather_code}",
                        "wind_speed": f"{current.get('wind_speed_10m', 0)} km/h",
                        "humidity": f"{current.get('relative_humidity_2m', 0)}%",
                        "high": temp_max,
                        "low": temp_min,
                        "precipitation": f"{raw_data['daily'].get('precipitation_probability_max', [0])[0]}%",
                    }

                    # Create compatible forecast entry
                    compatible_forecast = {
                        "ᴄɪᴛʏ": f"{city_name}  ",
                        "ᴅᴇᴛᴀɪʟs": json.dumps(detailed_data)
                    }

                    compatible_forecasts.append(compatible_forecast)

                except (KeyError, IndexError) as e:
                    logger.exception(f"Error converting raw OpenMeteo data for {city_name}: {e!s}")

            elif api_type == "weather-gov":
                try:
                    # Extract data from Weather.gov format
                    periods = raw_data.get("properties", {}).get("periods", [])
                    if periods:
                        day_period = next((p for p in periods if p.get("isDaytime", True)), periods[0])
                        night_period = next((p for p in periods if not p.get("isDaytime", True)), None)

                        temp_max = day_period.get("temperature", 0)
                        temp_min = night_period.get("temperature", 0) if night_period else temp_max - 10

                        detailed_data = {
                            "current_temp": temp_max,
                            "conditions": day_period.get("shortForecast", ""),
                            "wind_speed": day_period.get("windSpeed", ""),
                            "humidity": f"{day_period.get('relativeHumidity', {}).get('value', 0)}%",
                            "high": temp_max,
                            "low": temp_min,
                            "precipitation": f"{day_period.get('probabilityOfPrecipitation', {}).get('value', 0)}%",
                        }

                        # Create compatible forecast entry
                        compatible_forecast = {
                            "ᴄɪᴛʏ": f"{city_name}  ",
                            "ᴅᴇᴛᴀɪʟs": json.dumps(detailed_data)
                        }

                        compatible_forecasts.append(compatible_forecast)

                except (KeyError, IndexError) as e:
                    logger.exception(f"Error converting raw Weather.gov data for {city_name}: {e!s}")

        return compatible_forecasts

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

    async def fetch_raw_data_for_summary(self, city: str, locations_data: dict[str, tuple[str, tuple[float, float]]]) -> dict[str, Any]:
        """
        Fetch raw weather data from APIs with minimal processing to prepare for summary generation.

        This method retrieves the raw API responses but adds some metadata and normalization
        to make the data easier to work with for summarization, while preserving the original
        structure and richness of the API responses.

        Args:
            city: Name of the city to fetch data for, or "Everywhere" for all cities
            locations_data: Dictionary mapping city names to (api_type, coords) tuples

        Returns:
            Dictionary of city names to their minimally processed raw weather data

        """
        result_data = {}

        # Determine which cities to fetch data for
        if city == "Everywhere":
            cities_to_fetch = list(locations_data.keys())
        else:
            # Try to match the city name (case-insensitive)
            matched_city = None
            for loc in locations_data:
                if loc.lower() == city.lower():
                    matched_city = loc
                    break

            if matched_city:
                cities_to_fetch = [matched_city]
            else:
                # City not found, return error
                return {city: {"error": f"City '{city}' not found in configured locations"}}

        # Fetch data for each city
        for city_name in cities_to_fetch:
            api_type, coords = locations_data[city_name]

            # Get the API handler
            if api_type not in self.api_handlers:
                self.api_handlers[api_type] = WeatherAPIFactory.create_weather_api_handler(api_type)

            # Get raw forecast with error handling
            try:
                coords_str = ",".join(map(str, coords))
                handler = self.api_handlers[api_type]
                raw_forecast = await handler.get_forecast(coords_str)

                # Apply minimal normalization based on API type
                normalized_data = self._normalize_raw_data_for_summary(raw_forecast, api_type, city_name)
                result_data[city_name] = normalized_data

            except Exception as e:
                logger.exception("Error retrieving raw forecast data for %s: %s", city_name, str(e))
                result_data[city_name] = {"error": str(e)}

        return result_data

    def _normalize_raw_data_for_summary(self, raw_data: dict, api_type: str, city_name: str) -> dict:
        """
        Apply minimal normalization to raw data to ensure consistency across providers.

        This preserves the original data structure while adding a few standardized fields
        to help with summary generation.

        Args:
            raw_data: The raw API response data
            api_type: The type of API (e.g., "open-meteo", "weather-gov")
            city_name: The name of the city

        Returns:
            Minimally normalized data that preserves the original structure

        """
        # Start with a shallow copy of the raw data
        normalized = dict(raw_data)

        # Add metadata fields common to all providers
        normalized["_meta"] = {
            "api_type": api_type,
            "city_name": city_name,
            "processed_time": datetime.now(UTC).isoformat()
        }

        # Add units metadata based on API type
        if api_type == "open-meteo":
            normalized["temperature_unit"] = "°C"
            normalized["precipitation_unit"] = "mm"
            normalized["wind_speed_unit"] = "km/h"
        elif api_type == "weather-gov":
            # Extract units from the data if available
            if "properties" in raw_data and "periods" in raw_data["properties"] and raw_data["properties"]["periods"]:
                first_period = raw_data["properties"]["periods"][0]
                normalized["temperature_unit"] = f"°{first_period.get('temperatureUnit', 'F')}"
                normalized["precipitation_unit"] = "%"
                normalized["wind_speed_unit"] = first_period.get("windSpeed", "").split()[-1] if "windSpeed" in first_period else "mph"
            else:
                # Default units for Weather.gov
                normalized["temperature_unit"] = "°F"
                normalized["precipitation_unit"] = "%"
                normalized["wind_speed_unit"] = "mph"

        return normalized
