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

from utilities.announcement_utils import (
    HOLIDAY_STYLES,
    create_embed_announcement,
    preview_announcement,
    send_holiday_announcement,
)
from utilities.date_utils import DateUtil

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
                data = json.load(f)
                # Debug the structure of the loaded JSON
                log.debug(f"Loaded holidays JSON structure: top-level keys: {list(data.keys())}")
                if "holidays" in data:
                    log.debug(f"Found 'holidays' key with {len(data['holidays'])} entries")
                    log.debug(f"Holiday names in JSON: {list(data['holidays'].keys())}")
                    return data["holidays"]  # Extract the holidays section
                else:
                    log.debug(f"No 'holidays' key found in JSON, using entire file as holiday data")
                    return data  # Use the entire file if no holidays key
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

    async def reload_data_async(self):
        """
        Reload holiday data asynchronously.

        This is a public method that allows reloading the holiday data
        without accessing private members directly.
        """
        self.holidays_data = self._load_holidays_data()
        log.info("Holiday data reloaded")

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
        # Debug log for Holiday object properties
        log.debug(f"get_holiday_message called for holiday: {holiday.name}, phase: {phase}")
        if hasattr(holiday, "to_dict"):
            log.debug(f"Holiday object data: {holiday.to_dict()}")
        else:
            log.debug(f"Holiday object attributes: name={holiday.name}, month={getattr(holiday, 'month', 'N/A')}, day={getattr(holiday, 'day', 'N/A')}, color={getattr(holiday, 'color', 'N/A')}, image={getattr(holiday, 'image', 'N/A')}")

        # Debug log for holidays_data structure
        log.debug(f"self.holidays_data contains {len(self.holidays_data.get('holidays', {}))} entries")
        if "holidays" in self.holidays_data:
            log.debug(f"Available holiday names in data: {list(self.holidays_data['holidays'].keys())}")
            holiday_data = self.holidays_data["holidays"]
        else:
            log.debug(f"Available holiday names in data: {list(self.holidays_data.keys())}")
            holiday_data = self.holidays_data

        log.debug(f"Holiday data structure: {list(holiday_data.keys())[:3]}")  # Log first few keys

        # Check if we have flavortext for this holiday in our JSON data
        holiday_name = holiday.name
        if holiday_name in holiday_data:
            log.debug(f"Found holiday '{holiday_name}' in holidays_data")
            holiday_info = holiday_data[holiday_name]
            log.debug(f"Holiday info keys: {list(holiday_info.keys())}")

            if "announcements" in holiday_info:
                log.debug(f"Found announcements for {holiday_name}: {list(holiday_info['announcements'].keys())}")

                holiday_announcements = holiday_info["announcements"]
                if phase in holiday_announcements:
                    log.debug(f"Found {phase} announcement for {holiday_name}: {holiday_announcements[phase]}")

                    # Build proper embed parameters from JSON data
                    log.debug(f"Building embed for holiday: {holiday_name}, phase: {phase}")
                    embed_params = {}

                    # Add title if available
                    if "title" in holiday_announcements[phase]:
                        title_text = holiday_announcements[phase]["title"]
                        log.debug(f"Raw title text: {title_text}")

                        # Replace placeholders in title
                        if "{holiday_name}" in title_text:
                            display_name = holiday_info.get("display_name", holiday_name)
                            log.debug(f"Replacing holiday_name in title with: {display_name}")
                            title_text = title_text.replace("{holiday_name}", display_name)

                        embed_params["title"] = title_text
                        log.debug(f"Final title text: {embed_params['title']}")
                    else:
                        log.warning(f"No title found for {holiday_name} {phase} announcement")

                    # Only add description if explicitly provided
                    if "description" in holiday_announcements[phase]:
                        description_text = holiday_announcements[phase]["description"]
                        if "{holiday_name}" in description_text:
                            display_name = holiday_info.get("display_name", holiday_name)
                            log.debug(f"Replacing holiday_name in description with: {display_name}")
                            description_text = description_text.replace("{holiday_name}", display_name)

                        embed_params["description"] = description_text
                        log.debug(f"Set explicit description: {embed_params['description']}")

                    # Add footer if available - properly format as dict
                    if "footer" in holiday_announcements[phase]:
                        footer_text = holiday_announcements[phase]["footer"]
                        log.debug(f"Raw footer text: {footer_text}")

                        # Replace placeholders
                        # Replace holiday name placeholder
                        if "{holiday_name}" in footer_text:
                            # Use a display name if available, otherwise use the holiday name
                            display_name = holiday_info.get("display_name", holiday_name)
                            log.debug(f"Using display name for footer: {display_name}")
                            footer_text = footer_text.replace("{holiday_name}", display_name)
                            log.debug(f"Footer text after holiday_name replacement: {footer_text}")

                        # Replace days until placeholder
                        if days_until is not None and "{days_until}" in footer_text:
                            log.debug(f"Replacing days_until in footer with: {days_until}")
                            footer_text = footer_text.replace("{days_until}", str(days_until))
                            log.debug(f"Footer text after days_until replacement: {footer_text}")

                        # Discord.py expects footer as a dict
                        embed_params["footer"] = {"text": footer_text}
                        log.debug(f"Final footer dict: {embed_params['footer']}")
                    else:
                        log.warning(f"No footer found for {holiday_name} {phase} announcement")

                    # Add color from holiday data
                    if "color" in holiday_info:
                        color_hex = holiday_info["color"]
                        log.debug(f"Raw color value from holiday data: {color_hex}")
                        try:
                            # Remove # if present and convert to integer
                            color_hex = color_hex.lstrip("#")
                            embed_params["color"] = int(color_hex, 16)
                            log.debug(f"Set color: {color_hex} -> {embed_params['color']}")
                        except ValueError:
                            log.warning(f"Invalid color format: {color_hex}")
                    else:
                        log.warning(f"No color found for {holiday_name}")

                    # Log final embed parameters
                    log.debug(f"Final embed_params structure: {embed_params}")

                    result = {
                        "holiday_name": holiday_name,
                        "phase": phase,
                        "embed_params": embed_params,
                        "mention_type": None,  # Will be set by the calling function
                        "mention_id": None,    # Will be set by the calling function
                    }
                    log.debug(f"Returning holiday message data: {result}")
                    return result
                else:
                    log.warning(f"Phase '{phase}' not found in announcements for holiday '{holiday_name}'")
            else:
                log.warning(f"No 'announcements' key found for holiday '{holiday_name}'")
        else:
            log.warning(f"Holiday '{holiday_name}' not found in holidays_data")

        # If no custom holiday data found, fall back to existing template logic
        log.debug("Falling back to default template logic")
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
        date_obj = DateUtil.get_holiday_date(holiday.month, holiday.day)
        holiday_date = DateUtil.get_presentable_date(date_obj)

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
                bot=self.bot,
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
                bot=self.bot,
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
                bot=self.bot,
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
        # Add debug logging to help diagnose issues with holiday object
        log.debug(
            f"preview_holiday_announcement called for phase {phase}, "
            f"holiday={holiday}, days_until={days_until}, to_channel={to_channel}, ctx={ctx is not None}"
        )

        # Log the type and structure of the holiday object to help with debugging
        if hasattr(holiday, "__class__"):
            log.debug(f"Holiday object is of type {type(holiday).__name__} with attributes: {dir(holiday)}")
            log.debug(f"Holiday key properties: name={holiday.name}, month={getattr(holiday, 'month', 'N/A')}, day={getattr(holiday, 'day', 'N/A')}")
        else:
            log.debug(f"Holiday object is of type {type(holiday).__name__} with values: {holiday}")

        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                log.warning(f"Guild with ID {guild_id} not found")
                return False, f"Guild with ID {guild_id} not found"

            log.debug(f"Found guild: {guild.name} (ID: {guild.id})")

            # Get announcement config if mention settings not provided
            if mention_type is None:
                announcement_config = await self.get_announcement_config(guild_id)
                mention_type = announcement_config.get("mention_type")
                log.debug(f"Retrieved mention_type from config: {mention_type}")

                if mention_type == "role":
                    mention_id = announcement_config.get("role_id")
                    log.debug(f"Retrieved mention_id from config: {mention_id}")

            # Get the message template with placeholders replaced
            log.debug(f"Getting holiday message for {holiday.name}, phase {phase}")
            config = await self.get_holiday_message(
                holiday=holiday,
                phase=phase,
                guild_id=guild_id,
                custom_templates=custom_templates,
                days_until=days_until
            )
            log.debug(f"Retrieved message config with keys: {list(config.keys()) if config else 'None'}")
            log.debug(f"Embed params keys: {list(config.get('embed_params', {}).keys()) if config and 'embed_params' in config else 'None'}")

            # Set mention details for the preview
            config["mention_type"] = mention_type
            config["mention_id"] = mention_id
            log.debug(f"Set mention_type={mention_type}, mention_id={mention_id}")

            # Check if we should send to the current channel instead of DMs
            if to_channel and ctx:
                log.debug(f"Sending preview to channel (ctx.channel: {ctx.channel.name if hasattr(ctx.channel, 'name') else ctx.channel.id})")
                # Create a copy of the config for preview
                preview_config = dict(config)
                log.debug(f"Created preview_config with keys: {list(preview_config.keys())}")

                # Add a preview header to the embed
                embed_params = preview_config.get("embed_params", {}).copy()
                original_title = embed_params.get("title", "")
                embed_params["title"] = original_title
                log.debug(f"Using title for preview: '{original_title}'")

                # Add footer note
                footer = embed_params.get("footer", {})
                footer_text = footer.get("text", "") if isinstance(footer, dict) else ""
                log.debug(f"Original footer: {footer}")

                new_footer_text = f"{footer_text} | This is a preview" if footer_text else "This is a preview"
                embed_params["footer"] = {"text": new_footer_text}
                log.debug(f"Modified footer for preview: {embed_params['footer']}")

                preview_config["embed_params"] = embed_params
                log.debug(f"Final embed_params for preview has keys: {list(embed_params.keys())}")

                # Create the embed
                log.debug("Creating embed from embed_params")
                embed = await create_embed_announcement(preview_config.get("embed_params", {}))
                log.debug(f"Created embed with title: '{embed.title if embed else 'No embed created'}'")
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
                        role = guild.get_role(role_id)
                        if role:
                            mention_info = f"{role.mention} would be mentioned"
                            log.debug(f"Found role for mention: {role.name} (ID: {role.id})")
                        else:
                            mention_info = f"Role with ID {role_id} would be mentioned (role not found)"
                            log.warning(f"Role with ID {role_id} not found for mention preview")

                    content = f"**[PREVIEW]** {mention_info}"
                    log.debug(f"Added mention preview: {content}")

                # Try to locate attachment for image if specified
                image_attachment = None
                if "image" in preview_config.get("embed_params", {}) and preview_config.get("image_path"):
                    image_path = preview_config["image_path"]
                    log.debug(f"Image path specified in config: {image_path}")

                    # Check if the file exists
                    image_file_path = Path(__file__).parent / image_path
                    if image_file_path.exists():
                        try:
                            log.debug(f"Found image file at: {image_file_path}")
                            image_attachment = discord.File(
                                image_file_path, 
                                filename=Path(image_path).name
                            )
                            log.debug(f"Created attachment from image file: {Path(image_path).name}")
                        except Exception as e:
                            log.error(f"Error creating image attachment: {e}")
                    else:
                        log.warning(f"Image file not found at: {image_file_path}")
                        # Try parent directory as well
                        parent_path = Path(__file__).parent.parent / image_path
                        if parent_path.exists():
                            try:
                                log.debug(f"Found image file in parent directory: {parent_path}")
                                image_attachment = discord.File(
                                    parent_path,
                                    filename=Path(image_path).name
                                )
                                log.debug(f"Created attachment from image file in parent directory")
                            except Exception as e:
                                log.error(f"Error creating image attachment from parent path: {e}")
                        else:
                            log.warning(f"Image file not found in parent directory either: {parent_path}")

                # Send the preview to the channel
                try:
                    if image_attachment:
                        log.debug("Sending message with embed and image attachment")
                        await ctx.send(content=content, embed=embed, file=image_attachment)
                    else:
                        log.debug("Sending message with embed only (no image attachment)")
                        await ctx.send(content=content, embed=embed)

                    return True, "Preview sent to channel successfully"
                except discord.HTTPException as e:
                    log.error(f"Discord HTTP error when sending preview to channel: {e}")
                    return False, f"Failed to send preview: {e}"
                except Exception as e:
                    log.exception("Error sending preview to channel")
                    return False, f"An error occurred: {e}"
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

        Notes:
            For the "before" phase, announcements can be sent anytime between 7 days
            before the holiday and the day before the holiday, as long as no "before"
            announcement has been sent for this holiday in the current year.

            For "during" and "after" phases, announcements are only sent on the exact day.

        """
        # Get today's date - DateUtil.now() returns a date object
        today = DateUtil.now()
        # No need to call .date() since today is already a date object
        today_date = today

        # If already announced this phase
        if last_announced_date:
            try:
                # Try parsing the date more flexibly
                try:
                    # First try datetime.fromisoformat for modern Python versions
                    last_date = datetime.fromisoformat(last_announced_date)
                except (ValueError, AttributeError):
                    # Fall back to DateUtil for older Python or different formats
                    last_date = DateUtil.str_to_date(last_announced_date)

                last_date_date = last_date.date() if hasattr(last_date, "date") else last_date

                # For the "before" phase, check if we've already announced it this year
                if phase == "before":
                    if last_date_date.year == today_date.year:
                        log.info(f"Already announced 'before' phase for {holiday.name} this year")
                        return False, f"Already announced 'before' phase for {holiday.name} this year"
                # For other phases, just check if we've announced today
                elif DateUtil.is_same_day(last_date_date, today_date):
                    log.info(f"Already announced {phase} phase for {holiday.name} today")
                    return False, f"Already announced {phase} phase for {holiday.name} today"
            except ValueError as e:
                log.warning(f"Invalid last_announced_date format: {last_announced_date} - {str(e)}")
                # Continue with the check if date format was invalid
            except Exception as e:
                log.warning(f"Error parsing date {last_announced_date}: {str(e)}")
                # Continue with the check if there was any other error

        # Get holiday date for current year
        holiday_date = DateUtil.get_holiday_date(holiday.month, holiday.day)
        log.debug(f"Holiday date for {holiday.name}: {holiday_date}, Today: {today_date}")

        # Check based on phase
        if phase == "before":
            # Get date for 7 days before the holiday
            date_7_days_before = DateUtil.subtract_days(holiday_date, 7)

            # More flexible window: any time between 7 days before and the day before the holiday
            day_before_holiday = DateUtil.subtract_days(holiday_date, 1)

            # Check if today is between the 7-day mark and the day before the holiday (inclusive)
            if (today_date >= date_7_days_before) and (today_date <= day_before_holiday):
                log.info(f"Today is within the announcement window for {holiday.name}")
                return True, f"Today is within the announcement window for {holiday.name}"

            if today_date < date_7_days_before:
                log.debug(f"Too early to announce {holiday.name}")
                return False, f"Too early to announce {holiday.name}"
            log.debug(f"Too late to announce {holiday.name}")
            return False, f"Too late to announce {holiday.name}"

        if phase == "during":
            # Should be the day of the holiday
            if DateUtil.is_same_day(today_date, holiday_date):
                log.info(f"Today is {holiday.name}")
                return True, f"Today is {holiday.name}"
            log.debug(f"Today is not {holiday.name}")
            return False, f"Today is not {holiday.name}"

        if phase == "after":
            # Should be the day after the holiday
            date_after = DateUtil.add_days(holiday_date, 1)
            if DateUtil.is_same_day(today_date, date_after):
                log.info(f"Today is the day after {holiday.name}")
                return True, f"Today is the day after {holiday.name}"
            log.debug(f"Today is not the day after {holiday.name}")
            return False, f"Today is not the day after {holiday.name}"

        log.warning(f"Unknown phase: {phase}")
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

    async def trigger_announcement(
        self,
        holiday: Holiday,
        phase: str,
        guild_id: int,
        *,
        force: bool = False,
        channel_id: int | None = None,
        mention_type: str | None = None,
        mention_id: int | None = None,
        preview_only: bool = False,
        user_to_preview: discord.User | None = None
    ) -> tuple[bool, str, str | None]:
        """
        Manually trigger an announcement for a specific holiday and phase.

        This method provides a clean API for the command layer to trigger announcements
        while maintaining separation of business logic.

        Args:
            holiday: The holiday object
            phase: The phase of the holiday (before, during, after)
            guild_id: The ID of the guild
            force: Whether to bypass date eligibility checks
            channel_id: Optional channel ID to override config
            mention_type: Optional mention type to override config
            mention_id: Optional mention ID to override config
            preview_only: Whether to only generate a preview without sending
            user_to_preview: User to send the preview to (if preview_only is True)

        Returns:
            Tuple containing (success, message, status_reason)
            - success: Whether the operation was successful
            - message: A user-friendly message about the result
            - status_reason: Additional context about eligibility checks

        """
        log.debug(f"trigger_announcement called for holiday: {holiday.name}, phase: {phase}, guild_id: {guild_id}")
        log.debug(f"Parameters: force={force}, channel_id={channel_id}, mention_type={mention_type}, preview_only={preview_only}")

        if hasattr(holiday, "to_dict"):
            log.debug(f"Holiday object data: {holiday.to_dict()}")
        else:
            log.debug(f"Holiday attributes: name={holiday.name}, month={getattr(holiday, 'month', 'N/A')}, day={getattr(holiday, 'day', 'N/A')}")

        try:
            # Get last announcement date
            last_announced_date = await self.get_last_announcement(guild_id, holiday.name, phase)
            log.debug(f"Last announced date for {holiday.name} ({phase}): {last_announced_date}")

            # Check if announcement should be sent based on date eligibility
            should_send, reason = await self.should_send_announcement(
                holiday=holiday,
                phase=phase,
                last_announced_date=last_announced_date
            )

            # Handle force flag
            if not should_send and force:
                status_reason = f"Date check failed: {reason}. Bypassed with force flag."
                log.info(f"Force sending announcement for {holiday.name} ({phase}): {status_reason}")
                should_send = True
            else:
                status_reason = reason

            # Return early if shouldn't send and not forcing
            if not should_send:
                log.info(f"Announcement not eligible to be sent: {reason}")
                return False, f"Announcement not eligible to be sent: {reason}", status_reason

            if preview_only and user_to_preview:
                # Generate preview for user
                success, preview_msg = await self.preview_holiday_announcement(
                    holiday=holiday,
                    phase=phase,
                    user=user_to_preview,
                    guild_id=guild_id,
                    days_until=7 if phase == "before" else None,
                    mention_type=mention_type,
                    mention_id=mention_id
                )

                if not success:
                    log.error(f"Failed to generate preview: {preview_msg}")
                    return False, f"Failed to generate preview: {preview_msg}", status_reason
                return True, f"Preview generated successfully: {preview_msg}", status_reason

            # Determine which announcement method to call based on phase
            announcement_method = None
            if phase == "before":
                announcement_method = self.announce_upcoming_holiday
            elif phase == "during":
                announcement_method = self.announce_holiday_start
            elif phase == "after":
                announcement_method = self.announce_holiday_end
            else:
                log.error(f"Invalid phase: {phase}")
                return False, f"Invalid phase: {phase}", f"Phase must be 'before', 'during', or 'after'"

            # Call the appropriate announcement method
            log.info(f"Sending {phase} announcement for {holiday.name} in guild {guild_id}")
            success, error = await announcement_method(
                holiday=holiday,
                guild_id=guild_id,
                channel_id=channel_id,
                mention_type=mention_type,
                mention_id=mention_id
            )

            # Only update the last announcement timestamp if successful
            if success:
                log.info(f"Successfully sent {phase} announcement for {holiday.name}")
                await self.update_last_announcement(guild_id, holiday.name, phase)
                return True, f"Announcement for {holiday.name} ({phase} phase) sent successfully!", status_reason
            else:
                log.error(f"Failed to send {phase} announcement for {holiday.name}: {error}")
                return False, f"Failed to send announcement: {error}", status_reason

        except Exception as e:
            log.exception(f"Error in trigger_announcement for {holiday.name} ({phase})")
            return False, f"An error occurred: {str(e)}", "Exception occurred"

    async def debug_holiday_status(self, guild_id: int, holiday_name: str):
        """
        Log detailed diagnostic information about a holiday's status to help with debugging.

        Args:
            guild_id: The ID of the guild
            holiday_name: The name of the holiday to debug

        """
        try:
            # Get the holiday data
            holiday = await self.holiday_repository.get_holiday(holiday_name)
            if not holiday:
                log.error(f"Debug failed: Holiday '{holiday_name}' not found")
                return

            # Use DateUtil.now() which returns a date object already
            today = DateUtil.now()
            current_date = today  # No need to call .date()

            # Log holiday details
            log.info(f"======= HOLIDAY DEBUG INFO: {holiday.name} =======")
            log.info(f"Date Range: {holiday.date_start} to {holiday.date_end}")

            # Parse dates
            try:
                date_start = DateUtil.str_to_date(holiday.date_start, year=today.year)
                date_end = DateUtil.str_to_date(holiday.date_end, year=today.year)
                log.info(f"Parsed Dates: {date_start} to {date_end}")
                log.info(f"Current Date: {current_date}")

                days_until = (date_start - today).days + 1
                log.info(f"Days until start: {days_until}")

                if date_start <= current_date <= date_end:
                    log.info("Status: ACTIVE (holiday is currently running)")
                elif current_date < date_start:
                    log.info("Status: UPCOMING (holiday has not started yet)")
                else:
                    log.info("Status: OVER (holiday has ended)")
            except Exception as e:
                log.error(f"Error parsing dates: {e}")

            # Check last announcement times
            for phase in ["before", "during", "after"]:
                last_announced = await self.get_last_announcement(guild_id, holiday.name, phase)
                if last_announced:
                    log.info(f"Last '{phase}' announcement: {last_announced}")
                else:
                    log.info(f"Last '{phase}' announcement: Never announced")

            # Check announcement eligibility
            for phase in ["before", "during", "after"]:
                should_send, reason = await self.should_send_announcement(
                    holiday=holiday,
                    phase=phase,
                    last_announced_date=await self.get_last_announcement(guild_id, holiday.name, phase)
                )
                log.info(f"'{phase}' announcement eligibility: {should_send} - {reason}")

            # Get holiday message
            try:
                message_data = await self.get_holiday_message(
                    holiday=holiday,
                    phase="before",
                    guild_id=guild_id,
                    days_until=max(1, days_until)
                )
                log.info(f"Message data keys: {list(message_data.keys())}")
                embed_data = message_data.get("embed", {})
                log.info(f"Embed data keys: {list(embed_data.keys() if embed_data else [])}")
            except Exception as e:
                log.error(f"Error generating message data: {e}")

            log.info("========== END HOLIDAY DEBUG INFO ==========")
        except Exception:
            log.exception("Error in debug_holiday_status")
