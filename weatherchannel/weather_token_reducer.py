"""
Token reduction utilities specific to weather forecast data.

This module provides a domain-specific token reducer for weather data
to minimize token usage when sending forecasts to LLM services.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class WeatherTokenReducer:
    """Reduces weather forecast information to minimize token consumption."""
    
    def reduce_forecasts(self, forecasts: Dict[str, Any]) -> str:
        """
        Convert verbose weather forecast JSON to token-efficient plain text.
        
        Args:
            forecasts: Raw weather forecast data in JSON format
            
        Returns:
            Plain text representation of the weather data
        """
        text_lines = []
        
        for city, data in forecasts.items():
            if isinstance(data, dict) and "error" in data:
                # Skip cities with errors
                continue
                
            text_lines.append(f"{city}:")
            
            # Handle both WeatherGov and OpenMeteo data formats
            if "properties" in data and "periods" in data["properties"]:
                # Weather.gov format
                self._process_weather_gov_data(data, text_lines)
            elif "daily" in data or "current" in data:
                # OpenMeteo format
                self._process_open_meteo_data(data, text_lines)
            else:
                # Unknown format - add placeholder
                text_lines.append("  Data format not recognized")
        
        if not text_lines:
            return "No valid weather data available."
            
        return "\n".join(text_lines)
    
    def _process_weather_gov_data(self, data: Dict[str, Any], text_lines: List[str]) -> None:
        """Process Weather.gov data format."""
        periods = data["properties"]["periods"]
        
        for period in periods:
            # Extract the essential information
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "N/A")
            temp_unit = period.get("temperatureUnit", "F")
            forecast = period.get("shortForecast", "")
            
            # Get precipitation probability if available
            precip = "0%"  # Default to 0% instead of N/A
            if "probabilityOfPrecipitation" in period:
                if period["probabilityOfPrecipitation"].get("value") is not None:
                    precip = f"{period['probabilityOfPrecipitation']['value']}%"
            
            # Add this period's data with proper unicode for degree symbol
            text_lines.append(f"  {name}: {temp}°{temp_unit}, {forecast}, {precip} chance of precipitation")
    
    def _process_open_meteo_data(self, data: Dict[str, Any], text_lines: List[str]) -> None:
        """Process OpenMeteo data format."""
        # Get temperature unit from metadata if available
        temp_unit = data.get("temperature_unit", "°C")
        
        # Process current data if available
        if "current" in data:
            current = data["current"]
            current_temp = current.get("temperature_2m", "N/A")
            
            # Get weather code and convert to text
            weather_code = current.get("weather_code", 0)
            condition = self._weather_code_to_text(weather_code)
            
            # Get precipitation probability
            precip_prob = "0%"  # Default
            if "precipitation_probability" in current:
                precip_prob = f"{current['precipitation_probability']}%"
            
            text_lines.append(f"  Current: {current_temp}{temp_unit}, {condition}, {precip_prob} chance of precipitation")
        
        # Process daily forecast if available
        if "daily" in data:
            daily = data["daily"]
            
            # Check if we have time series data
            if isinstance(daily.get("time", []), list) and len(daily.get("time", [])) > 0:
                times = daily.get("time", [])
                
                for i, time in enumerate(times):
                    if i >= 7:  # Limit to 7 days to reduce tokens
                        break
                        
                    # Get the forecast for this day
                    max_temp = daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else "N/A"
                    min_temp = daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else "N/A"
                    
                    # Get weather code for this day
                    weather_code = daily.get("weather_code", [])[i] if "weather_code" in daily and i < len(daily["weather_code"]) else 0
                    condition = self._weather_code_to_text(weather_code)
                    
                    # Get precipitation probability
                    precip_prob = "0%"  # Default
                    if "precipitation_probability_max" in daily and i < len(daily["precipitation_probability_max"]):
                        prob = daily["precipitation_probability_max"][i]
                        if prob is not None:
                            precip_prob = f"{prob}%"
                    
                    # Format the date in a more readable way
                    date_parts = time.split("-")
                    if len(date_parts) == 3:
                        formatted_date = f"{date_parts[1]}/{date_parts[2]}"
                    else:
                        formatted_date = time
                    
                    text_lines.append(
                        f"  {formatted_date}: High {max_temp}{temp_unit}, Low {min_temp}{temp_unit}, "
                        f"{condition}, {precip_prob} chance of precipitation"
                    )
    
    def _weather_code_to_text(self, code: int) -> str:
        """Convert OpenMeteo weather code to human-readable text."""
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
        return weather_codes.get(code, "Unknown")
    
    def reduce_weather_dict(self, weather_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reduce a weather dictionary by removing unnecessary fields.
        
        Args:
            weather_dict: Full weather dictionary with potentially unnecessary fields
            
        Returns:
            Reduced dictionary with only essential fields
        """
        # Create a minimal version with only what we need
        result = {}
        
        for city, data in weather_dict.items():
            if isinstance(data, dict) and "error" in data:
                # Preserve error messages
                result[city] = {"error": data["error"]}
                continue
                
            # Initialize city data with basic structure
            city_data = {"periods": []}
            
            # Handle both WeatherGov and OpenMeteo formats
            if "properties" in data and "periods" in data["properties"]:
                # Weather.gov format
                for period in data["properties"]["periods"]:
                    reduced_period = {
                        "name": period.get("name", "Unknown"),
                        "temp": period.get("temperature", "N/A"),
                        "unit": period.get("temperatureUnit", "F"),
                        "forecast": period.get("shortForecast", ""),
                    }
                    
                    # Add precipitation if available
                    if "probabilityOfPrecipitation" in period and period["probabilityOfPrecipitation"].get("value") is not None:
                        reduced_period["precip"] = period["probabilityOfPrecipitation"]["value"]
                    else:
                        reduced_period["precip"] = 0  # Default to 0
                        
                    city_data["periods"].append(reduced_period)
                    
            elif "daily" in data:
                # OpenMeteo format - extract daily data
                daily = data["daily"]
                
                if isinstance(daily.get("time", []), list) and len(daily.get("time", [])) > 0:
                    times = daily.get("time", [])
                    
                    for i, time in enumerate(times):
                        if i >= 7:  # Limit to 7 days
                            break
                            
                        period = {
                            "name": f"Day {i+1}",
                            "date": time,
                            "temp_max": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else "N/A",
                            "temp_min": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else "N/A",
                            "unit": data.get("temperature_unit", "°C").replace("°", ""),
                            "precip": daily.get("precipitation_probability_max", [])[i] if "precipitation_probability_max" in daily and i < len(daily["precipitation_probability_max"]) else 0,
                            "weather_code": daily.get("weather_code", [])[i] if "weather_code" in daily and i < len(daily["weather_code"]) else 0
                        }
                        
                        city_data["periods"].append(period)
            
            # Add metadata
            if "_meta" in data:
                city_data["_meta"] = data["_meta"]
                
            result[city] = city_data
            
        return result
    
    def get_daily_summary(self, weather_data: Dict[str, Any]) -> str:
        """
        Create a concise daily summary from weather data.
        
        Args:
            weather_data: Weather data dictionary
            
        Returns:
            String with a condensed daily summary
        """
        text_lines = []
        
        for city, data in weather_data.items():
            if isinstance(data, dict) and "error" in data:
                continue
                
            text_lines.append(f"{city}:")
            
            # Handle both WeatherGov and OpenMeteo formats
            if "properties" in data and "periods" in data["properties"]:
                # Weather.gov format - extract daytime periods
                periods = data["properties"]["periods"]
                daytime_periods = [p for p in periods if p.get("isDaytime", False)][:3]
                
                for period in daytime_periods:
                    name = period.get("name", "Unknown")
                    temp = period.get("temperature", "N/A")
                    forecast = period.get("shortForecast", "")
                    
                    # Use proper unicode for degree symbol
                    text_lines.append(f"  {name}: {temp}°, {forecast}")
                    
            elif "daily" in data:
                # OpenMeteo format - extract daily data for first 3 days
                daily = data["daily"]
                temp_unit = data.get("temperature_unit", "°C")
                
                if isinstance(daily.get("time", []), list) and len(daily.get("time", [])) > 0:
                    limit = min(3, len(daily.get("time", [])))
                    
                    for i in range(limit):
                        date = daily.get("time", [])[i]
                        max_temp = daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else "N/A"
                        
                        # Get weather code for this day
                        weather_code = daily.get("weather_code", [])[i] if "weather_code" in daily and i < len(daily["weather_code"]) else 0
                        condition = self._weather_code_to_text(weather_code)
                        
                        # Format the date in a more readable way
                        date_parts = date.split("-")
                        if len(date_parts) == 3:
                            formatted_date = f"{date_parts[1]}/{date_parts[2]}"
                        else:
                            formatted_date = date
                        
                        text_lines.append(f"  {formatted_date}: {max_temp}{temp_unit}, {condition}")
        
        if not text_lines:
            return "No valid weather data available for summary."
            
        return "\n".join(text_lines)
    
    def get_relevant_alerts(self, weather_data: Dict[str, Any]) -> str:
        """
        Extract only relevant weather alerts.
        
        Args:
            weather_data: Weather data dictionary
            
        Returns:
            String with only significant alerts
        """
        alerts = []
        
        # Extract alerts if available
        for city, data in weather_data.items():
            if isinstance(data, dict) and "error" in data:
                continue
                
            if "alerts" in data:
                for alert in data["alerts"]:
                    # Only include higher-priority alerts to reduce tokens
                    if alert.get("severity") in ["Extreme", "Severe", "Moderate"]:
                        headline = alert.get("headline", "")
                        alerts.append(f"{city}: {headline}")
        
        if not alerts:
            return "No significant weather alerts."
            
        return "ALERTS:\n" + "\n".join(alerts)
    
    def format_for_llm_prompt(self, weather_data: Dict[str, Any], include_alerts: bool = True) -> str:
        """
        Format weather data for optimal LLM prompt.
        
        Args:
            weather_data: Weather data dictionary
            include_alerts: Whether to include alerts
            
        Returns:
            Token-optimized string for LLM prompt
        """
        # Get base forecast in plain text
        forecast_text = self.reduce_forecasts(weather_data)
        
        # Optionally add alerts if requested
        if include_alerts:
            alerts_text = self.get_relevant_alerts(weather_data)
            if alerts_text != "No significant weather alerts.":
                forecast_text += f"\n\n{alerts_text}"
                
        return forecast_text
