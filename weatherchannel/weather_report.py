"""
Weather report module for aggregating weather data across multiple cities.

This module provides functionality to collect weather data from multiple cities
and consolidate it into a single report.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

# Import LLM chain creation utility with fallback
try:
    from cogs.utilities.llm.json_to_markdown import json_to_markdown_weather_summary
    from cogs.utilities.llm.llm_utils import create_llm_chain
except ImportError:
    logging.warning("[WeatherReportService] Could not import LLM utilities - LLM features will be disabled")
    def create_llm_chain():
        return None
    # Create stub for json_to_markdown_weather_summary
    def json_to_markdown_weather_summary(data: dict) -> str:
        return f"Weather data for {len(data.get('all_cities', {}))} cities"

logger = logging.getLogger(__name__)


class WeatherReportService:

    """
    Service for generating consolidated weather reports across multiple cities.
    """

    def __init__(self, weather_service, llm_provider=None, llm_chain=None):
        """
        Initialize the WeatherReportService.

        Args:
            weather_service: The weather service to use for fetching weather data
            llm_provider: Optional LLM provider to use for generating summaries
            llm_chain: Optional pre-configured LLM chain

        """
        self.weather_service = weather_service
        self.llm_provider = llm_provider

        # Create LLM chain if not provided
        if llm_chain:
            self.llm_chain = llm_chain
        elif llm_provider:
            logger.debug("[WeatherReportService] Creating LLM chain with provider %s",
                        type(llm_provider).__name__)
            self.llm_chain = create_llm_chain(
                provider=llm_provider,
                system_prompt=(
                    "You are WeatherBot, an assistant that provides weather information. "
                    "You'll be given current weather conditions and forecasts for various cities. "
                    "Analyze this data and create a natural-sounding weather report that highlights "
                    "important conditions and interesting patterns across different locations."
                )
            )
        else:
            logger.warning("[WeatherReportService] No LLM provider - narrative summaries disabled")
            self.llm_chain = None

    async def get_consolidated_weather_data(self, locations_data: dict[str, tuple[str, tuple[float, float]]]) -> dict[str, Any]:
        """
        Collect weather data for all cities and consolidate into a single JSON structure.

        This method fetches weather information for all cities in parallel and combines
        the results into a single JSON object with an "all_cities" key containing all city data.

        Args:
            locations_data: Dictionary mapping city names to (api_type, coords) tuples

        Returns:
            A dictionary with an "all_cities" key containing all weather data

        Example response structure:
        {
            "all_cities": {
                "New York": { weather data for New York },
                "San Francisco": { weather data for San Francisco }
            },
            "timestamp": "2023-01-01T12:00:00Z"
        }

        """
        logger.debug("[WeatherReportService] Getting consolidated weather data for %d locations",
                    len(locations_data))
        # Prepare tasks for fetching each city's weather in parallel
        city_tasks = {}
        for city_name, (api_type, coords) in locations_data.items():
            logger.debug("[WeatherReportService] Creating task for %s using %s API",
                        city_name, api_type)
            city_tasks[city_name] = self.weather_service.fetch_weather(api_type, coords, city_name)

        # Execute all tasks and gather results
        all_cities_data = {}
        for city_name, task in city_tasks.items():
            # To avoid try-except within loop (PERF203), extract result first
            result = None
            try:
                result = await task
            except Exception:
                logger.exception("[WeatherReportService] Error fetching weather for %s", city_name)
                continue

            # Process result outside of try-except
            if result and isinstance(result, dict) and "error" not in result:
                all_cities_data[city_name] = result
            else:
                error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else "Non-dictionary result"
                logger.warning("[WeatherReportService] Skipping %s due to error: %s",
                              city_name, error_msg)

        # Create the consolidated response
        current_time = datetime.now(timezone.utc).isoformat()
        logger.debug("[WeatherReportService] Consolidated data for %d cities (out of %d requested)",
                    len(all_cities_data), len(locations_data))
        return {
            "all_cities": all_cities_data,
            "timestamp": current_time
        }

    async def generate_weather_summary(self, locations_data: dict[str, tuple[str, tuple[float, float]]]) -> str | None:
        """
        Generate a natural language summary of weather conditions across multiple cities.

        This method:
        1. Fetches consolidated weather data for all cities
        2. Converts the data to markdown format
        3. Processes the markdown through an LLM to generate a natural language summary

        Args:
            locations_data: Dictionary mapping city names to (api_type, coords) tuples

        Returns:
            A natural language summary of the weather conditions, or None if LLM processing is not available

        """
        logger.debug("[WeatherReportService] Generating weather summary for %d locations",
                    len(locations_data))
        if not self.llm_chain:
            logger.warning("[WeatherReportService] LLM chain not configured - cannot generate weather summary")
            return None

        content = None
        try:
            # Get consolidated weather data
            weather_data = await self.get_consolidated_weather_data(locations_data)
            logger.debug("[WeatherReportService] Consolidated weather data contains %d cities",
                        len(weather_data.get("all_cities", {})))

            # Convert to markdown
            logger.debug("[WeatherReportService] Converting weather data to markdown format")
            markdown_data = json_to_markdown_weather_summary(weather_data)
            if not markdown_data:
                logger.warning("[WeatherReportService] No markdown data generated")
                return None

            logger.debug("[WeatherReportService] Generated markdown data (length: %d chars)",
                        len(markdown_data))

            # Process through LLM chain
            logger.debug("[WeatherReportService] Sending to LLM for processing")
            response = await self.llm_chain.run(markdown_data)
            if response.error:
                logger.error("[WeatherReportService] Error generating weather summary: %s",
                            response.error_message)
                return None

            logger.debug("[WeatherReportService] Successfully generated weather narrative (length: %d chars)",
                        len(response.content))
            content = response.content

        except Exception:
            logger.exception("[WeatherReportService] Error generating weather summary")
            return None

        return content
