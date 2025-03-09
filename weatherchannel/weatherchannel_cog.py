from __future__ import annotations

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

# Check if .env file exists and load it if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Look for .env in project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        logging.info("Loading environment variables from %s", env_path)
        load_dotenv(dotenv_path=env_path)
    else:
        logging.warning("No .env file found at %s", env_path)
except ImportError:
    logging.warning("python-dotenv not installed, skipping .env loading in weatherchannel")


from .config import ConfigManager
from .weather_service import WeatherService

logger = logging.getLogger(__name__)

# Define constants
MAX_DISCORD_MESSAGE_LENGTH = 1900  # Maximum length for code blocks in Discord messages

class WeatherChannel(commands.Cog):

    """A cog for reporting weather conditions."""

    def __init__(self, bot):
        self.bot = bot
        logger.info("WeatherChannel cog initializing...")
        self.guild_id = int(os.getenv("GUILD_ID"))
        self.strings = self.load_strings()  # Load strings first so WeatherService can use them
        self.weather_service = WeatherService(self.strings)  # Pass strings to WeatherService
        self.config_manager = ConfigManager(self.guild_id, self)
        self.api_handlers = {}  # Initialize the api_handlers dictionary - also likely not needed here, service handles it.

        # Added tracking variables for scheduler status
        self.next_forecast_time = None
        self.scheduler_active = False
        self.last_forecast_time = None
        self.last_forecast_success = None

        self.on_forecast_task_complete.start()
        logger.info("WeatherChannel cog initialized. Registered commands: %s",
                   [c.name for c in self.weather.commands])


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

        # Save the next forecast time
        self.next_forecast_time = next_eastern_6am
        self.scheduler_active = True

        # Format the next run time for readability and log the information
        next_run_time_eastern = next_eastern_6am.astimezone(eastern).strftime("%Y-%m-%d %I:%M %p %Z")
        logger.info(
            "Next weather check scheduled for: %s (Eastern Time)", next_run_time_eastern
        )

        # Sleep until scheduled time
        delay = (next_eastern_6am - now_utc.astimezone(eastern)).total_seconds()
        await asyncio.sleep(delay)

        # Perform the forecast update task
        try:
            await self.forecast_task()
            self.last_forecast_time = datetime.now(pytz.utc)
            self.last_forecast_success = True
        except Exception as e:
            logger.exception("Error during forecast task: %s", str(e))
            self.last_forecast_time = datetime.now(pytz.utc)
            self.last_forecast_success = False

        # Immediately reschedule for precision
        self.on_forecast_task_complete.restart()


    def cog_unload(self):
        self.on_forecast_task_complete.cancel()


    weather = app_commands.Group(
        name="weather",
        description="Get weather information and forecasts for configured locations"
    )
    """Weather command group for retrieving and managing weather information.

    This group contains commands for viewing current weather conditions,
    generating summaries, accessing raw data, and configuring weather settings.

    Basic commands:
    • /weather current - View current weather for all or a specific location
    • /weather summary - Generate an AI summary of weather conditions
    • /weather schedule - Check when the next weather forecast is scheduled

    Admin commands:
    • /weather set channel - Configure channel for daily weather updates

    Developer commands:
    • /weather raw - Get raw JSON weather data
    """

    @weather.command(
        name="current",
        description="Get current weather information for all locations or a specific city"
    )
    @app_commands.describe(
        city="The city to get weather for (shows all cities if not specified)"
    )
    async def weather_current_slash_command(self, interaction: discord.Interaction, city: str = "Everywhere"):
        """
        Get current weather information for configured locations (slash command version).

        Parameters
        ----------
        interaction
            The Discord interaction
        city
            The city to get weather for (shows all cities if not specified)

        """
        logger.info("Command weather current (slash) invoked by %s with city: %s", interaction.user, city)
        ctx = await commands.Context.from_interaction(interaction)
        await self._weather_current_logic(ctx, city)

    @commands.group(name="weather", aliases=["wx"])
    @commands.guild_only()
    async def weather_group(self, ctx):
        """Weather commands for retrieving and managing weather information."""
        if ctx.invoked_subcommand is None:
            # Show help or a message about available subcommands
            embed = discord.Embed(
                title="Weather Commands",
                description="Here are the available weather commands:",
                color=discord.Color.blue()
            )
            embed.add_field(name="!weather current [city]", value="Get current weather information", inline=False)
            embed.add_field(name="!weather summary [city]", value="Generate an AI summary of weather conditions", inline=False)
            embed.add_field(name="!weather schedule", value="Check when the next weather forecast is scheduled", inline=False)
            embed.add_field(name="!weather raw [city]", value="Get raw weather data for debugging", inline=False)
            embed.add_field(name="!weather set channel [#channel]", value="Set the channel for daily weather updates (Admin only)", inline=False)
            embed.set_footer(text="Type !help weather for more detailed information")
            await ctx.send(embed=embed)

    @weather_group.command(
        name="current",
        aliases=["now"],
        description="Get current weather information for all locations or a specific city"
    )
    async def weather_current_text_command(self, ctx, city: str = "Everywhere"):
        """
        Get current weather information for configured locations (text command version).

        Parameters
        ----------
        ctx
            The command context
        city
            The city to get weather for (shows all cities if not specified)

        """
        logger.info("Command weather current (text) invoked by %s with city: %s", ctx.author, city)
        await self._weather_current_logic(ctx, city)

    async def _weather_current_logic(self, ctx, city: str = "Everywhere"):
        """
        Shared logic for current weather commands.

        Parameters
        ----------
        ctx
            The command context
        city
            The city to get weather for (shows all cities if not specified)

        """
        # Retrieve default locations
        default_locations = await self.config_manager.get_default_locations(self.guild_id)

        if city == "Everywhere":
            # Use the service to fetch weather for all locations
            forecasts = await self.weather_service.fetch_all_locations_weather(default_locations)

            if not forecasts:
                await ctx.send(self.strings["errors"]["service"]["no_weather_data"])
                return

            # Use the service to format the table
            table_string = await self.weather_service.format_forecast_table(forecasts, include_condition=False)

        elif city.lower() in (loc.lower() for loc in default_locations):
            # Use the service to fetch weather for specific city
            forecast = await self.weather_service.fetch_city_weather(city, default_locations)

            if not forecast or "error" in forecast:
                error_message = forecast.get("error", self.strings["errors"]["service"]["weather_fetch_error"].format(city=city)) if forecast else self.strings["errors"]["service"]["weather_fetch_error"].format(city=city)
                await ctx.send(error_message)
                return

            # Format single city forecast with condition included
            table_string = await self.weather_service.format_forecast_table([forecast], include_condition=True)
        else:
            await ctx.send(self.strings["errors"]["location_not_recognized"])
            return

        # Send the formatted table to Discord
        logger.debug(f"Final weather table: {table_string}")
        await ctx.send(f"```{table_string}```")

    @weather_current_slash_command.autocomplete("city")
    async def weather_current_autocomplete(self, _: discord.Interaction, current: str):
        """Provide autocomplete for city parameter."""
        choices = await self.config_manager.get_city_choices()
        return [choice for choice in choices if current.lower() in choice.name.lower()]

    @weather.command(
        name="raw",
        description="Get raw weather data for debugging and prompt testing"
    )
    @app_commands.describe(
        city="The city to get raw data for (shows all cities if not specified)"
    )
    async def weather_raw_slash_command(self, interaction: discord.Interaction, city: str = "Everywhere"):
        """
        Get raw JSON weather data for debugging and testing (slash command version).

        Parameters
        ----------
        interaction
            The Discord interaction
        city
            The city to get raw data for (shows all cities if not specified)

        """
        logger.info("Command weather raw (slash) invoked by %s with city: %s", interaction.user, city)
        ctx = await commands.Context.from_interaction(interaction)
        await self._weather_raw_logic(ctx, city)

    @weather_group.command(
        name="raw",
        aliases=["data"],
        description="Get raw JSON weather data for debugging and testing"
    )
    async def weather_raw_text_command(self, ctx, city: str = "Everywhere"):
        """
        Get raw JSON weather data for debugging and testing (text command version).

        Parameters
        ----------
        ctx
            The command context
        city
            The city to get raw data for (shows all cities if not specified)

        """
        logger.info("Command weather raw (text) invoked by %s with city: %s", ctx.author, city)
        await self._weather_raw_logic(ctx, city)

    async def _weather_raw_logic(self, ctx, city: str = "Everywhere"):
        """
        Shared logic for raw weather data commands.

        Parameters
        ----------
        ctx
            The command context
        city
            The city to get raw data for (shows all cities if not specified)

        """
        import json
        import tempfile

        # Retrieve default locations
        default_locations = await self.config_manager.get_default_locations(self.guild_id)

        # Use the service to fetch raw weather data
        raw_data = await self.weather_service.fetch_raw_weather_data(city, default_locations)

        if "error" in raw_data and len(raw_data) == 1:
            await ctx.send(raw_data["error"])
            return

        # Convert to formatted JSON string
        raw_json = json.dumps(raw_data, indent=2)

        # Check if the data is too large for a Discord message
        if len(raw_json) > MAX_DISCORD_MESSAGE_LENGTH:  # Leave some room for code block formatting
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
                f.write(raw_json)
                temp_path = f.name

            # Send as a file attachment
            await ctx.send(
                f"Raw weather data for {city} (sent as attachment due to size)",
                file=discord.File(temp_path, f"weather_data_{city.replace(' ', '_')}.json")
            )

            # Clean up the temporary file
            Path(temp_path).unlink()
        else:
            # Send as a code block
            await ctx.send(f"```json\n{raw_json}\n```")

    @weather_raw_slash_command.autocomplete("city")
    async def weather_raw_autocomplete(self, _: discord.Interaction, current: str):
        """Provide autocomplete for city parameter."""
        choices = await self.config_manager.get_city_choices()
        return [choice for choice in choices if current.lower() in choice.name.lower()]

    @weather.command(
        name="summary",
        description="Generate an AI-powered natural language summary of weather conditions"
    )
    @app_commands.describe(
        city="The city to generate a summary for (summarizes all cities if not specified)"
    )
    async def weather_summary_slash_command(self, interaction: discord.Interaction, city: str = "Everywhere"):
        """
        Generate an AI-powered natural language summary of weather conditions (slash command version).

        Parameters
        ----------
        interaction
            The Discord interaction
        city
            The city to generate a summary for (summarizes all cities if not specified)

        """
        logger.info("Command weather summary (slash) invoked by %s with city: %s", interaction.user, city)
        ctx = await commands.Context.from_interaction(interaction)
        await self._weather_summary_logic(ctx, city)

    @weather_group.command(
        name="summary",
        aliases=["sum", "report"],
        description="Generate an AI-powered natural language summary of weather conditions"
    )
    async def weather_summary_text_command(self, ctx, city: str = "Everywhere"):
        """
        Generate an AI-powered natural language summary of weather conditions (text command version).

        Parameters
        ----------
        ctx
            The command context
        city
            The city to generate a summary for (summarizes all cities if not specified)

        """
        logger.info("Command weather summary (text) invoked by %s with city: %s", ctx.author, city)
        await self._weather_summary_logic(ctx, city)

    async def _weather_summary_logic(self, ctx, city: str = "Everywhere"):
        """
        Shared logic for weather summary commands.

        Parameters
        ----------
        ctx
            The command context
        city
            The city to generate a summary for (summarizes all cities if not specified)

        """
        await ctx.send("Generating weather summary, please wait...")

        # Retrieve default locations
        default_locations = await self.config_manager.get_default_locations(self.guild_id)

        # Fetch raw weather data for summary using the new method
        raw_forecasts = await self.weather_service.fetch_raw_data_for_summary(city, default_locations)

        # Check if we have valid data
        if not raw_forecasts:
            await ctx.send(self.strings["errors"]["service"]["no_weather_data"])
            return

        # Check for city-specific errors
        if city != "Everywhere" and city in raw_forecasts and "error" in raw_forecasts[city]:
            await ctx.send(raw_forecasts[city]["error"])
            return

        # Check for any data to process
        if all("error" in data for city_name, data in raw_forecasts.items()):
            await ctx.send(self.strings["errors"]["service"]["no_weather_data"])
            return

        try:
            # Generate summary using the new raw data method
            summary = await self.weather_service.get_weather_summary_from_raw(raw_forecasts)
            if not summary:
                await ctx.send("Unable to generate weather summary. Please try again later.")
                return

            # Prepare a simplified preview of the raw data (limited to avoid huge messages)
            preview_data = {}
            for city_name, data in raw_forecasts.items():
                if "error" not in data:
                    if "current" in data:
                        # For OpenMeteo
                        preview_data[city_name] = {
                            "temp": f"{data.get('current', {}).get('temperature_2m', 'N/A')}{data.get('temperature_unit', '°C')}",
                            "humidity": f"{data.get('current', {}).get('relative_humidity_2m', 'N/A')}%",
                            "conditions": self._get_condition_text(data)
                        }
                    elif "properties" in data and "periods" in data["properties"]:
                        # For Weather.gov
                        period = data["properties"]["periods"][0] if data["properties"]["periods"] else {}
                        preview_data[city_name] = {
                            "temp": f"{period.get('temperature', 'N/A')}{data.get('temperature_unit', '°F')}",
                            "humidity": f"{period.get('relativeHumidity', {}).get('value', 'N/A')}%",
                            "conditions": period.get("shortForecast", "Unknown")
                        }

            # Format preview data as string, limited to 500 chars
            consolidated_data = json.dumps(preview_data, indent=2)[:500] + "..."

            # Send back the summary
            await ctx.send(
                f"**Weather Summary:**\n{summary}\n\n*Data preview:*\n```\n{consolidated_data}\n```"
            )
        except Exception as e:
            logger.exception("Error generating weather summary: %s", str(e))
            await ctx.send(f"An error occurred while generating the weather summary: {e!s}")

    def _get_condition_text(self, data):
        """Extract weather condition text from OpenMeteo data."""
        if "daily" in data and "weather_code" in data["daily"] and data["daily"]["weather_code"]:
            weather_code = data["daily"]["weather_code"][0]
            # Map known weather codes to text descriptions
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
                61: "Slight rain",
                63: "Moderate rain",
                65: "Heavy rain",
                71: "Slight snow fall",
                73: "Moderate snow fall",
                75: "Heavy snow fall",
                80: "Slight rain showers",
                81: "Moderate rain showers",
                82: "Violent rain showers",
                95: "Thunderstorm"
            }
            return weather_codes.get(weather_code, f"Code {weather_code}")
        return "Unknown"

    @weather_summary_slash_command.autocomplete("city")
    async def weather_summary_autocomplete(self, _: discord.Interaction, current: str):
        """Provide autocomplete for city parameter."""
        choices = await self.config_manager.get_city_choices()
        return [choice for choice in choices if current.lower() in choice.name.lower()]

    async def forecast_task(self):
        int(datetime.now(tz=UTC).timestamp())

        default_locations = await self.config_manager.get_default_locations(self.guild_id)
        if not default_locations:
            logger.warning("No default locations set for this guild.")
            msg = "No default locations configured"
            raise ValueError(msg)

        channel_id = await self.config_manager.get_weather_channel(self.guild_id)
        channel = self.bot.get_channel(channel_id)

        if not channel:
            logger.warning("Weather channel not found.")
            msg = "Weather channel not found or not configured"
            raise ValueError(msg)

        # Use the service to fetch and format weather data
        forecasts = await self.weather_service.fetch_all_locations_weather(default_locations)

        if not forecasts:
            logger.warning("No valid weather data to report in forecast task.")
            return

        # Use the service to format the table
        table_string = await self.weather_service.format_forecast_table(forecasts)

        # Fetch raw data for summary
        raw_forecasts = await self.weather_service.fetch_raw_data_for_summary("Everywhere", default_locations)

        # Generate AI summary from raw data
        summary = ""
        if raw_forecasts and not all("error" in data for city_name, data in raw_forecasts.items()):
            summary = await self.weather_service.get_weather_summary_from_raw(raw_forecasts)

        # Build final message
        message_content = (
            f"{self.strings['weather_report_title']}\n"
            f"```{table_string}```"
            f"{summary if summary else ''}"
        )

        await channel.send(message_content, allowed_mentions=discord.AllowedMentions.none())

    # Create a subgroup for settings
    set_group = app_commands.Group(
        name="set",
        description="Configure weather settings",
        parent=weather  # Specify the parent directly
    )

    @set_group.command(
        name="channel",
        description="Set the channel for daily weather updates (Admin only)"
    )
    @app_commands.describe(
        channel="The text channel where daily weather reports will be posted"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def weather_set_channel_slash_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        Configure the channel where daily weather updates will be posted (slash command version).

        Parameters
        ----------
        interaction
            The Discord interaction
        channel
            The text channel where daily weather reports will be posted

        """
        logger.info(
            "Command weather set channel (slash) invoked by %s with channel: %s",
            interaction.user, channel.mention
        )
        ctx = await commands.Context.from_interaction(interaction)
        await self._weather_set_channel_logic(ctx, channel)

    @weather_group.group(name="set", aliases=["config"])
    @commands.has_permissions(administrator=True)
    async def weather_set_group(self, ctx):
        """Commands for configuring weather settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a setting to configure. Available options: `channel`")

    @weather_set_group.command(
        name="channel",
        description="Set the channel for daily weather updates (Admin only)"
    )
    async def weather_set_channel_text_command(self, ctx, channel: discord.TextChannel):
        """
        Configure the channel where daily weather updates will be posted (text command version).

        Parameters
        ----------
        ctx
            The command context
        channel
            The text channel where daily weather reports will be posted

        """
        logger.info(
            "Command weather set channel (text) invoked by %s with channel: %s",
            ctx.author, channel.mention
        )
        await self._weather_set_channel_logic(ctx, channel)

    async def _weather_set_channel_logic(self, ctx, channel: discord.TextChannel):
        """
        Shared logic for setting weather channel commands.

        Parameters
        ----------
        ctx
            The command context
        channel
            The text channel where daily weather reports will be posted

        """
        try:
            await self.config_manager.set_weather_channel(ctx.guild.id, channel.id)
            # Use message from strings.json
            success_message = self.strings["messages"]["weather_channel_set_success"].format(channel_mention=channel.mention)
            await ctx.send(success_message)
            logger.info(
                "Weather channel set to %s for guild %s (ID: %s)",
                channel.mention, ctx.guild.name, ctx.guild.id
            )
        except Exception:
            logger.exception("Failed to set weather channel for guild %s (ID: %s)", ctx.guild.name, ctx.guild.id)
            # Use string from strings.json
            await ctx.send(self.strings["errors"]["weather_channel_set_error"])

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        """Handle errors from slash commands."""
        logger.error("Slash command error: %s", error)
        if interaction.response.is_done():
            await interaction.followup.send(f"An error occurred: {error}")
        else:
            await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)

    @weather.command(
        name="schedule",
        description="Check when the next weather forecast is scheduled"
    )
    async def weather_schedule_slash_command(self, interaction: discord.Interaction):
        """
        Check when the next weather forecast is scheduled (slash command version).

        Parameters
        ----------
        interaction
            The Discord interaction

        """
        logger.info("Command weather schedule (slash) invoked by %s", interaction.user)
        ctx = await commands.Context.from_interaction(interaction)
        await self._weather_schedule_logic(ctx)

    @weather_group.command(
        name="schedule",
        aliases=["sched", "when"],
        description="Check when the next weather forecast is scheduled"
    )
    async def weather_schedule_text_command(self, ctx):
        """
        Check when the next weather forecast is scheduled (text command version).

        Parameters
        ----------
        ctx
            The command context

        """
        logger.info("Command weather schedule (text) invoked by %s", ctx.author)
        await self._weather_schedule_logic(ctx)

    async def _weather_schedule_logic(self, ctx):
        """
        Shared logic for weather schedule commands.

        Parameters
        ----------
        ctx
            The command context

        """
        embed = discord.Embed(
            title="Weather Forecast Schedule",
            color=discord.Color.blue()
        )

        # Check if scheduler is active
        if not self.scheduler_active or not self.next_forecast_time:
            embed.description = "⚠️ The weather scheduler is not active."
            await ctx.send(embed=embed)
            return

        # Get channel information
        channel_id = await self.config_manager.get_weather_channel(self.guild_id)
        channel = self.bot.get_channel(channel_id)
        channel_mention = channel.mention if channel else "Not configured"

        # Calculate time until next forecast
        now_utc = datetime.now(pytz.utc)
        time_until = self.next_forecast_time - now_utc
        hours, remainder = divmod(time_until.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        # Format next forecast time in user-friendly way
        eastern = pytz.timezone("America/New_York")
        next_time_formatted = self.next_forecast_time.astimezone(eastern).strftime("%A, %B %d at %I:%M %p %Z")

        # Add information to embed
        embed.add_field(
            name="Next Forecast",
            value=f"📅 {next_time_formatted}",
            inline=False
        )

        embed.add_field(
            name="Time Until Next Forecast",
            value=f"⏱️ {hours} hours, {minutes} minutes",
            inline=False
        )

        embed.add_field(
            name="Forecast Channel",
            value=f"📣 {channel_mention}",
            inline=False
        )

        # Add last run information if available
        if self.last_forecast_time:
            last_run_time = self.last_forecast_time.astimezone(eastern).strftime("%A, %B %d at %I:%M %p %Z")
            status = "✅ Successful" if self.last_forecast_success else "❌ Failed"
            embed.add_field(
                name="Last Forecast Run",
                value=f"🕒 {last_run_time}\nStatus: {status}",
                inline=False
            )

        await ctx.send(embed=embed)
