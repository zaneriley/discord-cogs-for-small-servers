import logging
from abc import ABC, abstractmethod

import aiohttp

logger = logging.getLogger(__name__)


class WeatherAPIHandler(ABC):
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    @abstractmethod
    async def get_forecast(self, location: str):
        pass

    @abstractmethod
    async def get_alerts(self, location: str):
        pass

    def _reraise_exception(self, e: Exception, message: str, location: str):
        """Helper function to log and re-raise exceptions."""
        logger.exception(f"{message} for location %s: %s", location, str(e))
        raise ValueError(message) from e


class OpenMeteoAPI(WeatherAPIHandler):
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_forecast(self, location: str):
        # Parse location coordinates
        try:
            lat, lon = map(float, location.split(","))
            logger.debug(f"OpenMeteoAPI: Fetching forecast for coordinates {lat},{lon}")
        except (ValueError, IndexError):
            error_msg = f"Invalid coordinates format: {location}. Expected 'latitude,longitude'"
            logger.exception(error_msg)
            raise ValueError(error_msg) from None

        # Set up parameters for OpenMeteo API with more comprehensive data
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "is_day",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m"
            ],
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_direction_10m"
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "apparent_temperature_max",
                "apparent_temperature_min",
                "sunrise",
                "sunset",
                "precipitation_sum",
                "precipitation_probability_max"
            ],
            "timezone": "auto",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                    return await response.json()
        except aiohttp.ClientError as e:
            self._reraise_exception(e, "Error fetching forecast from Open-Meteo API", location)

    async def get_alerts(self, location: str):
        # Open-Meteo API doesn't have explicit alerts in the same way as weather.gov, so this is a placeholder.
        logger.warning("Alerts are not supported by Open-Meteo API.")


class WeatherGovAPI(WeatherAPIHandler):
    BASE_URL = "https://api.weather.gov"

    def _validate_location_format(self, location: str):
        location = "".join(char for char in location if char.isdigit() or char in (",", ".", "-"))
        parts = location.split(",")
        if len(parts) != 2:
            lat_long_error = f"Location format error: Expected 'lat,lon', got '{location}'"
            raise ValueError(lat_long_error)
        return map(float, parts)  # returns a tuple of (lat, lon)

    async def _get_gridpoint(self, location: str):
        """Helper function to get gridpoint for a location."""
        try:
            lat, lon = self._validate_location_format(location)
            endpoint = f"/points/{lat},{lon}"
            async with self.session.get(self.BASE_URL + endpoint) as response:
                response.raise_for_status()
                data = await response.json()
                forecast_url = data["properties"]["forecast"]
                logger.debug("Forecast URL retrieved: %s", forecast_url)
                return forecast_url
        except ValueError as e:  # Catch specific ValueError
            self._reraise_exception(e, "Invalid location string", location)
        except aiohttp.ClientError as e:  # Catch specific aiohttp ClientError
            self._reraise_exception(e, "Error retrieving gridpoint data", location)
        except KeyError as e: # Catch specific KeyError if 'properties' or 'forecast' is missing
            self._reraise_exception(e, "Data structure error - missing key while retrieving gridpoint", location)
        except Exception as e:  # Catch any other unexpected exceptions
            self._reraise_exception(e, "Unexpected error during _get_gridpoint", location)


    async def get_forecast(self, location: str):
        """Retrieve forecast data for a given location."""
        try:
            forecast_url = await self._get_gridpoint(location)
            async with self.session.get(forecast_url) as response:
                response.raise_for_status()
                forecast_data = await response.json()
                if "properties" not in forecast_data:
                    logger.error("Forecast data missing 'properties' key: %s", forecast_data)
                    msg = "Forecast data missing 'properties' key"
                    raise KeyError(msg)
                return forecast_data
        except aiohttp.ClientError as e:  # Catch specific aiohttp ClientError
            self._reraise_exception(e, "Error retrieving forecast data", location)
        except KeyError as e: # Catch specific KeyError if 'properties' is missing in forecast data
            self._reraise_exception(e, "Data structure error - Forecast data missing 'properties' key", location)
        except Exception as e:  # Catch any other unexpected exceptions
            self._reraise_exception(e, "Error retrieving forecast data", location)


    async def get_alerts(self, location: str):
        """Retrieve alerts for a given location."""
        try:
            forecast_url = await self._get_gridpoint(location)
            async with self.session.get(forecast_url) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:  # Catch specific aiohttp ClientError
            self._reraise_exception(e, "Error retrieving alerts data", location)
        except Exception as e:  # Catch any other unexpected exceptions
            self._reraise_exception(e, "Error retrieving alerts data", location)


    async def close(self):
        await self.session.close()


class WeatherAPIFactory:
    @staticmethod
    def create_weather_api_handler(api_type: str) -> WeatherAPIHandler:
        if api_type == "open-meteo":
            return OpenMeteoAPI()
        if api_type == "weather-gov":
            return WeatherGovAPI()
        unsupported_api_message = f"Unsupported API type: {api_type}"
        raise ValueError(unsupported_api_message)
