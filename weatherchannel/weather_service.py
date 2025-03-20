from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

# Import config manager with fallback
try:
    from utilities.config_manager import ConfigManager
except ImportError:
    try:
        from cogs.utilities.config_manager import ConfigManager
    except ImportError:
        logging.warning("[WeatherService] Could not import ConfigManager")
        ConfigManager = object  # Use object as fallback

logger = logging.getLogger(__name__)

# Constants
HTTP_OK = 200
MAX_FORECAST_DAYS = 7

class WeatherService:

    """Service for retrieving and processing weather information from various APIs."""

    def __init__(self, config: ConfigManager | None = None):
        """
        Initialize the WeatherService.

        Args:
            config: Optional configuration manager

        """
        self.config = config
        self.session = None
        self.api_formatters = {}
        self._initialize_api_formatters()

    def _initialize_api_formatters(self):
        """
        Initialize formatters for each supported weather API.

        This sets up the formatters that will transform raw API responses into
        standardized weather data format.
        """
        # Map API types to their respective formatters
        self.api_formatters = {
            "openmeteo": self._format_openmeteo_response,
            "weathergov": self._format_weathergov_response,
        }
        logger.debug("[WeatherService] Initialized %d API formatters", len(self.api_formatters))

    async def _ensure_session(self):
        """
        Ensure that an aiohttp session exists.

        Creates a new session if one doesn't exist or if the existing one is closed.
        """
        if self.session is None or self.session.closed:
            logger.debug("[WeatherService] Creating new aiohttp session")
            self.session = aiohttp.ClientSession()

    async def fetch_weather(self, api_type: str, coords: tuple[float, float], city_name: str = "Unknown") -> dict[str, Any]:
        """
        Fetch and format weather data for a given location.

        Args:
            api_type: Type of weather API to use ('openmeteo' or 'weathergov')
            coords: Tuple of (latitude, longitude)
            city_name: Name of the city (for display/logging purposes)

        Returns:
            Formatted weather data dictionary

        """
        logger.debug("[WeatherService] Fetching weather for %s using %s API", city_name, api_type)
        try:
            # Get raw forecast data
            raw_data = await self.get_raw_forecast_for_city(api_type, coords, city_name)
            if not raw_data or "error" in raw_data:
                error_msg = raw_data.get("error", "Unknown error") if isinstance(raw_data, dict) else "No data returned"
                logger.warning("[WeatherService] Error fetching raw data for %s: %s",
                              city_name, error_msg)
                return {"error": error_msg}

            # Format the data
            formatter = self.api_formatters.get(api_type)
            if not formatter:
                logger.warning("[WeatherService] No formatter found for API type: %s", api_type)
                return {"error": f"Unsupported API type: {api_type}"}

            formatted_data = formatter(raw_data, city_name)
            if not formatted_data:
                logger.warning("[WeatherService] Failed to format data for %s", city_name)
                return {"error": "Data formatting failed"}

            logger.debug("[WeatherService] Successfully fetched and formatted weather for %s", city_name)
            return formatted_data

        except Exception as e:
            logger.exception("[WeatherService] Error in fetch_weather for %s", city_name)
            return {"error": f"Weather fetch failed: {str(e)}"}

    async def get_raw_forecast_for_city(self, api_type: str, coords: tuple[float, float], city_name: str) -> dict[str, Any]:
        """
        Get raw forecast data from the specified API.

        Args:
            api_type: Type of weather API to use
            coords: Tuple of (latitude, longitude)
            city_name: Name of the city

        Returns:
            Raw API response data

        """
        latitude, longitude = coords
        logger.debug("[WeatherService] Getting raw forecast for %s (%f, %f) using %s API",
                    city_name, latitude, longitude, api_type)

        try:
            # Ensure we have an active session
            await self._ensure_session()

            if api_type == "openmeteo":
                return await self._fetch_openmeteo_forecast(latitude, longitude)
            elif api_type == "weathergov":
                return await self._fetch_weathergov_forecast(latitude, longitude)
            else:
                logger.warning("[WeatherService] Unsupported API type: %s", api_type)
                return {"error": f"Unsupported API type: {api_type}"}

        except Exception as e:
            logger.exception("[WeatherService] Error getting forecast for %s", city_name)
            return {"error": f"API request failed: {str(e)}"}

    async def _fetch_openmeteo_forecast(self, latitude: float, longitude: float) -> dict[str, Any]:
        """
        Fetch forecast from Open-Meteo API.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Raw API response data

        """
        logger.debug("[WeatherService] Fetching from Open-Meteo API for coords (%f, %f)",
                    latitude, longitude)

        # Open-Meteo API parameters
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature",
                      "weather_code", "wind_speed_10m", "wind_direction_10m",
                      "precipitation"],
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min",
                    "precipitation_sum", "precipitation_probability_max"],
            "timezone": "auto",
            "forecast_days": MAX_FORECAST_DAYS
        }

        url = "https://api.open-meteo.com/v1/forecast"
        async with self.session.get(url, params=params) as response:
            if response.status != HTTP_OK:
                error_text = await response.text()
                logger.warning("[WeatherService] Open-Meteo API error: %d - %s",
                              response.status, error_text)
                return {"error": f"API returned status {response.status}: {error_text}"}

            data = await response.json()
            logger.debug("[WeatherService] Successfully retrieved Open-Meteo forecast")
            return data

    async def _fetch_weathergov_forecast(self, latitude: float, longitude: float) -> dict[str, Any]:
        """
        Fetch forecast from Weather.gov API.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Raw API response data

        """
        logger.debug("[WeatherService] Fetching from Weather.gov API for coords (%f, %f)",
                    latitude, longitude)

        # First, get the forecast office and grid coordinates
        points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
        try:
            async with self.session.get(points_url) as response:
                if response.status != HTTP_OK:
                    error_text = await response.text()
                    logger.warning("[WeatherService] Weather.gov points API error: %d - %s",
                                  response.status, error_text)
                    return {"error": f"Points API returned status {response.status}: {error_text}"}

                points_data = await response.json()

                # Extract the forecast URL from the points response
                forecast_url = points_data.get("properties", {}).get("forecast")
                hourly_forecast_url = points_data.get("properties", {}).get("forecastHourly")

                if not forecast_url or not hourly_forecast_url:
                    logger.warning("[WeatherService] Weather.gov API did not return forecast URLs")
                    return {"error": "Forecast URLs not found in points response"}

                # Fetch forecast data
                async with self.session.get(forecast_url) as forecast_response:
                    if forecast_response.status != HTTP_OK:
                        error_text = await forecast_response.text()
                        logger.warning("[WeatherService] Weather.gov forecast API error: %d - %s",
                                      forecast_response.status, error_text)
                        return {"error": f"Forecast API returned status {forecast_response.status}: {error_text}"}

                    forecast_data = await forecast_response.json()

                # Fetch hourly forecast data
                async with self.session.get(hourly_forecast_url) as hourly_response:
                    if hourly_response.status != HTTP_OK:
                        error_text = await hourly_response.text()
                        logger.warning("[WeatherService] Weather.gov hourly API error: %d - %s",
                                      hourly_response.status, error_text)
                        # Continue with just the daily forecast if hourly fails
                        hourly_data = {"error": f"Hourly API returned status {hourly_response.status}"}
                    else:
                        hourly_data = await hourly_response.json()

                # Combine the data
                result = {
                    "points": points_data,
                    "forecast": forecast_data,
                    "hourly": hourly_data
                }

                logger.debug("[WeatherService] Successfully retrieved Weather.gov forecast")
                return result

        except Exception as e:
            logger.exception("[WeatherService] Error fetching from Weather.gov API")
            return {"error": f"Weather.gov API request failed: {str(e)}"}

    def _format_openmeteo_response(self, data: dict[str, Any], city_name: str) -> dict[str, Any]:
        """
        Format Open-Meteo API response into a standardized structure.

        Args:
            data: Raw API response data
            city_name: Name of the city

        Returns:
            Formatted weather data

        """
        if not data or "error" in data:
            return {"error": data.get("error", "Invalid data from Open-Meteo API")}

        try:
            # Weather code mapping
            weather_codes = {
                0: {"description": "Clear sky", "icon": "☀️"},
                1: {"description": "Mainly clear", "icon": "🌤️"},
                2: {"description": "Partly cloudy", "icon": "⛅"},
                3: {"description": "Overcast", "icon": "☁️"},
                45: {"description": "Fog", "icon": "🌫️"},
                48: {"description": "Depositing rime fog", "icon": "🌫️"},
                51: {"description": "Light drizzle", "icon": "🌦️"},
                53: {"description": "Moderate drizzle", "icon": "🌧️"},
                55: {"description": "Dense drizzle", "icon": "🌧️"},
                56: {"description": "Light freezing drizzle", "icon": "🌨️"},
                57: {"description": "Dense freezing drizzle", "icon": "🌨️"},
                61: {"description": "Slight rain", "icon": "🌦️"},
                63: {"description": "Moderate rain", "icon": "🌧️"},
                65: {"description": "Heavy rain", "icon": "🌧️"},
                66: {"description": "Light freezing rain", "icon": "🌨️"},
                67: {"description": "Heavy freezing rain", "icon": "🌨️"},
                71: {"description": "Slight snow fall", "icon": "🌨️"},
                73: {"description": "Moderate snow fall", "icon": "🌨️"},
                75: {"description": "Heavy snow fall", "icon": "❄️"},
                77: {"description": "Snow grains", "icon": "❄️"},
                80: {"description": "Slight rain showers", "icon": "🌦️"},
                81: {"description": "Moderate rain showers", "icon": "🌧️"},
                82: {"description": "Violent rain showers", "icon": "🌧️"},
                85: {"description": "Slight snow showers", "icon": "🌨️"},
                86: {"description": "Heavy snow showers", "icon": "❄️"},
                95: {"description": "Thunderstorm", "icon": "⛈️"},
                96: {"description": "Thunderstorm with slight hail", "icon": "⛈️"},
                99: {"description": "Thunderstorm with heavy hail", "icon": "⛈️"}
            }

            # Extract current weather
            current = data.get("current", {})
            current_weather_code = current.get("weather_code")
            current_weather = weather_codes.get(current_weather_code, {"description": "Unknown", "icon": "❓"})

            # Extract daily forecast
            daily = data.get("daily", {})
            daily_weather_codes = daily.get("weather_code", [])
            daily_time = daily.get("time", [])
            daily_temp_max = daily.get("temperature_2m_max", [])
            daily_temp_min = daily.get("temperature_2m_min", [])
            daily_precip_sum = daily.get("precipitation_sum", [])
            daily_precip_prob = daily.get("precipitation_probability_max", [])

            # Build forecast data
            daily_forecast = []
            for i in range(min(len(daily_time), MAX_FORECAST_DAYS)):  # Ensure we get up to 7 days
                if i < len(daily_weather_codes) and i < len(daily_temp_max) and i < len(daily_temp_min):
                    weather_code = daily_weather_codes[i]
                    weather_info = weather_codes.get(weather_code, {"description": "Unknown", "icon": "❓"})

                    forecast_day = {
                        "date": daily_time[i] if i < len(daily_time) else "",
                        "temperature": {
                            "high": daily_temp_max[i] if i < len(daily_temp_max) else None,
                            "low": daily_temp_min[i] if i < len(daily_temp_min) else None,
                            "unit": "°C"
                        },
                        "condition": {
                            "description": weather_info["description"],
                            "icon": weather_info["icon"]
                        },
                        "precipitation": {
                            "amount": daily_precip_sum[i] if i < len(daily_precip_sum) else 0,
                            "probability": daily_precip_prob[i] if i < len(daily_precip_prob) else 0,
                            "unit": "mm"
                        }
                    }
                    daily_forecast.append(forecast_day)

            # Build the formatted response
            formatted_data = {
                "city": city_name,
                "current": {
                    "temperature": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "humidity": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "wind_direction": current.get("wind_direction_10m"),
                    "condition": {
                        "description": current_weather["description"],
                        "icon": current_weather["icon"]
                    },
                    "precipitation": current.get("precipitation", 0),
                    "units": {
                        "temperature": "°C",
                        "wind_speed": "km/h",
                        "precipitation": "mm"
                    }
                },
                "forecast": daily_forecast,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "Open-Meteo"
            }

            return formatted_data

        except Exception as e:
            logger.exception("[WeatherService] Error formatting Open-Meteo data")
            return {"error": f"Data formatting failed: {str(e)}"}

    def _format_weathergov_response(self, data: dict[str, Any], city_name: str) -> dict[str, Any]:
        """
        Format Weather.gov API response into a standardized structure.

        Args:
            data: Raw API response data
            city_name: Name of the city

        Returns:
            Formatted weather data

        """
        if not data or "error" in data:
            return {"error": data.get("error", "Invalid data from Weather.gov API")}

        try:
            # Extract forecast data
            forecast_data = data.get("forecast", {}).get("properties", {}).get("periods", [])
            hourly_data = data.get("hourly", {}).get("properties", {}).get("periods", [])

            if not forecast_data:
                return {"error": "No forecast periods found in Weather.gov response"}

            # Get current conditions from the first hourly period
            current = {}
            if hourly_data and len(hourly_data) > 0:
                first_hour = hourly_data[0]
                current = {
                    "temperature": first_hour.get("temperature"),
                    "feels_like": None,  # Not provided directly by Weather.gov
                    "humidity": None,    # Not provided directly in this response
                    "wind_speed": self._parse_wind_speed(first_hour.get("windSpeed", "")),
                    "wind_direction": first_hour.get("windDirection"),
                    "condition": {
                        "description": first_hour.get("shortForecast", ""),
                        "icon": self._map_weathergov_icon(first_hour.get("shortForecast", ""))
                    },
                    "precipitation": None,  # Not provided directly
                    "units": {
                        "temperature": "°F" if first_hour.get("temperatureUnit") == "F" else "°C",
                        "wind_speed": "mph",  # Weather.gov uses mph
                        "precipitation": "in"  # Weather.gov uses inches
                    }
                }
            else:
                # Fallback to the first forecast period if no hourly data
                if len(forecast_data) > 0:
                    first_period = forecast_data[0]
                    current = {
                        "temperature": first_period.get("temperature"),
                        "feels_like": None,
                        "humidity": None,
                        "wind_speed": self._parse_wind_speed(first_period.get("windSpeed", "")),
                        "wind_direction": first_period.get("windDirection"),
                        "condition": {
                            "description": first_period.get("shortForecast", ""),
                            "icon": self._map_weathergov_icon(first_period.get("shortForecast", ""))
                        },
                        "precipitation": None,
                        "units": {
                            "temperature": "°F" if first_period.get("temperatureUnit") == "F" else "°C",
                            "wind_speed": "mph",
                            "precipitation": "in"
                        }
                    }

            # Process forecast periods into daily format
            # Weather.gov provides periods for day and night separately
            daily_forecast = []

            # Group by day - each day has a day and night period
            for i in range(0, min(14, len(forecast_data)), 2):
                day_period = forecast_data[i] if i < len(forecast_data) else None
                night_period = forecast_data[i+1] if i+1 < len(forecast_data) else None

                if not day_period:
                    continue

                # Parse date from the start time
                forecast_date = day_period.get("startTime", "").split("T")[0] if day_period else ""

                # Extract temperatures
                high_temp = day_period.get("temperature") if day_period else None
                low_temp = night_period.get("temperature") if night_period else None

                # Extract conditions - use day period's conditions
                condition_desc = day_period.get("shortForecast", "") if day_period else ""
                condition_icon = self._map_weathergov_icon(condition_desc)

                # Create forecast day entry
                forecast_day = {
                    "date": forecast_date,
                    "temperature": {
                        "high": high_temp,
                        "low": low_temp,
                        "unit": "°F" if day_period.get("temperatureUnit") == "F" else "°C"
                    },
                    "condition": {
                        "description": condition_desc,
                        "icon": condition_icon
                    },
                    "precipitation": {
                        "amount": None,  # Not provided directly by Weather.gov
                        "probability": self._extract_precipitation_probability(day_period.get("detailedForecast", "")),
                        "unit": "in"
                    }
                }
                daily_forecast.append(forecast_day)

                # Limit to 7 days
                if len(daily_forecast) >= MAX_FORECAST_DAYS:
                    break

            # Build the formatted response
            formatted_data = {
                "city": city_name,
                "current": current,
                "forecast": daily_forecast,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "Weather.gov"
            }

            return formatted_data

        except Exception as e:
            logger.exception("[WeatherService] Error formatting Weather.gov data")
            return {"error": f"Data formatting failed: {str(e)}"}

    def _parse_wind_speed(self, wind_speed_str: str) -> int | None:
        """
        Parse wind speed from Weather.gov format (e.g., '10 mph').

        Args:
            wind_speed_str: Wind speed string from Weather.gov

        Returns:
            Wind speed as an integer, or None if parsing fails

        """
        try:
            if not wind_speed_str:
                return None

            # Extract the numeric part
            parts = wind_speed_str.split()
            if len(parts) > 0:
                return int(parts[0])
            else:
                return None
        except (ValueError, IndexError):
            return None

    def _map_weathergov_icon(self, condition: str) -> str:
        """
        Map Weather.gov condition to an emoji icon.

        Args:
            condition: Weather condition description

        Returns:
            Emoji icon representing the weather condition

        """
        condition = condition.lower()

        if "thunderstorm" in condition:
            return "⛈️"
        elif "rain" in condition and "snow" in condition:
            return "🌨️"
        elif "rain" in condition or "shower" in condition:
            if "light" in condition:
                return "🌦️"
        else:
                return "🌧️"
        elif "snow" in condition:
            return "❄️"
        elif "sleet" in condition or "ice" in condition:
            return "🌨️"
        elif "fog" in condition or "haze" in condition:
            return "🌫️"
        elif "cloud" in condition:
            if "partly" in condition:
                return "⛅"
            else:
                return "☁️"
        elif "clear" in condition or "sunny" in condition:
            return "☀️"
        else:
            return "❓"

    def _extract_precipitation_probability(self, detailed_forecast: str) -> int | None:
        """
        Extract precipitation probability from detailed forecast text.

        Args:
            detailed_forecast: Detailed forecast text from Weather.gov

        Returns:
            Precipitation probability as an integer percentage, or None if not found

        """
        try:
            if not detailed_forecast:
                return None

            # Look for patterns like "Chance of precipitation is 30%"
            if "chance of precipitation is " in detailed_forecast.lower():
                parts = detailed_forecast.lower().split("chance of precipitation is ")
                if len(parts) > 1:
                    percentage_part = parts[1].split("%")[0].strip()
                    return int(percentage_part)

            # Alternative patterns
            import re
            match = re.search(r'(\d+)% chance', detailed_forecast.lower())
            if match:
                return int(match.group(1))

            return None
        except (ValueError, IndexError):
            return None

    async def close(self):
        """Close the HTTP session if it exists."""
        if self.session and not self.session.closed:
            logger.debug("[WeatherService] Closing aiohttp session")
            await self.session.close()
