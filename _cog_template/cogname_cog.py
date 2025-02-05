import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from redbot.core import commands, Config

from .config import ConfigManager
from .strings import load_cog_strings

logger = logging.getLogger(__name__)

class TemplateCog(commands.Cog):
    """Description of cog functionality"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ConfigManager(self)
        self.strings = load_cog_strings(Path(__file__).parent)
        
        # Example task initialization
        # self.background_task.start()

    def cog_unload(self):
        # Example task cleanup
        # self.background_task.cancel()

    # Example hybrid command group
    @app_commands.command()
    @app_commands.describe(arg="Description of argument")
    async def example(self, interaction: discord.Interaction, arg: str):
        """Base command description"""
        await interaction.response.defer()
        try:
            # Command logic here
            await interaction.followup.send(f"Processed: {arg}")
        except Exception as e:
            logger.error(f"Error in example command: {str(e)}")
            await interaction.followup.send("An error occurred processing your request", ephemeral=True)

    # Example background task
    # @tasks.loop(minutes=60)
    # async def background_task(self):
    #     logger.debug("Running maintenance task")
    #     # Task logic here

async def setup(bot: commands.Bot):
    await bot.add_cog(TemplateCog(bot))
