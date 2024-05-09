import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

import discord
from discord.ext import commands
from discord.errors import HTTPException, NotFound, Forbidden
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red


from .dialogs import DialogManager
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))


# TODO: Move to a database or something, this is just to mock up data.
class Character:
    def __init__(self, name: str):
        self.name = name
        self.weapons: List[str] = []
        self.armor: List[str] = []
        self.items: List[str] = []
        self.health: int = 100
        self.level: int = 1
        self.experience: int = 0


class UserData:
    def __init__(self):
        self.characters: List[Character] = []
        self.active_character: Optional[Character] = None

    def create_character(self, name: str) -> bool:
        if any(char for char in self.characters if char.name == name):
            logger.debug(f"Character '{name}' already exists.")
            return False
        char = Character(name)
        self.characters.append(char)
        if not self.active_character:
            self.active_character = char
        return True

    def switch_character(self, name: str) -> bool:
        for char in self.characters:
            if char.name == name:
                self.active_character = char
                return True
        return False

    def get_active_character(self) -> Optional[Character]:
        return self.active_character


class CharacterNameModal(discord.ui.Modal, title="Create a new character"):
    def __init__(self, onboarding_cog: commands.Cog, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dialog_manager = DialogManager()
        create_character_prompt = self.dialog_manager.get_dialog(
            "CREATE_CHARACTER_PROMPT"
        )

        self.add_item(
            discord.ui.TextInput(
                label=create_character_prompt, placeholder="Enter a character name"
            )
        )
        self.onboarding_cog = onboarding_cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        char_name = self.children[0].value
        try:
            create_character_start_msg = self.onboarding_cog.dialog_manager.get_dialog(
                "CREATE_CHARACTER_START"
            )
            await interaction.response.send_message(
                create_character_start_msg, ephemeral=True
            )

            user_data = self.onboarding_cog.get_or_create_user_data(
                interaction.user.id, interaction.guild.id
            )
            if user_data.create_character(char_name):
                create_character_msg = self.onboarding_cog.dialog_manager.get_dialog(
                    "CREATE_CHARACTER_FINISH"
                ).format(char_name=char_name)
                await interaction.followup.send(create_character_msg, ephemeral=True)
            else:
                char_exists_msg = self.onboarding_cog.dialog_manager.get_dialog(
                    "CHARACTER_EXISTS"
                ).format(char_name=char_name)
                await interaction.followup.send(char_exists_msg, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in on_submit of CharacterNameModal: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while creating the character.", ephemeral=True
            )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        logger.error(f"Error in CharacterNameModal: {str(error)}")
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )


class RPG(commands.Cog):
    """
    RPG Cog for managing role-playing game features in Discord.
    """

    def __init__(self, bot: Red) -> None:
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
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dialog_manager = DialogManager()
        self.user_data: Dict[str, UserData] = {}

    def get_user_key(self, user_id: int, guild_id: int) -> str:
        return f"{user_id}_{guild_id}"

    def get_or_create_user_data(self, user_id: int, guild_id: int) -> UserData:
        key = self.get_user_key(user_id, guild_id)
        if key not in self.user_data:
            self.user_data[key] = UserData()
        return self.user_data[key]

    @app_commands.guild_only()
    @app_commands.command(name="start", description="Join the game")
    async def start(self, interaction: discord.Interaction):
        try:
            user_data = self.get_or_create_user_data(
                interaction.user.id, interaction.guild.id
            )
            # ... rest of your logic ...

        except (HTTPException, NotFound, Forbidden) as e:
            logger.error(f"Error in start command: {str(e)}")

    @app_commands.command(name="create", description="Create a new character")
    @app_commands.guild_only()
    async def create_character(self, interaction: discord.Interaction) -> None:
        try:
            modal_msg = self.dialog_manager.get_dialog("CREATE_CHARACTER_PROMPT")

            modal = CharacterNameModal(onboarding_cog=self, title=modal_msg)
            await interaction.response.send_modal(modal)
        except (HTTPException, NotFound, Forbidden) as e:
            logger.error(f"Error in create_character command: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while processing the command.", ephemeral=True
            )

    @app_commands.command(name="switch", description="Switch to a different character")
    @app_commands.guild_only()
    async def switch_character(self, interaction: discord.Interaction, char_name: str):
        try:
            user_data = self.get_or_create_user_data(
                interaction.user.id, interaction.guild.id
            )
            if user_data.switch_character(char_name):
                active_char = user_data.get_active_character()
                await interaction.response.send_message(
                    f"Switched to '{char_name}'! Health: {active_char.health}, Level: {active_char.level}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Character '{char_name}' not found!", ephemeral=True
                )

        except (HTTPException, NotFound, Forbidden) as e:
            logger.error(f"Error in switch_character command: {str(e)}")


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
