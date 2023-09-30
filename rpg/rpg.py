import os
from collections import defaultdict
from typing import Dict, Union, List, Optional

from dotenv import load_dotenv

load_dotenv()

import discord
from redbot.core import commands, app_commands, Config

from dialogs.dialogs import DialogManager

from ..logging_config import get_logger

logger = get_logger(__name__)


IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))


class RPG(commands.Cog):
    """
    RPG Cog for managing role-playing game features in Discord.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the RPG Cog.

        Args:
            bot (commands.Bot): The Red bot instance.
        """
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=IDENTIFIER, force_registration=True
        )
        self.dialog_manager = DialogManager()


class Onboarding(commands.Cog):
    """
    Handles character creation and other onboarding features.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dialog_manager = DialogManager()

    @app_commands.command(name="start", description="Begin your RPG adventure!")
    async def start(self, interaction: discord.Interaction):
        # Welcome the player
        await interaction.response.send_message(
            "Welcome to the world of RPG Adventure!", ephemeral=True
        )

        # Guide through character creation
        await interaction.followup.send(
            "Let's create your character. What will you be called?"
        )

    @app_commands.command(name="create character", description="Create a character.")
    @app_commands.guild_only()
    async def create_character(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Let's create a new character!", ephemeral=True
        )


class Inventory(commands.Cog):
    """
    Handles inventory management.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dialog_manager = DialogManager()

    @app_commands.command(
        name="inventory", description="View your RPG character's inventory."
    )
    @app_commands.guild_only()
    async def inventory(self, interaction: discord.Interaction):
        inventory_msg = self.dialog_manager.get_dialog("INVENTORY")
        await interaction.response.send_message(inventory_msg, ephemeral=True)
