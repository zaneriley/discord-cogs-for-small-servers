"""
HolidayAnnouncer service for the SeasonalRoles cog.

This service manages all holiday-related announcements, including:
- Upcoming holiday notifications (7 days before)
- Holiday start announcements (day of)
- Holiday end announcements (day after)

It handles message templates, styling, and delivery to configured channels.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from cogs.utilities.announcement_utils import (
    HOLIDAY_STYLES,
    create_embed_announcement,
    preview_announcement,
    send_holiday_announcement,
)
from cogs.utilities.date_utils import DateUtil

if TYPE_CHECKING:
    from redbot.core import Config
    from redbot.core.bot import Red
    from redbot.core.commands import Context

    from .holiday.holiday_data import Holiday

log = logging.getLogger("red.seasonalroles.holiday_announcer")

# Message template placeholders
HOLIDAY_NAME_PLACEHOLDER = "{holiday_name}"
HOLIDAY_DATE_PLACEHOLDER = "{holiday_date}"
HOLIDAY_COLOR_PLACEHOLDER = "{holiday_color}"
DAYS_UNTIL_PLACEHOLDER = "{days_until}"
SERVER_NAME_PLACEHOLDER = "{server_name}"

# Default message templates
DEFAULT_TEMPLATES = {
    "before": {
        "title": f"Upcoming Holiday: {HOLIDAY_NAME_PLACEHOLDER}",
        "description": f"Get ready for {HOLIDAY_NAME_PLACEHOLDER} in {DAYS_UNTIL_PLACEHOLDER} days! It will be celebrated on {HOLIDAY_DATE_PLACEHOLDER}.",
    },
    "during": {
        "title": f"Happy {HOLIDAY_NAME_PLACEHOLDER}!",
        "description": f"Today is {HOLIDAY_NAME_PLACEHOLDER}! Celebrate with us and enjoy this special day.",
    },
    "after": {
        "title": f"{HOLIDAY_NAME_PLACEHOLDER} has ended",
        "description": f"Hope you enjoyed {HOLIDAY_NAME_PLACEHOLDER}! See you next time.",
    }
}

# Constants for announcement phases
PHASE_BEFORE = "before"
PHASE_DURING = "during"
PHASE_AFTER = "after"

# Constant for days before announcement
DAYS_BEFORE_ANNOUNCEMENT = 7

class HolidayAnnouncer:

    """
    Service class for managing holiday announcements.

    This class handles the creation and delivery of holiday announcements
    for different phases (before, during, after) of holidays.
    """

    def __init__(self, bot: Red, config: Config):
        """
        Initialize the HolidayAnnouncer service.

        Args:
            bot: The Red Discord bot instance
            config: The Red config instance for accessing guild configuration

        """
        self.bot = bot
        self.config = config
        self.default_templates = DEFAULT_TEMPLATES

        # Setup data directory and load holidays data
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.holidays_data = self._load_holidays_data()

    def _load_holidays_data(self) -> dict:
        """
        Load holiday data from holidays.json.

        Returns:
            Dictionary containing holiday data

        """
        # First try to load from the root of the cog folder
        cog_dir = Path(__file__).parent
        holidays_file = cog_dir / "holidays.json"

        # Check if the file exists
        if not holidays_file.exists():
            log.warning("holidays.json not found in cog directory, checking data directory...")
            # Fall back to data directory
            holidays_file = self.data_dir / "holidays.json"
            if not holidays_file.exists():
                log.warning("holidays.json not found in data directory")
                return {}

        try:
            with holidays_file.open("r") as f:
                log.info(f"Loading holidays data from {holidays_file}")
                return json.load(f)
        except json.JSONDecodeError:
            log.exception("Error parsing holidays.json")
            return {}
        except FileNotFoundError:
            # If not found, create a new holidays json file
            with holidays_file.open("w") as f:
                json.dump({"holidays": [], "categories": []}, f, indent=4)
            log.info(f"Created new holidays file at {holidays_file}")
            return {}
        except OSError:
            log.exception("Error loading holidays.json")
            return {}

    async def get_announcement_config(self, guild_id: int) -> dict[str, Any]:
        """
        Get the announcement configuration for a guild.

        Args:
            guild_id: The ID of the guild

        Returns:
            The announcement configuration dictionary

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return {}

        return await self.config.guild(guild).announcement_config()

    async def set_announcement_enabled(self, guild_id: int, *, is_enabled: bool) -> bool:
        """
        Enable or disable announcements for a guild.

        Args:
            guild_id: The ID of the guild
            is_enabled: Whether announcements should be enabled

        Returns:
            True if successful, False otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return False

        await self.config.guild(guild).announcement_config.set_raw("enabled", value=is_enabled)
        log.info(f"Announcement {'enabled' if is_enabled else 'disabled'} for guild {guild.name}")
        return True

    async def set_announcement_channel(self, guild_id: int, channel_id: int) -> bool:
        """
        Set the channel for announcements.

        Args:
            guild_id: The guild ID
            channel_id: The channel ID

        Returns:
            bool: True if successful, False otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return False

        # Verify the channel exists
        if channel_id:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.HTTPException, discord.Forbidden) as e:
                log.warning(f"Channel with ID {channel_id} not found: {e}")
                return False

            if not channel:
                return False

        # Update the config
        async with self.config.guild(guild).announcement_config() as config:
            config["channel_id"] = channel_id

        return True

    async def set_mention_settings(self, guild_id: int, mention_type: str | None, mention_id: int | None = None) -> bool:
        """
        Set the mention settings for announcements.

        Args:
            guild_id: The ID of the guild
            mention_type: The type of mention (everyone, here, role, or None)
            mention_id: The ID of the role to mention (only used if mention_type is 'role')

        Returns:
            True if successful, False otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return False

        # Validate mention settings
        if mention_type not in (None, "everyone", "here", "role"):
            log.warning(f"Invalid mention type: {mention_type}")
            return False

        if mention_type == "role" and mention_id is None:
            log.warning("Role ID must be provided when mention type is 'role'")
            return False

        # Save mention settings
        await self.config.guild(guild).announcement_config.set_raw("mention_type", value=mention_type)
        await self.config.guild(guild).announcement_config.set_raw("role_id", value=mention_id)

        log.info(f"Announcement mention settings updated for guild {guild.name}")
        return True

    async def set_template(self, guild_id: int, holiday_name: str, phase: str, template: dict[str, str]) -> bool:
        """
        Set a custom template for a specific holiday and phase.

        Args:
            guild_id: The ID of the guild
            holiday_name: The name of the holiday
            phase: The phase of the holiday (before, during, after)
            template: Dictionary containing title and description for the template

        Returns:
            True if successful, False otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return False

        # Validate phase
        if phase not in ("before", "during", "after"):
            log.warning(f"Invalid phase: {phase}. Must be 'before', 'during', or 'after'.")
            return False

        # Validate template
        if not isinstance(template, dict) or "title" not in template or "description" not in template:
            log.warning("Template must be a dictionary with 'title' and 'description' keys")
            return False

        # Save template
        templates = await self.config.guild(guild).announcement_config.get_raw("templates", default={})

        # Initialize holiday dictionary if it doesn't exist
        if holiday_name not in templates:
            templates[holiday_name] = {}

        # Set the template for the specific phase
        templates[holiday_name][phase] = template

        # Save back to config
        await self.config.guild(guild).announcement_config.set_raw("templates", value=templates)

        log.info(f"Custom template set for '{holiday_name}' ({phase}) in guild {guild.name}")
        return True

    async def get_template(self, guild_id: int, holiday_name: str, phase: str) -> dict[str, str] | None:
        """
        Get a custom template for a specific holiday and phase.

        Args:
            guild_id: The ID of the guild
            holiday_name: The name of the holiday
            phase: The phase of the holiday (before, during, after)

        Returns:
            The custom template if it exists, None otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return None

        # Validate phase
        if phase not in ("before", "during", "after"):
            log.warning(f"Invalid phase: {phase}. Must be 'before', 'during', or 'after'.")
            return None

        try:
            templates = await self.config.guild(guild).announcement_config.get_raw("templates", default={})
            if holiday_name in templates and phase in templates[holiday_name]:
                return templates[holiday_name][phase]
        except (KeyError, TypeError):
            log.exception("Error getting template")
            return None
        else:
            return None

    async def list_templates(self, guild_id: int) -> dict[str, dict[str, dict[str, str]]]:
        """
        List all custom templates for a guild.

        Args:
            guild_id: The ID of the guild

        Returns:
            Dictionary of all custom templates grouped by holiday and phase

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return {}

        return await self.config.guild(guild).announcement_config.get_raw("templates", default={})

    async def delete_template(self, guild_id: int, holiday_name: str, phase: str | None = None) -> bool:
        """
        Delete a custom template for a specific holiday and optionally a specific phase.

        Args:
            guild_id: The ID of the guild
            holiday_name: The name of the holiday
            phase: The phase of the holiday (before, during, after), if None all phases will be deleted

        Returns:
            True if successful, False otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild with ID {guild_id} not found")
            return False

        # Validate phase if provided
        if phase is not None and phase not in ("before", "during", "after"):
            log.warning(f"Invalid phase: {phase}. Must be 'before', 'during', or 'after'.")
            return False

        try:
            templates = await self.config.guild(guild).announcement_config.get_raw("templates", default={})

            # Check if the holiday exists
            if holiday_name not in templates:
                log.warning(f"No templates found for holiday '{holiday_name}'")
                return False

            # Delete the specific phase or the entire holiday
            if phase is None:
                # Delete the entire holiday
                del templates[holiday_name]
                log.info(f"Deleted all templates for holiday '{holiday_name}' in guild {guild.name}")
            else:
                # Delete the specific phase
                if phase in templates[holiday_name]:
                    del templates[holiday_name][phase]
                    log.info(f"Deleted template for '{holiday_name}' ({phase}) in guild {guild.name}")
                else:
                    log.warning(f"No template found for '{holiday_name}' ({phase})")
                    return False

                # If no phases left, delete the holiday entry
                if not templates[holiday_name]:
                    del templates[holiday_name]

            # Save back to config
            await self.config.guild(guild).announcement_config.set_raw("templates", value=templates)
        except Exception:
            log.exception("Error deleting template")
            return False
        else:
            return True

    async def get_holiday_message(
        self,
        holiday: Holiday,
        phase: str,
        guild_id: int,
        custom_templates: dict[str, dict[str, str]] | None = None,
        days_until: int | None = None
    ) -> dict[str, Any]:
        """
        Get the appropriate message template for a holiday and phase.

        Args:
            holiday: The holiday object
            phase: The phase of the holiday (before, during, after)
            guild_id: The ID of the guild
            custom_templates: Optional custom templates to use instead of defaults
            days_until: Optional number of days until holiday (for 'before' phase)

        Returns:
            Dict containing the message template with placeholders replaced

        """
        # Check if we have flavortext for this holiday in our JSON data
        holiday_name = holiday.name
        if holiday_name in self.holidays_data and "announcements" in self.holidays_data[holiday_name]:
            holiday_announcements = self.holidays_data[holiday_name]["announcements"]
            if phase in holiday_announcements:
                # Build minimal embed parameters from JSON data
                embed_params = {}

                # Add title if available
                if "title" in holiday_announcements[phase]:
                    embed_params["title"] = holiday_announcements[phase]["title"]

                # Add footer if available
                if "footer" in holiday_announcements[phase]:
                    footer_text = holiday_announcements[phase]["footer"]

                    # Replace placeholders
                    # Replace holiday name placeholder
                    if "{holiday_name}" in footer_text:
                        # Use a display name if available, otherwise use the holiday name
                        display_name = self.holidays_data[holiday_name].get("display_name", holiday_name)
                        footer_text = footer_text.replace("{holiday_name}", display_name)

                    # Replace days until placeholder
                    if days_until is not None and "{days_until}" in footer_text:
                        footer_text = footer_text.replace("{days_until}", str(days_until))

                    embed_params["footer_text"] = footer_text

                # Add color from holiday data
                if "color" in self.holidays_data[holiday_name]:
                    color_hex = self.holidays_data[holiday_name]["color"]
                    embed_params["color"] = int(color_hex[1:], 16)

                # Add image if available
                if "image" in self.holidays_data[holiday_name]:
                    embed_params["image_url"] = self.holidays_data[holiday_name]["image"]

                return {
                    "holiday_name": holiday_name,
                    "phase": phase,
                    "embed_params": embed_params,
                    "mention_type": None,  # Will be set by the calling function
                    "mention_id": None,    # Will be set by the calling function
                }

        # If no custom holiday data found, fall back to existing template logic
        # Get the template based on phase
        templates = custom_templates or self.default_templates

        # Check if there are custom templates in the config for this holiday and phase
        if not custom_templates:
            guild = self.bot.get_guild(guild_id)
            if guild:
                try:
                    # Get custom templates from the config
                    config_templates = await self.config.guild(guild).announcement_config.get_raw(
                        "templates", default={}
                    )

                    # Check if there's a custom template for this holiday
                    holiday_name = holiday.name.lower()
                    if holiday_name in config_templates and phase in config_templates[holiday_name]:
                        # Use the custom template from config
                        phase_templates = templates.copy()
                        phase_templates[phase] = config_templates[holiday_name][phase]
                        templates = phase_templates
                        log.debug(f"Using custom template for '{holiday.name}' ({phase})")
                except Exception:
                    log.exception("Error getting custom templates")
                    # Fall back to default templates

        if phase not in templates:
            log.warning(f"Template for phase '{phase}' not found, using 'during' instead")
            phase = "during"  # Default to "during" phase if phase not found

        # Get the base template
        template = templates[phase].copy()

        # Get the guild name for placeholders
        guild = self.bot.get_guild(guild_id)
        server_name = guild.name if guild else "Server"

        # Get a presentable date string
        holiday_date = DateUtil.get_presentable_date(holiday.month, holiday.day)

        # Replace common placeholders
        for key, value in template.items():
            if isinstance(value, str):
                # Create a new variable for the updated value
                updated_value = value

                # Replace holiday name
                updated_value = updated_value.replace(HOLIDAY_NAME_PLACEHOLDER, holiday.name)

                # Replace holiday date
                updated_value = updated_value.replace(HOLIDAY_DATE_PLACEHOLDER, holiday_date)

                # Replace server name
                updated_value = updated_value.replace(SERVER_NAME_PLACEHOLDER, server_name)

                # Replace days until (for before phase)
                if days_until is not None and DAYS_UNTIL_PLACEHOLDER in updated_value:
                    updated_value = updated_value.replace(DAYS_UNTIL_PLACEHOLDER, str(days_until))

                template[key] = updated_value

        # Apply holiday styling (colors, etc)
        holiday_name_lower = holiday.name.lower()
        if holiday_name_lower in HOLIDAY_STYLES and phase in HOLIDAY_STYLES[holiday_name_lower]:
            # Add color and other styling elements from announcement_utils.HOLIDAY_STYLES
            style_params = HOLIDAY_STYLES[holiday_name_lower][phase]
            for style_key, style_value in style_params.items():
                template[style_key] = style_value

        return {
            "holiday_name": holiday.name,
            "phase": phase,
            "embed_params": template,
            "mention_type": None,  # Will be set by the calling function
            "mention_id": None,    # Will be set by the calling function
        }

    async def announce_upcoming_holiday(
        self,
        holiday: Holiday,
        guild_id: int,
        channel_id: int | None = None,
        mention_type: str | None = None,
        mention_id: int | None = None,
        custom_templates: dict[str, dict[str, str]] | None = None
    ) -> tuple[bool, str | None]:
        """
        Announce an upcoming holiday (7 days before).

        Args:
            holiday: The holiday object
            guild_id: The ID of the guild
            channel_id: Optional channel ID to override config
            mention_type: Optional mention type to override config
            mention_id: Optional mention ID to override config
            custom_templates: Optional custom templates to use

        Returns:
            Tuple of (success, error_message)

        """
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return False, f"Guild with ID {guild_id} not found"

            # Get announcement config
            announcement_config = await self.get_announcement_config(guild_id)

            # Check if announcements are enabled
            if not announcement_config.get("enabled", False):
                log.debug(f"Announcements are disabled for guild {guild.name}")
                return False, "Announcements are disabled for this guild"

            # Use provided channel_id or get from config
            channel_id = channel_id or announcement_config.get("channel_id")
            if not channel_id:
                return False, "No announcement channel configured"

            # Use provided mention settings or get from config
            mention_type = mention_type or announcement_config.get("mention_type")
            if mention_type == "role":
                mention_id = mention_id or announcement_config.get("role_id")

            # Get the message template with placeholders replaced
            config = await self.get_holiday_message(
                holiday=holiday,
                phase="before",
                guild_id=guild_id,
                custom_templates=custom_templates,
                days_until=7  # Upcoming announcement is 7 days before
            )

            # Set mention details
            config["mention_type"] = mention_type
            config["mention_id"] = mention_id

            # Send the holiday announcement
            log.info(f"Sending upcoming holiday announcement for {holiday.name} to channel {channel_id}")
            success, error = await send_holiday_announcement(
                client=self.bot,
                channel_id=channel_id,
                config=config
            )

            if not success:
                log.error(f"Failed to send upcoming holiday announcement: {error}")
                return False, f"Failed to send announcement: {error}"

            # Update the last announcement timestamp
            await self.update_last_announcement(guild_id, holiday.name, "before")
        except Exception:
            log.exception("Error in announce_upcoming_holiday")
            return False, "An error occurred while sending the announcement"
        else:
            return True, None

    async def announce_holiday_start(
        self,
        holiday: Holiday,
        guild_id: int,
        channel_id: int | None = None,
        mention_type: str | None = None,
        mention_id: int | None = None,
        custom_templates: dict[str, dict[str, str]] | None = None
    ) -> tuple[bool, str | None]:
        """
        Announce the start of a holiday (day of).

        Args:
            holiday: The holiday object
            guild_id: The ID of the guild
            channel_id: Optional channel ID to override config
            mention_type: Optional mention type to override config
            mention_id: Optional mention ID to override config
            custom_templates: Optional custom templates to use

        Returns:
            Tuple of (success, error_message)

        """
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return False, f"Guild with ID {guild_id} not found"

            # Get announcement config
            announcement_config = await self.get_announcement_config(guild_id)

            # Check if announcements are enabled
            if not announcement_config.get("enabled", False):
                log.debug(f"Announcements are disabled for guild {guild.name}")
                return False, "Announcements are disabled for this guild"

            # Use provided channel_id or get from config
            channel_id = channel_id or announcement_config.get("channel_id")
            if not channel_id:
                return False, "No announcement channel configured"

            # Use provided mention settings or get from config
            mention_type = mention_type or announcement_config.get("mention_type")
            if mention_type == "role":
                mention_id = mention_id or announcement_config.get("role_id")

            # Get the message template with placeholders replaced
            config = await self.get_holiday_message(
                holiday=holiday,
                phase="during",  # Holiday start uses "during" phase
                guild_id=guild_id,
                custom_templates=custom_templates
            )

            # Set mention details
            config["mention_type"] = mention_type
            config["mention_id"] = mention_id

            # Send the holiday announcement
            log.info(f"Sending holiday start announcement for {holiday.name} to channel {channel_id}")
            success, error = await send_holiday_announcement(
                client=self.bot,
                channel_id=channel_id,
                config=config
            )

            if not success:
                log.error(f"Failed to send holiday start announcement: {error}")
                return False, f"Failed to send announcement: {error}"

            # Update the last announcement timestamp
            await self.update_last_announcement(guild_id, holiday.name, "during")
        except Exception:
            log.exception("Error in announce_holiday_start")
            return False, "An error occurred while sending the announcement"
        else:
            return True, None

    async def announce_holiday_end(
        self,
        holiday: Holiday,
        guild_id: int,
        channel_id: int | None = None,
        mention_type: str | None = None,
        mention_id: int | None = None,
        custom_templates: dict[str, dict[str, str]] | None = None
    ) -> tuple[bool, str | None]:
        """
        Announce the end of a holiday (day after).

        Args:
            holiday: The holiday object
            guild_id: The ID of the guild
            channel_id: Optional channel ID to override config
            mention_type: Optional mention type to override config
            mention_id: Optional mention ID to override config
            custom_templates: Optional custom templates to use

        Returns:
            Tuple of (success, error_message)

        """
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return False, f"Guild with ID {guild_id} not found"

            # Get announcement config
            announcement_config = await self.get_announcement_config(guild_id)

            # Check if announcements are enabled
            if not announcement_config.get("enabled", False):
                log.debug(f"Announcements are disabled for guild {guild.name}")
                return False, "Announcements are disabled for this guild"

            # Use provided channel_id or get from config
            channel_id = channel_id or announcement_config.get("channel_id")
            if not channel_id:
                return False, "No announcement channel configured"

            # Use provided mention settings or get from config
            mention_type = mention_type or announcement_config.get("mention_type")
            if mention_type == "role":
                mention_id = mention_id or announcement_config.get("role_id")

            # Get the message template with placeholders replaced
            config = await self.get_holiday_message(
                holiday=holiday,
                phase="after",  # Holiday end uses "after" phase
                guild_id=guild_id,
                custom_templates=custom_templates
            )

            # Set mention details
            config["mention_type"] = mention_type
            config["mention_id"] = mention_id

            # Send the holiday announcement
            log.info(f"Sending holiday end announcement for {holiday.name} to channel {channel_id}")
            success, error = await send_holiday_announcement(
                client=self.bot,
                channel_id=channel_id,
                config=config
            )

            if not success:
                log.error(f"Failed to send holiday end announcement: {error}")
                return False, f"Failed to send announcement: {error}"

            # Update the last announcement timestamp
            await self.update_last_announcement(guild_id, holiday.name, "after")
        except Exception:
            log.exception("Error in announce_holiday_end")
            return False, "An error occurred while sending the announcement"
        else:
            return True, None

    async def preview_holiday_announcement(
        self,
        holiday: Holiday,
        phase: str,
        user: discord.User,
        guild_id: int,
        custom_templates: dict[str, dict[str, str]] | None = None,
        days_until: int | None = None,
        mention_type: str | None = None,
        mention_id: int | None = None,
        *,
        to_channel: bool = False,
        ctx: Context | None = None
    ) -> tuple[bool, str]:
        """
        Send a preview of a holiday announcement to either a user's DMs or the current channel.

        Args:
            holiday: The holiday object
            phase: The phase of the holiday (before, during, after)
            user: The Discord user to send the preview to
            guild_id: The ID of the guild
            custom_templates: Optional custom templates to use
            days_until: Days until the holiday (for 'before' phase)
            mention_type: Optional mention type to override config
            mention_id: Optional mention ID to override config
            to_channel: Whether to send the preview to the current channel (for dryrun mode)
            ctx: The command context if to_channel is True

        Returns:
            Tuple of (success, message)

        """
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return False, f"Guild with ID {guild_id} not found"

            # Get announcement config if mention settings not provided
            if mention_type is None:
                announcement_config = await self.get_announcement_config(guild_id)
                mention_type = announcement_config.get("mention_type")

                if mention_type == "role":
                    mention_id = announcement_config.get("role_id")

            # Get the message template with placeholders replaced
            config = await self.get_holiday_message(
                holiday=holiday,
                phase=phase,
                guild_id=guild_id,
                custom_templates=custom_templates,
                days_until=days_until
            )

            # Set mention details for the preview
            config["mention_type"] = mention_type
            config["mention_id"] = mention_id

            # Check if we should send to the current channel instead of DMs
            if to_channel and ctx:
                # Create a copy of the config for preview
                preview_config = dict(config)

                # Add a preview header to the embed
                embed_params = preview_config.get("embed_params", {}).copy()
                original_title = embed_params.get("title", "")
                embed_params["title"] = f"PREVIEW: {original_title}"

                # Add footer note
                footer_text = embed_params.get("footer_text", "")
                embed_params["footer_text"] = f"{footer_text} | This is a preview" if footer_text else "This is a preview"

                preview_config["embed_params"] = embed_params

                # Create the embed
                embed = await create_embed_announcement(preview_config.get("embed_params", {}))
                content = None

                # Add mention preview (if applicable)
                if preview_config.get("mention_type"):
                    mention_info = ""
                    if preview_config["mention_type"] == "everyone":
                        mention_info = "@everyone would be mentioned"
                    elif preview_config["mention_type"] == "here":
                        mention_info = "@here would be mentioned"
                    elif preview_config["mention_type"] == "role" and preview_config.get("mention_id"):
                        role_id = preview_config["mention_id"]
                        role = ctx.guild.get_role(role_id)
                        if role:
                            mention_info = f"Role {role.name} would be mentioned"
                        else:
                            mention_info = f"Role with ID {role_id} would be mentioned"

                    if mention_info:
                        content = f"**PREVIEW:** {mention_info}"

                # Send to the current channel
                try:
                    await ctx.send(content=content, embed=embed)
                except Exception:
                    log.exception("Error sending announcement preview to channel")
                    return False, "Failed to send preview to channel"
                else:
                    return True, "Preview shown in channel."
            else:
                # Send the preview to the user's DMs
                log.info(f"Sending holiday announcement preview for {holiday.name} to user {user.name}")
                success, message = await preview_announcement(
                    user=user,
                    config=config,
                    announcement_type="holiday",
                    is_holiday=True
                )

                if not success:
                    log.error(f"Failed to send holiday announcement preview: {message}")
                    return False, f"Failed to send preview: {message}"

                return True, "Preview sent to your DMs! This is how the announcement will appear."
        except Exception:
            log.exception("Error in preview_holiday_announcement")
            return False, "An error occurred while sending the preview"

    async def should_send_announcement(
        self,
        holiday: Holiday,
        phase: str,
        last_announced_date: str | None = None
    ) -> tuple[bool, str]:
        """
        Determine if an announcement should be sent for a holiday phase.

        Args:
            holiday: The holiday object
            phase: The phase of the holiday (before, during, after)
            last_announced_date: ISO format date string of when this phase was last announced

        Returns:
            Tuple of (should_send, reason)

        """
        today = DateUtil.now()

        # If already announced this phase
        if last_announced_date:
            try:
                last_date = DateUtil.str_to_date(last_announced_date)
                if DateUtil.is_same_day(last_date, today):
                    return False, f"Already announced {phase} phase for {holiday.name} today"
            except ValueError:
                log.warning(f"Invalid last_announced_date format: {last_announced_date}")
                # Continue with the check if date format was invalid

        # Get holiday date for current year
        holiday_date = DateUtil.get_holiday_date(holiday.month, holiday.day)

        # Check based on phase
        if phase == "before":
            # Should be exactly 7 days before the holiday
            date_7_days_before = DateUtil.subtract_days(holiday_date, 7)
            if DateUtil.is_same_day(today, date_7_days_before):
                return True, f"Today is 7 days before {holiday.name}"
            return False, f"Today is not 7 days before {holiday.name}"

        if phase == "during":
            # Should be the day of the holiday
            if DateUtil.is_same_day(today, holiday_date):
                return True, f"Today is {holiday.name}"
            return False, f"Today is not {holiday.name}"

        if phase == "after":
            # Should be the day after the holiday
            date_after = DateUtil.add_days(holiday_date, 1)
            if DateUtil.is_same_day(today, date_after):
                return True, f"Today is the day after {holiday.name}"
            return False, f"Today is not the day after {holiday.name}"

        return False, f"Unknown phase: {phase}"

    async def update_last_announcement(self, guild_id: int, holiday_name: str, phase: str) -> bool:
        """
        Update the timestamp of the last sent announcement for a holiday and phase.

        Args:
            guild_id: The ID of the guild
            holiday_name: The name of the holiday
            phase: The phase of the holiday (before, during, after)

        Returns:
            True if successful, False otherwise

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild {guild_id} not found")
            return False

        # Validate phase
        if phase not in ("before", "during", "after"):
            log.warning(f"Invalid phase: {phase}. Must be 'before', 'during', or 'after'.")
            return False

        try:
            # Get current announcement history
            last_announcements = await self.config.guild(guild).announcement_config.get_raw(
                "last_announcements", default={}
            )

            # Initialize holiday dictionary if it doesn't exist
            if holiday_name not in last_announcements:
                last_announcements[holiday_name] = {}

            # Set the current date as ISO format string
            current_date = datetime.now(timezone.utc).isoformat()
            last_announcements[holiday_name][phase] = current_date

            # Save back to config
            await self.config.guild(guild).announcement_config.set_raw(
                "last_announcements", value=last_announcements
            )

            log.info(f"Updated last announcement for '{holiday_name}' ({phase}) to {current_date}")
        except Exception:
            log.exception("Error updating last announcement")
            return False
        else:
            return True

    async def get_last_announcement(self, guild_id: int, holiday_name: str, phase: str) -> str | None:
        """
        Get the date of the last announcement for a holiday phase.

        Parameters
        ----------
        guild_id : int
            The ID of the guild.
        holiday_name : str
            The name of the holiday.
        phase : str
            The phase of the holiday ('before', 'during', or 'after').

        Returns
        -------
        Optional[str]
            The date of the last announcement in ISO format, or None if no announcement was made.

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild {guild_id} not found")
            return None

        try:
            announcement_history = await self.config.guild(guild).announcement_config.get_raw(
                "last_announcements", default={}
            )

            # Early returns for missing data
            if holiday_name not in announcement_history:
                return None

            if phase not in announcement_history[holiday_name]:
                return None
        except Exception:
            log.exception("Error getting last announcement")
            return None
        else:
            return announcement_history[holiday_name][phase]

    async def clear_announcement_history(self, guild_id: int, holiday_name: str | None = None) -> bool:
        """
        Clear announcement history for a specific holiday or all holidays.

        Parameters
        ----------
        guild_id : int
            The ID of the guild to clear history for.
        holiday_name : Optional[str]
            The name of the holiday to clear history for, or None to clear all history.

        Returns
        -------
        bool
            True if cleared successfully, False otherwise.

        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild {guild_id} not found")
            return False

        try:
            await self.config.guild(guild).announcement_config.get_raw(
                "last_announcements", default={}
            )
            if holiday_name is None:
                # Clear all announcement history
                await self.config.guild(guild).announcement_config.set_raw(
                    "last_announcements", value={}
                )
                log.info(f"Cleared all announcement history for guild {guild_id}")
            else:
                # Clear history for specific holiday
                last_announcements = await self.config.guild(guild).announcement_config.get_raw(
                    "last_announcements", default={}
                )

                if holiday_name in last_announcements:
                    del last_announcements[holiday_name]
                    await self.config.guild(guild).announcement_config.set_raw(
                        "last_announcements", value=last_announcements
                    )
                    log.info(f"Cleared announcement history for '{holiday_name}' in guild {guild_id}")
                else:
                    log.warning(f"No announcement history found for holiday '{holiday_name}'")
                    return False
        except Exception:
            log.exception("Error clearing announcement history")
            return False
        else:
            return True
