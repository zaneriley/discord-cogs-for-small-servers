import hashlib
import json
import logging
import os

from redbot.core import Config

logger = logging.getLogger(__name__)


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
        default_locations = json.loads(os.getenv("WX_LOCATIONS", "{}"))
        default_guild = {"guild_id": guild_id, "default_locations": default_locations, "weather_channel_id": None}
        self.config.register_guild(**default_guild)

    async def set_default_location(self, guild_id: int, location: str):
        await self.config.guild_from_id(guild_id).default_location.set(location)

    async def get_default_locations(self, guild_id: int):
        locations = await self.config.guild_from_id(guild_id).default_locations()
        for city, (api_type, coord_str) in locations.items():
            locations[city] = (api_type, tuple(map(float, coord_str.split(","))))
        return locations

    async def set_weather_channel(self, guild_id: int, channel_id: int):
        await self.config.guild_from_id(guild_id).weather_channel_id.set(channel_id)

    async def get_weather_channel(self, guild_id: int):
        return await self.config.guild_from_id(guild_id).weather_channel_id()
