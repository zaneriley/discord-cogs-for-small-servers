import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
import pytz

import discord
from discord import app_commands
from discord.ext import tasks
from redbot.core import commands

from utilities.text_formatting_utils import format_row, get_max_widths

from .config import ConfigManager
from .weather_api import WeatherAPIFactory
from .weather_formatter import WeatherFormatter, WeatherGovFormatter

logger = logging.getLogger(__name__)


class WeatherChannel(commands.Cog):

    """A cog for reporting weather conditions."""

    def __init__(self, bot):
        self.bot = bot
        self.guild_id = int(os.getenv("GUILD_ID"))
        self.weather_api = WeatherAPIFactory.create_weather_api_handler("weather-gov")
        self.weather_formatter = WeatherFormatter(WeatherGovFormatter())  # Pass an instance of WeatherGovFormatter
        self.config_manager = ConfigManager(self.guild_id, self)
        self.api_handlers = {}  # Initialize the api_handlers dictionary
        self.forecast_task.start()

    def on_forecast_task_complete(self, task):
        """Schedule the next run at 6 AM Eastern or Tokyo time, whichever comes next."""
        eastern = pytz.timezone('America/New_York')
        tokyo = pytz.timezone('Asia/Tokyo')
        now_utc = datetime.now(pytz.utc)

        next_eastern_6am = (now_utc.astimezone(eastern)
                            .replace(hour=6, minute=0, second=0, microsecond=0)
                            .astimezone(pytz.utc))
        if next_eastern_6am < now_utc:
            next_eastern_6am += timedelta(days=1)

        next_tokyo_6am = (now_utc.astimezone(tokyo)
                          .replace(hour=6, minute=0, second=0, microsecond=0)
                          .astimezone(pytz.utc))
        if next_tokyo_6am < now_utc:
            next_tokyo_6am += timedelta(days=1)

        next_run_time = min(next_eastern_6am, next_tokyo_6am)
        delay = (next_run_time - now_utc).total_seconds()
        self.forecast_task.change_interval(seconds=delay)
        self.forecast_task.restart()
        
    def cog_unload(self):
        self.forecast_task.cancel()

    async def fetch_weather(self, api_type, coords, city):
        if api_type not in self.api_handlers:
            self.api_handlers[api_type] = WeatherAPIFactory.create_weather_api_handler(api_type)

        # Type checking for coords
        if not isinstance(coords, tuple) or len(coords) != 2:
            logger.error("Invalid coordinates format: %s", coords)
            return f"Invalid coordinates format for {city}."

        try:
            # Ensure each part of coords can be converted to float
            coords_str = ",".join(map(str, map(float, coords)))
            weather_data = await self.api_handlers[api_type].get_forecast(coords_str)
            return self.weather_formatter.format_individual_forecast(weather_data, city)
        except ValueError:
            logger.exception("Error converting coordinates to float for %s:", city)
            return f"Error in coordinates format for {city}."
        except Exception:
            logger.exception("Error processing forecast for %s:", city)
            return f"Error fetching weather for {city}."

    weather = app_commands.Group(name="weather", description="Commands related to weather information")

    @weather.command(name="current", description="Get current weather information")
    @app_commands.describe(location="Location to get weather information for")
    @app_commands.choices(
        location=[
            app_commands.Choice(name="San Francisco", value="San Francisco"),
            app_commands.Choice(name="Seattle", value="Seattle"),
            app_commands.Choice(name="Blodgett", value="Blodgett"),
            app_commands.Choice(name="New York City", value="New York City"),
            app_commands.Choice(name="Boston", value="Boston"),
            app_commands.Choice(name="Everywhere", value="Everywhere"),
        ]
    )
    async def forecast(self, ctx, location: str | None = None):
        """Get the current weather!"""
        current_time = int(datetime.now(tz=UTC).timestamp())  # Get current Unix timestamp
        timestamp = f"<t:{current_time}:F>"  # Format for Discord, eg. Sunday, June 2, 2024 at 9:57 PM

        if location == "Everywhere" or location is None:
            default_locations = await self.config_manager.get_default_locations(self.guild_id)
            if not default_locations:
                await ctx.send("No default locations set for this guild.")
                return
            forecasts = [
                await self.fetch_weather(api_type, coords, city)
                for city, (api_type, coords) in default_locations.items()
            ]
            await ctx.send(f"{timestamp}\n```{forecasts}```")
        else:
            # Assume default API type and coordinates format for direct location queries
            formatted_data = await self.fetch_weather("weather-gov", location.split(","), location)
            await ctx.send(f"{timestamp}\n```{formatted_data}```")

    @tasks.loop(hours=1)
    async def forecast_task(self):
        current_time = int(datetime.now(tz=UTC).timestamp())
        timestamp = f"<t:{current_time}:F>"

        default_locations = await self.config_manager.get_default_locations(self.guild_id)
        if not default_locations:
            logger.warning("No default locations set for this guild.")
            return
        channel_id = await self.config_manager.get_weather_channel(self.guild_id)
        channel = self.bot.get_channel(channel_id)
        if channel:
            forecasts = await asyncio.gather(
                *[self.fetch_weather(api_type, coords, city) for city, (api_type, coords) in default_locations.items()]
            )
            logger.info(f"Fetched forecasts: {forecasts[0]}")

            # Ensure we have a list of dictionaries.
            table_data = [forecast for forecast in forecasts if isinstance(forecast, dict)]

            keys = ["City", "C", "F", "Precip"]
            alignments = ["left", "left", "left", "left"]
            widths = get_max_widths(table_data, keys)

            header = format_row({k: k for k in keys}, keys, widths, alignments)
            rows = [format_row(row, keys, widths, alignments) for row in table_data]
            table_string = header + "\n" + "\n".join(rows)

            await channel.send(f"{timestamp}\n```\n{table_string}\n```") 
        else:
            logger.warning("Weather channel not found.")

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def setweatherchannel(self, ctx, channel: discord.TextChannel):
        """Sets the channel for weather updates."""
        try:
            await self.config_manager.set_weather_channel(ctx.guild.id, channel.id)
            await ctx.send(f"Weather updates will now be sent to {channel.mention}.")
            logger.info(
                "Weather channel set to %s for guild %s (ID: %s)", channel.mention, ctx.guild.name, ctx.guild.id
            )
        except Exception:
            logger.exception("Failed to set weather channel for guild %s (ID: %s)", ctx.guild.name, ctx.guild.id)
            await ctx.send("An error occurred while setting the weather channel.")
