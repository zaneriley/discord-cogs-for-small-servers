import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import ClassVar

from cogs.utilities.llm.llm_utils import create_llm_chain

logger = logging.getLogger(__name__)

class CityCodes:
    codes: ClassVar[dict[str, str]] = {
        "Austin": "AUS",
        "Chicago": "CHI",
        "Houston": "HOU",
        "Dallas": "DAL",
        "San Antonio": "SAT",
        "San Francisco": "SF",
        "New York City": "NYC",
        "Los Angeles": "LA",
        "San Diego": "SAN",
        "Portland": "PDX",
        "Denver": "DEN",
        "London": "LDN",
        "Paris": "PAR",
        "Washington, D.C.": "DCA",
        "Miami": "MIA",
        "Atlanta": "ATL",
        "Philadelphia": "PHL",
        "Washington": "WAS",
        "Cleveland": "CLE",
        "Detroit": "DET",
        "Minneapolis": "MN",
        "St. Louis": "STL",
        "Pittsburgh": "PIT",
        "Baltimore": "BD",
        "Columbus": "COL",
        "Indianapolis": "IND",
        "Milwaukee": "MKE",
        "Memphis": "MEM",
        "Nashville": "NAS",
    }


class WeatherFormatterInterface(ABC):
    @abstractmethod
    def format_individual_forecast(self, weather_data, city_name=None):
        pass

    @abstractmethod
    def format_alerts(self, alerts):
        pass


class OpenMeteoFormatter(WeatherFormatterInterface):
    def format_individual_forecast(self, weather_data, city_name=None):
        temperature = weather_data["hourly"]["temperature_2m"][0]
        condition = "Sunny"  # Map weather codes to conditions
        if city_name:
            return f"☀ {city_name}: {condition}, {temperature}°C"
        return f"{condition}, {temperature}°C"

    def format_alerts(self, alerts):
        # Implement formatting for OpenMeteoAPI alerts
        pass


class WeatherGovFormatter(WeatherFormatterInterface):
    def __init__(self, strings):
        self.icon_map = {
            "Sunny": "☀",
            "Clear": "◯",
            "Mostly Sunny": "☼",
            "Partly Sunny": "◔",
            "Mostly Cloudy": "☁",
            "Cloudy": "●",
            "Rain Showers": "☂",
            "Chance Rain Showers": "☂",
            "Slight Chance Rain Showers": "☂",
            "Thunderstorms": "☇",
            "Chance Thunderstorms": "☇",
            "Slight Chance Thunderstorms": "☇",
            "Snow": "❄",
            "Chance Snow": "❄",
            "Slight Chance Snow": "❄",
            "Fog": "🌫",  # This is a two-character Unicode symbol for fog
            "Haze": "☈",
            "Windy": "💨",
            "Hot": "♨",
            "Cold": "❆",
            "Partly Cloudy": "◒",  # Similar to partly sunny but emphasizes clouds
            "Light Rain": "☂",
            "Heavy Rain": "☔",
            "Light Snow": "❄",
            "Heavy Snow": "☃",
            "Freezing Rain": "❆",  # Represents freezing conditions
            "Sleet": "❆",
            "Flurries": "❄",
            "Scattered Showers": "☔",
            "Isolated Showers": "☔",
            "Scattered Thunderstorms": "☇",
            "Isolated Thunderstorms": "☇",
            # Additional or less common conditions:
            "Breezy": "💨",
            "Blustery": "💨",
            "Wintry Mix": "❆",
            "Dust": "💨",  # Represents blowing dust
            "Smoke": "🌫",
            "Frigid": "❆",
            "Warm": "♨",
        }
        self.llm_chain = create_llm_chain()
        self.strings = strings

    def format_individual_forecast(self, weather_data, city_name=None):
        if not weather_data:
            logger.error("No weather data provided.")
            return "Weather data not available."

        if "properties" not in weather_data:
            logger.error("Weather data is missing 'properties' key: %s", weather_data)
            return "Incomplete weather data."

        try:
            now = datetime.now(tz=UTC)
            current_date = now.strftime("%Y-%m-%d")

            periods = weather_data["properties"].get("periods", [])
            if not periods:
                logger.error("No 'periods' key found in 'properties' of weather data.")
                return "No forecast available for today."

            daytime_period = None
            nighttime_period = None
            for period in periods:
                if current_date in period["startTime"]:
                    if period["isDaytime"]:
                        daytime_period = period
                    else:
                        nighttime_period = period

            if not daytime_period or not nighttime_period:
                logger.info("No matching period found for today's date and time.")
                return "No forecast available for today."

            city_code = CityCodes.codes.get(city_name, city_name)
            short_forecast = daytime_period["shortForecast"].capitalize()
            temperature_f_high = daytime_period["temperature"]
            temperature_c_high = round((temperature_f_high - 32) * 5 / 9)
            temperature_f_low = nighttime_period["temperature"]
            temperature_c_low = round((temperature_f_low - 32) * 5 / 9)
            precipitation_value = daytime_period.get("probabilityOfPrecipitation", {}).get("value", "0")
            if precipitation_value is None or precipitation_value == "None":
                precipitation = " 0%"
            else:
                precipitation = f"{precipitation_value}%"

            detailed_data = {
                "current_temp": daytime_period["temperature"],
                "conditions": daytime_period["detailedForecast"],
                "wind": daytime_period["windSpeed"],
                "humidity": daytime_period["relativeHumidity"]["value"],
                "uv_index": daytime_period.get("uvIndex", "N/A")
            }

            forecast = {
                "ᴄɪᴛʏ": f"{city_code}  ",
                "ᴄᴏɴᴅ": f"{short_forecast}  ",
                "ʜ°ᴄ": f"{temperature_c_high}°  ",
                "ʟ°ᴄ": f"{temperature_c_low}°  ",
                "ᴘʀᴇᴄɪᴘ": f"{precipitation}",
                "ᴅᴇᴛᴀɪʟs": json.dumps(detailed_data)  # Store for summary generation
            }
        except KeyError:
            logger.exception("Missing key in weather data:")
            return "Incomplete weather data."
        except Exception:
            logger.exception("Unexpected error while formatting forecast:")
            return "Error processing weather data."
        else:
            return forecast

    def format_alerts(self, alerts):
        # Implement formatting for WeatherGovAPI alerts
        pass

    async def generate_llm_summary(self, forecasts: list) -> str:
        max_retries = 3
        retry_delay = 1  # seconds

        try:
            consolidated_data = "\n".join(
                f"{f['ᴄɪᴛʏ'].strip()}: {json.loads(f.get('ᴅᴇᴛᴀɪʟs','{}'))}"
                for f in forecasts
            )

            for attempt in range(max_retries):
                try:
                    response = await self.llm_chain.run(
                        self.strings["prompts"]["weather_summary"].format(data=consolidated_data),
                        temperature=0.3
                    )
                    return f"\n**AI Weather Summary**\n{response.content}"
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"LLM summary attempt {attempt+1} failed: {e!s}. Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        continue
                    raise
        except Exception as e:
            logger.exception(f"LLM summary failed after {max_retries} attempts: {e!s}")
            return ""


class WeatherFormatter:
    def __init__(self, formatter: WeatherFormatterInterface):
        self.formatter = formatter

    def format_individual_forecast(self, weather_data, city_name=None):
        return self.formatter.format_individual_forecast(weather_data, city_name)

    def format_alerts(self, alerts):
        return self.formatter.format_alerts(alerts)
