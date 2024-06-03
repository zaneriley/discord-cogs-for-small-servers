import logging
import os

from discord import app_commands
from redbot.core import commands

from .config import ConfigManager

logger = logging.getLogger(__name__)


class NameOfCog(commands.Cog):

    """What cog does"""

    def __init__(self, bot):
        self.bot = bot
        self.guild_id = int(os.getenv("GUILD_ID"))
        self.config_manager = ConfigManager(self.guild_id, self)

    def cog_unload(self):
        pass

    @app_commands.group(name="name", description="Commands related to name")
    async def name(self, ctx):
        """Commands related to name"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid name command passed.")
