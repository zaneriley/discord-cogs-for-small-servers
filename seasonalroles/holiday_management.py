from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from utilities.date_utils import DateUtil

from .holiday.holiday_calculator import find_upcoming_holiday as calc_upcoming_holiday
from .holiday.holiday_calculator import get_sorted_holidays as calc_sorted_holidays
from .holiday.holiday_validator import (
    find_holiday,
    validate_color,
    validate_date_format,
    validate_holiday_name,
)
from .role_management import RoleManager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass
class HolidayData:

    """Class for storing holiday data."""

    name: str
    date: str
    color: str
    image: str | None = None
    banner_url: str | None = None


class HolidayService:
    def __init__(self, config, repository=None):
        self.config = config
        if repository is None:
            from .holiday.holiday_repository import ConfigHolidayRepository

            self.repository = ConfigHolidayRepository(config)
        else:
            self.repository = repository
        self.role_manager = RoleManager(self.config)

    async def get_holidays(self, guild) -> dict:
        """
        Retrieve the holiday configurations for the specified guild.

        Args:
        ----
            guild (discord.Guild): The guild from which to retrieve holiday configurations.

        Returns:
        -------
            dict: A dictionary containing the holiday configurations.

        """
        try:
            return await self.repository.get_holidays(guild)
        except Exception:
            logger.exception(f"Failed to retrieve holidays for guild {guild.name}")
            return {}

    async def add_holiday(
        self, guild, holiday_data: HolidayData
    ) -> tuple[bool, str]:
        """Add a new holiday configuration."""
        # Use business logic validation functions
        if not validate_holiday_name(holiday_data.name):
            return False, f"Invalid holiday name: {holiday_data.name}."

        # Validate date format
        if not validate_date_format(holiday_data.date):
            return False, f"Invalid date format: {holiday_data.date}. Expected MM-DD format."

        # Validate color format
        if not validate_color(holiday_data.color):
            return False, f"Invalid color format: {holiday_data.color}. Expected #RRGGBB format."

        holiday_dict = {"date": holiday_data.date, "color": holiday_data.color}
        if holiday_data.image:
            holiday_dict["image"] = holiday_data.image
        if holiday_data.banner_url:
            holiday_dict["banner"] = holiday_data.banner_url

        success = await self.repository.add_holiday(guild, holiday_data.name, holiday_dict)
        if success:
            return True, f"Holiday {holiday_data.name} added successfully!"
        return False, f"Holiday {holiday_data.name} already exists!"

    async def remove_holiday(self, guild, name) -> tuple[bool, str]:
        """Remove a holiday configuration."""
        success = await self.repository.remove_holiday(guild, name)
        if success:
            return True, f"Holiday {name} has been removed successfully!"
        return False, f"Holiday {name} does not exist!"

    async def edit_holiday(
        self, guild, holiday_data: HolidayData
    ) -> tuple[bool, str]:
        """Edit an existing holiday configuration."""
        # Use business logic validation functions
        if not validate_holiday_name(holiday_data.name):
            return False, f"Invalid holiday name: {holiday_data.name}."

        # Validate date format
        if not validate_date_format(holiday_data.date):
            return False, f"Invalid date format: {holiday_data.date}. Expected MM-DD format."

        # Validate color format
        if not validate_color(holiday_data.color):
            return False, f"Invalid color format: {holiday_data.color}. Expected #RRGGBB format."

        holiday_dict = {"date": holiday_data.date, "color": holiday_data.color}
        if holiday_data.image:
            holiday_dict["image"] = holiday_data.image
        if holiday_data.banner_url:
            holiday_dict["banner"] = holiday_data.banner_url

        success = await self.repository.update_holiday(guild, holiday_data.name, holiday_dict)
        if success:
            return True, f"Holiday {holiday_data.name} has been updated successfully!"
        return False, f"Holiday {holiday_data.name} does not exist!"

    async def get_sorted_holidays(self, guild) -> tuple[list | None, str | None, dict]:
        """Get holidays sorted by their days until occurrence."""
        holidays = await self.repository.get_holidays(guild)
        if not holidays:
            return None, None, {}

        current_date = DateUtil.now().date()

        # Use the calculator function instead of reimplementing the logic
        upcoming_holiday, days_until = calc_upcoming_holiday(holidays, current_date)

        # Use the calculator function to get sorted holidays
        sorted_holidays = calc_sorted_holidays(holidays, current_date)

        return sorted_holidays, upcoming_holiday, days_until

    async def validate_holiday_exists(
        self, holidays, holiday_name
    ) -> tuple[bool, str | None]:
        """
        Check if the holiday exists in the given dictionary of holidays.

        Args:
        ----
            holidays (dict): A dictionary of holidays.
            holiday_name (str): The name of the holiday to check.

        Returns:
        -------
            tuple: (bool, str) indicating if the holiday exists and an optional message.

        """
        if not validate_holiday_name(holiday_name):
            logger.warning("Empty or invalid holiday name provided.")
            return False, "Holiday name cannot be empty or invalid!"

        # Use the find_holiday business logic function instead of reimplementing
        original_name, details = find_holiday(holidays, holiday_name)

        if original_name is not None:
            logger.debug(f"Holiday '{holiday_name}' found as '{original_name}'.")
            return True, None

        logger.warning(f"Holiday '{holiday_name}' does not exist.")
        return False, f"Holiday '{holiday_name}' does not exist!"

    # These validation methods should be removed since we now use the business logic
    # We'll keep the _normalize_name method since it's used by other methods
    def _normalize_name(self, name):
        """Normalize a holiday name for comparison."""
        if not name:
            return ""
        # Convert to lowercase and normalize whitespace
        return " ".join(name.lower().split())

    async def remove_all_except_current_holiday_role(self, guild, current_holiday_name):
        """
        Removes all holiday roles from members except the current holiday role.
        """
        try:
            holidays = await self.repository.get_holidays(guild)
            roles_removed = []

            for holiday_name, details in holidays.items():
                original_name, _ = find_holiday(holidays, holiday_name)

                if (
                    original_name
                    and original_name.lower() != current_holiday_name.lower()
                ):
                    formatted_role_name = f"{original_name} {details['date']}"
                    for role in guild.roles:
                        if role.name.lower() == formatted_role_name.lower():
                            await self.role_manager.remove_role_from_all_members(
                                guild, role
                            )
                            roles_removed.append(role.name)
                            logger.debug(
                                f"Removed role {role.name} from all members in {guild.name}"
                            )
                            break
            return True, f"Removed roles: {', '.join(roles_removed)}"
        except Exception:
            logger.exception("Failed to remove holiday roles due to an error")
            return False, "An error occurred while removing holiday roles."

    async def apply_holiday_role(self, guild, holiday_name):
        """
        Applies the role for the specified holiday to all members who are opted in.
        """
        try:
            holidays = await self.repository.get_holidays(guild)

            # Use business logic to find the holiday
            original_name, holiday_details = find_holiday(holidays, holiday_name)

            if not original_name or not holiday_details:
                logger.error(f"Holiday '{holiday_name}' not found when applying role.")
                return False, f"Holiday '{holiday_name}' does not exist."

            logger.debug(f"Holiday details retrieved: {holiday_details}")
            role = await self.role_manager.create_or_update_role(
                guild,
                original_name,
                holiday_details["color"],
                holiday_details["date"],
                holiday_details.get("image"),
            )

            if not role:
                return False, "Failed to apply the holiday role."

            # Move and assign role only if we successfully created or updated it
            await self.role_manager.move_role_to_top_priority(guild, role)
            await self.role_manager.assign_role_to_all_members(guild, role)
            return True, f"Holiday role '{original_name}' applied to all members."  # noqa: TRY300

        except discord.HTTPException as e:
            return False, f"Failed to apply holiday role due to an HTTP error: {e!s}"
        except (ValueError, TypeError, AttributeError, discord.DiscordException) as e:
            return False, f"Failed to apply holiday role due to an error: {e!s}"
