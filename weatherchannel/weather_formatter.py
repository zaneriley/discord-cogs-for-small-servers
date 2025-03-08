import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar
import re

from utilities.llm.llm_utils import create_llm_chain
from utilities.text_formatting_utils import format_row, get_max_widths

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

    @abstractmethod
    def format_forecast_table(self, forecasts: list[dict[str, Any]], include_condition: bool = False) -> str:
        """Format a list of forecasts into a table string."""


class OpenMeteoFormatter(WeatherFormatterInterface):
    def __init__(self):
        # Weather code mapping for OpenMeteo
        # From https://open-meteo.com/en/docs/
        self.weather_code_map = {
            0: {"condition": "Clear sky", "icon": "☀"},
            1: {"condition": "Mainly clear", "icon": "🌤"},
            2: {"condition": "Partly cloudy", "icon": "⛅"},
            3: {"condition": "Overcast", "icon": "☁"},
            45: {"condition": "Fog", "icon": "🌫"},
            48: {"condition": "Depositing rime fog", "icon": "🌫"},
            51: {"condition": "Light drizzle", "icon": "🌦"},
            53: {"condition": "Moderate drizzle", "icon": "🌦"},
            55: {"condition": "Dense drizzle", "icon": "🌧"},
            56: {"condition": "Light freezing drizzle", "icon": "🌨"},
            57: {"condition": "Dense freezing drizzle", "icon": "🌨"},
            61: {"condition": "Slight rain", "icon": "🌦"},
            63: {"condition": "Moderate rain", "icon": "🌧"},
            65: {"condition": "Heavy rain", "icon": "🌧"},
            66: {"condition": "Light freezing rain", "icon": "🌨"},
            67: {"condition": "Heavy freezing rain", "icon": "🌨"},
            71: {"condition": "Slight snow fall", "icon": "🌨"},
            73: {"condition": "Moderate snow fall", "icon": "❄"},
            75: {"condition": "Heavy snow fall", "icon": "❄"},
            77: {"condition": "Snow grains", "icon": "❄"},
            80: {"condition": "Slight rain showers", "icon": "🌦"},
            81: {"condition": "Moderate rain showers", "icon": "🌧"},
            82: {"condition": "Violent rain showers", "icon": "⛈"},
            85: {"condition": "Slight snow showers", "icon": "🌨"},
            86: {"condition": "Heavy snow showers", "icon": "❄"},
            95: {"condition": "Thunderstorm", "icon": "⛈"},
            96: {"condition": "Thunderstorm with slight hail", "icon": "⛈"},
            99: {"condition": "Thunderstorm with heavy hail", "icon": "⛈"}
        }

    def format_individual_forecast(self, weather_data, city_name=None):
        try:
            # Extract current temperature and weather code
            current_temp = weather_data["current"]["temperature_2m"]
            weather_code = weather_data["current"]["weather_code"]

            # Get condition and icon
            weather_info = self.weather_code_map.get(weather_code, {"condition": "Unknown", "icon": "❓"})
            condition = weather_info["condition"]
            icon = weather_info["icon"]

            # Format the result
            if city_name:
                return f"{icon} {city_name}: {condition}, {current_temp}°C"
            return f"{condition}, {current_temp}°C"
        except (KeyError, TypeError) as e:
            logger.exception(f"Error formatting weather data for {city_name}: {e!s}")
            if city_name:
                return f"{city_name}: Weather data unavailable"
            return "Weather data unavailable"

    def format_alerts(self, alerts):
        # Implement formatting for OpenMeteoAPI alerts
        # OpenMeteo doesn't have alerts, so return a placeholder
        return "No alerts available (not supported by Open-Meteo)"

    def format_forecast_table(self, forecasts: list[dict[str, Any]], include_condition: bool = False) -> str:
        """Format a list of forecasts into a table string."""
        if not forecasts:
            return ""

        keys = ["ᴄɪᴛʏ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]  # noqa: RUF001
        if include_condition:
            keys.insert(1, "ᴄᴏɴᴅ")

        # Use mixed alignment: right-align temperature columns, left-align others
        alignments = []
        for key in keys:
            if key in ["ʜ°ᴄ", "ʟ°ᴄ"]:  # Temperature columns are right-aligned
                alignments.append("right")
            elif key == "ᴘʀᴇᴄɪᴘ":  # Precipitation needs special handling
                alignments.append("right")  # Right-align precipitation for consistent % symbol position
            else:  # Other columns (city, condition) are left-aligned
                alignments.append("left")

        # Pre-process the forecasts to ensure consistent formatting
        processed_forecasts = []
        for forecast in forecasts:
            processed_forecast = {}
            for key in keys:
                if key not in forecast or not forecast[key]:
                    # Replace missing data with consistent placeholders
                    if key in ["ʜ°ᴄ", "ʟ°ᴄ"]:
                        processed_forecast[key] = "-°"  # Consistent format for temperature placeholders
                    elif key == "ᴘʀᴇᴄɪᴘ":
                        processed_forecast[key] = "-%"  # Consistent format for precipitation placeholders
                    else:
                        processed_forecast[key] = "-"
                else:
                    # Remove trailing spaces from values to avoid inconsistent spacing
                    processed_forecast[key] = forecast[key].rstrip()
            processed_forecasts.append(processed_forecast)
        
        # Calculate column widths based on the processed forecasts
        widths = get_max_widths(processed_forecasts, keys)
        
        # Special handling for temperature columns
        temp_keys = [k for k in keys if k in ["ʜ°ᴄ", "ʟ°ᴄ"]]
        if temp_keys:
            # 1. Ensure all temperature columns have the same width
            max_temp_width = max(widths[k] for k in temp_keys)
            
            # 2. Check if any temperature values are negative
            has_negative_temp = False
            for forecast in processed_forecasts:
                for key in temp_keys:
                    if key in forecast and "-" in forecast[key]:
                        has_negative_temp = True
                        break
                if has_negative_temp:
                    break
            
            # 3. Add extra width to ensure consistent spacing between columns
            for key in temp_keys:
                # Make all temperature columns the same width
                widths[key] = max_temp_width
                
                # If there are negative values, add extra space to ensure consistent alignment
                if has_negative_temp:
                    widths[key] += 1
        
        # Ensure the precipitation column has enough width for the longest value
        # Add a consistent width of 2 spaces to create an even column
        if "ᴘʀᴇᴄɪᴘ" in widths:
            widths["ᴘʀᴇᴄɪᴘ"] += 2
        
        # First create the header row
        header = format_row({k: k for k in keys}, keys, widths, alignments)
        
        # Format each data row
        rows = []
        for forecast in processed_forecasts:
            row = format_row(forecast, keys, widths, alignments)
            rows.append(row)
        
        # Ensure all rows have the same width by removing trailing spaces
        # and then padding to the maximum width
        header = header.rstrip()
        rows = [row.rstrip() for row in rows]
        
        # Calculate the maximum row width to ensure consistency
        max_width = max(len(row) for row in [header] + rows)
        
        # Create final padded rows with exact same width
        uniform_rows = []
        header = header + " " * (max_width - len(header))
        
        for row in rows:
            padded_row = row + " " * (max_width - len(row))
            uniform_rows.append(padded_row)
        
        # Create the final table
        return header + "\n" + "\n".join(uniform_rows)

    def _extract_forecast_data(self, weather_data, city_name):
        """Extract relevant data from the OpenMeteo API response and format it for display"""
        # Clear debug log of incoming data structure
        logger.debug(f"OpenMeteoFormatter: Processing data for {city_name} with keys: {list(weather_data.keys())}")
        if 'daily' in weather_data:
            logger.debug(f"OpenMeteoFormatter: Daily data keys: {list(weather_data['daily'].keys())}")
        
        try:
            # Log the raw temperature values
            temp_max_raw = weather_data["daily"]["temperature_2m_max"][0]
            temp_min_raw = weather_data["daily"]["temperature_2m_min"][0]
            logger.debug(f"OpenMeteoFormatter: {city_name} raw temps - high: {temp_max_raw}, low: {temp_min_raw}")
            
            # Get temperature data and round to integers
            temp_max = round(temp_max_raw)
            temp_min = round(temp_min_raw)
            logger.debug(f"OpenMeteoFormatter: {city_name} rounded temps - high: {temp_max}, low: {temp_min}")

            # Get weather code for condition
            weather_code = weather_data["daily"]["weather_code"][0]
            weather_info = self.weather_code_map.get(weather_code, {"condition": "Unknown", "icon": "❓"})
            condition = weather_info["condition"]
            icon = weather_info["icon"]

            # Log precipitation data availability
            has_precip_prob = "precipitation_probability_max" in weather_data["daily"]
            has_precip_sum = "precipitation_sum" in weather_data["daily"]
            logger.debug(f"OpenMeteoFormatter: {city_name} precip data - has_prob: {has_precip_prob}, has_sum: {has_precip_sum}")
            
            if has_precip_prob:
                precip_prob = weather_data["daily"]["precipitation_probability_max"][0]
                logger.debug(f"OpenMeteoFormatter: {city_name} precip_prob value: {precip_prob}")
                precip = f"{precip_prob}%"
            elif has_precip_sum:
                # If we only have sum but no probability, we should convert it
                precip_sum = weather_data["daily"]["precipitation_sum"][0]
                logger.debug(f"OpenMeteoFormatter: {city_name} only has precip_sum: {precip_sum}mm")
                # TODO: Consider handling this case better
                precip = f"{precip_sum}mm"
            else:
                precip = "0%"
            
            logger.debug(f"OpenMeteoFormatter: {city_name} final precip value: {precip}")

            # Extract current conditions for detailed data
            current = weather_data.get("current", {})

            # Create a detailed data object for potential AI summarization
            detailed_data = {
                "current_temp": round(current.get("temperature_2m", temp_max)),
                "feels_like": round(current.get("apparent_temperature", temp_max)),
                "conditions": condition,
                "wind_speed": f"{current.get('wind_speed_10m', 0)} km/h",
                "humidity": f"{current.get('relative_humidity_2m', 0)}%",
                "high": temp_max,
                "low": temp_min,
                "precipitation": precip,
                "icon": icon
            }

            # Prepare formatted result
            result = {
                "ᴄɪᴛʏ": f"{city_name}  ",
                "ᴄᴏɴᴅ": f"{icon} {condition}  ",
                "ʜ°ᴄ": f"{temp_max}°  ",
                "ʟ°ᴄ": f"{temp_min}°  ",
                "ᴘʀᴇᴄɪᴘ": f"{precip}",
                "ᴅᴇᴛᴀɪʟs": json.dumps(detailed_data)  # Store for summary generation
            }
            
            logger.debug(f"OpenMeteoFormatter: {city_name} final formatted result: {result}")
            return result
        except KeyError as e:
            logger.exception(f"Error extracting forecast data for {city_name}: {e!s}")
            return {
                "ᴄɪᴛʏ": f"{city_name}  ",
                "ᴄᴏɴᴅ": "Data error  ",
                "ʜ°ᴄ": "N/A  ",
                "ʟ°ᴄ": "N/A  ",
                "ᴘʀᴇᴄɪᴘ": "N/A",
                "ᴅᴇᴛᴀɪʟs": json.dumps({"error": f"Data error: {e!s}"})
            }


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
                "humidity": daytime_period.get("relativeHumidity", {}).get("value", "N/A"),
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

    def format_forecast_table(self, forecasts: list[dict[str, Any]], include_condition: bool = False) -> str:
        """Format a list of forecasts into a table string."""
        if not forecasts:
            return ""

        keys = ["ᴄɪᴛʏ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]  # noqa: RUF001
        if include_condition:
            keys.insert(1, "ᴄᴏɴᴅ")

        # Use mixed alignment: right-align temperature columns, left-align others
        alignments = []
        for key in keys:
            if key in ["ʜ°ᴄ", "ʟ°ᴄ"]:  # Temperature columns are right-aligned
                alignments.append("right")
            elif key == "ᴘʀᴇᴄɪᴘ":  # Precipitation needs special handling
                alignments.append("right")  # Right-align precipitation for consistent % symbol position
            else:  # Other columns (city, condition) are left-aligned
                alignments.append("left")

        # Pre-process the forecasts to ensure consistent formatting
        processed_forecasts = []
        for forecast in forecasts:
            processed_forecast = {}
            for key in keys:
                if key not in forecast or not forecast[key]:
                    # Replace missing data with consistent placeholders
                    if key in ["ʜ°ᴄ", "ʟ°ᴄ"]:
                        processed_forecast[key] = "-°"  # Consistent format for temperature placeholders
                    elif key == "ᴘʀᴇᴄɪᴘ":
                        processed_forecast[key] = "-%"  # Consistent format for precipitation placeholders
                    else:
                        processed_forecast[key] = "-"
                else:
                    # Remove trailing spaces from values to avoid inconsistent spacing
                    processed_forecast[key] = forecast[key].rstrip()
            processed_forecasts.append(processed_forecast)
        
        # Calculate column widths based on the processed forecasts
        widths = get_max_widths(processed_forecasts, keys)
        
        # Special handling for temperature columns
        temp_keys = [k for k in keys if k in ["ʜ°ᴄ", "ʟ°ᴄ"]]
        if temp_keys:
            # 1. Ensure all temperature columns have the same width
            max_temp_width = max(widths[k] for k in temp_keys)
            
            # 2. Check if any temperature values are negative
            has_negative_temp = False
            for forecast in processed_forecasts:
                for key in temp_keys:
                    if key in forecast and "-" in forecast[key]:
                        has_negative_temp = True
                        break
                if has_negative_temp:
                    break
            
            # 3. Add extra width to ensure consistent spacing between columns
            for key in temp_keys:
                # Make all temperature columns the same width
                widths[key] = max_temp_width
                
                # If there are negative values, add extra space to ensure consistent alignment
                if has_negative_temp:
                    widths[key] += 1
        
        # Ensure the precipitation column has enough width for the longest value
        # Add a consistent width of 2 spaces to create an even column
        if "ᴘʀᴇᴄɪᴘ" in widths:
            widths["ᴘʀᴇᴄɪᴘ"] += 2
        
        # First create the header row
        header = format_row({k: k for k in keys}, keys, widths, alignments)
        
        # Format each data row
        rows = []
        for forecast in processed_forecasts:
            row = format_row(forecast, keys, widths, alignments)
            rows.append(row)
        
        # Ensure all rows have the same width by removing trailing spaces
        # and then padding to the maximum width
        header = header.rstrip()
        rows = [row.rstrip() for row in rows]
        
        # Calculate the maximum row width to ensure consistency
        max_width = max(len(row) for row in [header] + rows)
        
        # Create final padded rows with exact same width
        uniform_rows = []
        header = header + " " * (max_width - len(header))
        
        for row in rows:
            padded_row = row + " " * (max_width - len(row))
            uniform_rows.append(padded_row)
        
        # Create the final table
        return header + "\n" + "\n".join(uniform_rows)


class WeatherFormatter:
    def __init__(self, formatter: WeatherFormatterInterface):
        self.formatter = formatter

    def format_individual_forecast(self, weather_data, city_name=None):
        return self.formatter.format_individual_forecast(weather_data, city_name)

    def format_alerts(self, alerts):
        return self.formatter.format_alerts(alerts)

    def format_forecast_table(self, forecasts: list[dict[str, Any]], include_condition: bool = False) -> str:
        """Format a list of forecasts into a table string."""
        # Check if Tokyo is in the forecasts and log its format
        for forecast in forecasts:
            if isinstance(forecast, dict) and "ᴄɪᴛʏ" in forecast and "Tokyo" in forecast["ᴄɪᴛʏ"]:
                logger.info(f"Tokyo in format_forecast_table: {forecast}")
                
        return self.formatter.format_forecast_table(forecasts, include_condition)
