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


class OpenMeteoAPI(WeatherAPIHandler):
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_forecast(self, location: str):
        params = {
            "latitude": location.split(",")[0],
            "longitude": location.split(",")[1],
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
            "timezone": "auto",
        }
        async with aiohttp.ClientSession() as session, session.get(self.BASE_URL, params=params) as response:
            return await response.json()

    async def get_alerts(self, location: str):
        pass


class WeatherGovAPI(WeatherAPIHandler):
    BASE_URL = "https://api.weather.gov"

    def _validate_location_format(self, location: str):
        location = "".join(char for char in location if char.isdigit() or char == "," or char == "." or char == "-")
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
                if response.status != 200:
                    logger.error("Failed to retrieve gridpoint data: %s", await response.text())
                    response.raise_for_status()
                data = await response.json()
                forecast_url = data["properties"]["forecast"]
                logger.debug("Forecast URL retrieved: %s", forecast_url)
                return forecast_url
        except ValueError:
            logger.exception("Invalid location string: %s", location)
            raise
        except Exception as e:
            logger.exception("Error retrieving gridpoint data: %s", str(e))
            raise

    async def get_forecast(self, location: str):
        """Retrieve forecast data for a given location."""
        try:
            forecast_url = await self._get_gridpoint(location)
            async with self.session.get(forecast_url) as response:
                if response.status != 200:
                    logger.error("Failed to retrieve forecast data: %s", await response.text())
                    response.raise_for_status()
                forecast_data = await response.json()
                if "properties" not in forecast_data:
                    logger.error("Forecast data missing 'properties' key: %s", forecast_data)
                    raise KeyError("Forecast data missing 'properties' key")
                return forecast_data
        except Exception as e:
            logger.exception("Error retrieving forecast data: %s", str(e))
            raise

    async def get_alerts(self, location: str):
        """Retrieve alerts for a given location."""
        try:
            forecast_url = await self._get_gridpoint(location)
            alerts_url = forecast_url.replace("forecast", "alerts")
            async with self.session.get(alerts_url) as response:
                if response.status != 200:
                    logger.error("Failed to retrieve alerts data: %s", await response.text())
                    response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.exception("Error retrieving alerts data: %s", str(e))
            raise

    async def close(self):
        await self.session.close()


class WeatherAPIFactory:
    @staticmethod
    def create_weather_api_handler(api_type: str) -> WeatherAPIHandler:
        if api_type == "open-meteo":
            return OpenMeteoAPI()
        elif api_type == "weather-gov":
            return WeatherGovAPI()
        else:
            unsupported_api_message = f"Unsupported API type: {api_type}"
            raise ValueError(unsupported_api_message)
