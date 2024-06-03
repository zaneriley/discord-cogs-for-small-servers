import hashlib
import os

from redbot.core import Config


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
        default_guild = {
            "guild_id": guild_id,
        }
        self.config.register_guild(**default_guild)

    async def set_NAME_OF_DATA(self, guild_id: int, location: str):
        await self.config.guild_from_id(guild_id).NAME_OF_DATA.set(location)

    async def get_NAME_OF_DATAs(self, guild_id: int):
        locations = await self.config.guild_from_id(guild_id).NAME_OF_DATAs()
        for city, (api_type, coord_str) in locations.items():
            locations[city] = (api_type, tuple(map(float, coord_str.split(","))))
        return locations
