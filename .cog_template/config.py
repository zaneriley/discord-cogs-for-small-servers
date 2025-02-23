import hashlib

from redbot.core import Config


class ConfigManager:
    def __init__(self, cog_instance):
        self.config = self._init_config(cog_instance)

    def _init_config(self, cog_instance):
        cog_name = cog_instance.__class__.__name__
        identifier = int(hashlib.sha256(cog_name.encode()).hexdigest(), 16) % 10**10
        return Config.get_conf(
            cog_instance,
            identifier=identifier,
            force_registration=True
        )

    async def setup_defaults(self):
        await self.config.register_guild(
            example_setting="default_value",
            # Add other default settings
        )

    async def set_NAME_OF_DATA(self, guild_id: int, location: str):
        await self.config.guild_from_id(guild_id).NAME_OF_DATA.set(location)

    async def get_NAME_OF_DATAs(self, guild_id: int):
        locations = await self.config.guild_from_id(guild_id).NAME_OF_DATAs()
        for city, (api_type, coord_str) in locations.items():
            locations[city] = (api_type, tuple(map(float, coord_str.split(","))))
        return locations
