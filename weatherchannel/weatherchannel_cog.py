import asyncio
import json  # Import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path  # Import Path

import discord
import pytz
from discord import app_commands
from discord.ext import tasks
from redbot.core import commands

from utilities.text_formatting_utils import format_row, get_max_widths

from .config import ConfigManager
from .weather_service import WeatherService

logger = logging.getLogger(__name__)


class WeatherChannel(commands.Cog):

    """A cog for reporting weather conditions."""

    def __init__(self, bot):
        self.bot = bot
        self.guild_id = int(os.getenv("GUILD_ID"))
        self.strings = self.load_strings()  # Load strings first so WeatherService can use them
        self.weather_service = WeatherService(self.strings)  # Pass strings to WeatherService
        self.config_manager = ConfigManager(self.guild_id, self)
        self.api_handlers = {}  # Initialize the api_handlers dictionary - also likely not needed here, service handles it.
        self.on_forecast_task_complete.start()


    def load_strings(self) -> dict:  # Renamed for clarity, and to be called only once.
        """Load localized strings from JSON file."""
        path = Path(__file__).parent / "strings.json"
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    @tasks.loop()
    async def on_forecast_task_complete(self):
        """Schedule the next run at 6 AM Eastern."""
        eastern = pytz.timezone("America/New_York")
        now_utc = datetime.now(pytz.utc)

        # Calculate next 6 AM Eastern (or next day if past 6 AM already)
        next_eastern_6am = (
            now_utc.astimezone(eastern)
            .replace(hour=8, minute=0, second=0, microsecond=0)  # 8 AM UTC is 6 AM Eastern
            .astimezone(pytz.utc)
        )
        if next_eastern_6am < now_utc:
            next_eastern_6am += timedelta(days=1)

        # Format the next run time for readability and log the information
        next_run_time_eastern = next_eastern_6am.astimezone(eastern).strftime("%Y-%m-%d %I:%M %p %Z")
        logger.info(
            "Next weather check scheduled for: %s (Eastern Time)", next_run_time_eastern
        )

        # Sleep until scheduled time
        delay = (next_eastern_6am - now_utc.astimezone(eastern)).total_seconds()
        await asyncio.sleep(delay)

        # Perform the forecast update task
        await self.forecast_task()

        # Immediately reschedule for precision
        self.on_forecast_task_complete.restart()


    def cog_unload(self):
        self.on_forecast_task_complete.cancel()
        self.forecast_task.cancel()


    weather = app_commands.Group(name="weather", description="Commands related to weather information")

    @weather.command(
        name="now",
        # These need to be literals for Discord.py
        description="Get current weather information. Shows all locations if none specified."
    )
    @app_commands.describe(
        # This also needs to be a literal
        location="Location to get weather information for (defaults to all locations)"
    )
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
    async def weather_now(self, interaction: discord.Interaction, location: str | None = None):
        """Get the current weather!"""
        # Default to "Everywhere" if no location specified
        location = location or "Everywhere"

        # Retrieve default locations
        default_locations = await self.config_manager.get_default_locations(self.guild_id)

        if location == "Everywhere":
            # Fetch weather for all locations
            forecasts = await asyncio.gather(
                *[self.weather_service.fetch_weather(api_type, coords, city) 
                  for city, (api_type, coords) in default_locations.items()]
            )
            forecasts = [f for f in forecasts if isinstance(f, dict) and "error" not in f]
            keys = ["ᴄɪᴛʏ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]
        elif location in default_locations:
            # Fetch weather for the specified location
            api_type, coords = default_locations[location]
            forecast_response = await self.weather_service.fetch_weather(api_type, coords, location)
            if "error" in forecast_response:
                await interaction.response.send_message(
                    forecast_response["error"], ephemeral=True
                )
                return
            forecasts = [forecast_response]
            keys = ["ᴄɪᴛʏ", "ᴄᴏɴᴅ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]
        else:
            await interaction.response.send_message(
                self.strings["errors"]["location_not_recognized"], ephemeral=True
            )
            return

        # Format the data
        table_data = [forecast for forecast in forecasts if isinstance(forecast, dict)]
        if not table_data:
            await interaction.response.send_message(
                self.strings["errors"]["service"]["no_weather_data"],
                ephemeral=True
            )
            return

        alignments = ["left"] * len(keys)
        widths = get_max_widths(table_data, keys)
        header = format_row({k: k for k in keys}, keys, widths, alignments)
        rows = [format_row(row, keys, widths, alignments) for row in table_data]
        table_string = header + "\n" + "\n".join(rows)

        await interaction.response.send_message(f"`{table_string}`")

    async def forecast_task(self):
        current_time = int(datetime.now(tz=UTC).timestamp())

        default_locations = await self.config_manager.get_default_locations(self.guild_id)
        if not default_locations:
            logger.warning("No default locations set for this guild.")
            return
        channel_id = await self.config_manager.get_weather_channel(self.guild_id)
        channel = self.bot.get_channel(channel_id)
        if channel:
            forecasts = await asyncio.gather(
                *[self.weather_service.fetch_weather(api_type, coords, city) for city, (api_type, coords) in default_locations.items()]
            )
            logger.info(f"Fetched forecasts: {forecasts}") # Log all forecast results, including errors

            # Ensure we have a list of dictionaries and filter out errors for table display.
            table_data = [forecast for forecast in forecasts if isinstance(forecast, dict) and "error" not in forecast]

            if not table_data: # Handle case where no valid forecast data is available (all errors, or no locations)
                logger.warning("No valid weather data to report in forecast task.")
                return # Exit forecast task if no valid data

            keys = ["ᴄɪᴛʏ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]
            alignments = ["left", "left", "left", "right"]
            widths = get_max_widths(table_data, keys)

            header = format_row({k: k for k in keys}, keys, widths, alignments)
            rows = [format_row(row, keys, widths, alignments) for row in table_data]
            table_string = header + "\n" + "\n".join(rows)

            await channel.send(f"{self.strings['weather_report_title']}\n`{table_string}\n`",
                               allowed_mentions=discord.AllowedMentions.none())
        else:
            logger.warning("Weather channel not found.")

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def setweatherchannel(self, ctx, channel: discord.TextChannel):
        """Sets the channel for weather updates."""
        try:
            await self.config_manager.set_weather_channel(ctx.guild.id, channel.id)
            # Edit the strings in strings.json if you want to change these
            success_message = self.strings["messages"]["weather_channel_set_success"].format(channel_mention=channel.mention)
            await ctx.send(success_message)
            logger.info(
                "Weather channel set to %s for guild %s (ID: %s)", channel.mention, ctx.guild.name, ctx.guild.id
            )
        except Exception:
            logger.exception("Failed to set weather channel for guild %s (ID: %s)", ctx.guild.name, ctx.guild.id)
            # Use string from strings.json
            await ctx.send(self.strings["errors"]["weather_channel_set_error"])