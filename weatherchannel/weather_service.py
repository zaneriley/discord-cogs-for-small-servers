import asyncio
import logging
from typing import Dict, Any

from .weather_api import WeatherAPIFactory
from .weather_formatter import (
    WeatherFormatter,
    OpenMeteoFormatter,
    WeatherGovFormatter,
)

logger = logging.getLogger(__name__)


class WeatherService:
    def __init__(self, strings):
        self.api_handlers = {}
        self.strings = strings
        # Remove the service-level formatter initialization
        # We'll create formatters per API type as needed

    def _create_formatter(self, api_type: str) -> WeatherFormatter:
        """Create appropriate formatter based on API type."""
        if api_type == "open-meteo":
            formatter = OpenMeteoFormatter()
        elif api_type == "weather-gov":
            formatter = WeatherGovFormatter()
        else:
            error_msg = f"Unsupported API type: {api_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        return WeatherFormatter(formatter=formatter)

    async def fetch_weather(self, api_type: str, coords, city: str):
        """Fetch and format weather data for given coordinates."""
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
            return weather_formatter.format_individual_forecast(weather_data, city)

        except ValueError as e:
            logger.error("Formatter creation failed: %s", str(e))
            return {"error": str(e)}
        except Exception:
            logger.exception("Error processing forecast for %s:", city)
            return {
                "error": self.strings["errors"]["service"]["weather_fetch_error"].format(
                    city=city
                )
            }