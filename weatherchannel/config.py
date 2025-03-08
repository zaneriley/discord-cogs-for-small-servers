from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from discord import app_commands
from redbot.core import Config

logger = logging.getLogger(__name__)

# Path to the cities.json file
CITIES_FILE = Path(__file__).parent / "cities.json"

class ConfigManager:
    def __init__(self, guild_id, cog_instance):
        cog_name = cog_instance.__class__.__name__
        identifier = int(hashlib.sha256(cog_name.encode()).hexdigest(), 16) % 10**10
        get_guild_id_from_env = int(os.getenv("GUILD_ID", None))
        set_guild_id = guild_id or get_guild_id_from_env
        if set_guild_id is None:
            error_no_guild_id = "No GUILD_ID passed or set from .env file."
            raise ValueError(error_no_guild_id)

        self.config = Config.get_conf(cog_instance, identifier=identifier, force_registration=True)
        logger.info("Config: %s", self.config)

        # Load city data from file
        self.cities_data = self.load_cities_data()

        # Always use cities.json as the single source of truth
        default_locations = {}
        if self.cities_data and "cities" in self.cities_data:
            for city_name, city_info in self.cities_data["cities"].items():
                coords_str = f"{city_info['coordinates'][0]},{city_info['coordinates'][1]}"
                default_locations[city_name] = (city_info["api_type"], coords_str)

        default_guild = {
            "guild_id": guild_id,
            "default_locations": default_locations,
            "weather_channel_id": None
        }
        self.config.register_guild(**default_guild)

    def load_cities_data(self) -> dict:
        """Load cities data from the JSON file."""
        try:
            if CITIES_FILE.exists():
                with CITIES_FILE.open() as f:
                    return json.load(f)
            else:
                logger.warning("Cities file not found: %s", CITIES_FILE)
                return {}
        except Exception:
            logger.exception("Error loading cities data")
            return {}

    async def set_default_location(self, guild_id: int, location: str):
        await self.config.guild_from_id(guild_id).default_location.set(location)

    async def get_default_locations(self, guild_id: int) -> dict[str, tuple[str, tuple[float, float]]]:
        """Get default locations with coordinates as tuples."""
        locations = await self.config.guild_from_id(guild_id).default_locations()
        for city, (api_type, coord_str) in locations.items():
            locations[city] = (api_type, tuple(map(float, coord_str.split(","))))
        return locations

    async def get_city_choices(self) -> list[app_commands.Choice]:
        """Get city choices for Discord command UI."""
        choices = []

        # Add city choices from cities.json
        if self.cities_data and "cities" in self.cities_data:
            for city_name, city_info in self.cities_data["cities"].items():
                display_name = city_info.get("display_name", city_name)
                choices.append(app_commands.Choice(name=display_name, value=city_name))

        # Add special options
        if self.cities_data and "special_options" in self.cities_data:
            for option_name, option_info in self.cities_data["special_options"].items():
                display_name = option_info.get("display_name", option_name)
                choices.append(app_commands.Choice(name=display_name, value=option_name))

        # If no choices from file, fall back to Everywhere option
        if not choices:
            choices.append(app_commands.Choice(name="Everywhere", value="Everywhere"))

        return choices

    async def set_weather_channel(self, guild_id: int, channel_id: int):
        await self.config.guild_from_id(guild_id).weather_channel_id.set(channel_id)

    async def get_weather_channel(self, guild_id: int):
        return await self.config.guild_from_id(guild_id).weather_channel_id()
