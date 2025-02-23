import logging

import discord

from utilities.date_utils import DateUtil

from .role_management import RoleManager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HolidayService:
    def __init__(self, config):
        self.config = config
        self.role_manager = RoleManager(self.config)

    async def get_holidays(self, guild):
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
            return await self.config.guild(guild).holidays()
        except Exception as e:
            logger.exception(f"Failed to retrieve holidays for guild {guild.name}: {e!s}")
            return {}

    async def add_holiday(self, guild, name, date, color, image=None, banner_url=None):
        holidays = await self.config.guild(guild).holidays()
        if holidays.get(name):
            return False, f"Holiday {name} already exists!"

        holidays[name] = {"date": date, "color": color}
        if image:
            holidays[name]["image"] = image
        if banner_url:
            holidays[name]["banner"] = banner_url

        await self.config.guild(guild).holidays.set(holidays)
        return True, f"Holiday {name} added successfully!"

    async def remove_holiday(self, guild, name):
        holidays = await self.config.guild(guild).holidays()
        if not holidays.get(name):
            return False, f"Holiday {name} does not exist!"

        del holidays[name]
        await self.config.guild(guild).holidays.set(holidays)
        return True, f"Holiday {name} has been removed successfully!"

    async def edit_holiday(self, guild, name, new_date, new_color, new_image=None, new_banner_url=None):
        holidays = await self.config.guild(guild).holidays()
        if not holidays.get(name):
            return False, f"Holiday {name} does not exist!"

        # Update the holiday details
        holidays[name]["date"] = new_date
        holidays[name]["color"] = new_color
        if new_image:
            holidays[name]["image"] = new_image
        if new_banner_url:
            holidays[name]["banner"] = new_banner_url

        await self.config.guild(guild).holidays.set(holidays)
        return True, f"Holiday {name} has been updated successfully!"

    async def get_sorted_holidays(self, guild):
        holidays = await self.config.guild(guild).holidays()
        if not holidays:
            return None, "No holidays have been configured."

        upcoming_holiday, days_until = self.find_upcoming_holiday(holidays)
        future_holidays = {name: days for name, days in days_until.items() if days > 0}
        past_holidays = {name: days for name, days in days_until.items() if days <= 0}

        sorted_future_holidays = sorted(future_holidays.items(), key=lambda x: x[1])
        sorted_past_holidays = sorted(past_holidays.items(), key=lambda x: x[1], reverse=False)

        sorted_holidays = sorted_future_holidays + sorted_past_holidays
        return sorted_holidays, upcoming_holiday, days_until

    def find_upcoming_holiday(self, holidays):
        # Logic to find the upcoming holiday
        current_date = DateUtil.now()
        upcoming_holiday = None
        min_days_diff = float("inf")
        days_until = {}

        for name, details in holidays.items():
            holiday_date_str = f"{current_date.year}-{details['date']}"
            holiday_date = DateUtil.str_to_date(holiday_date_str, "%Y-%m-%d")

            days_diff = (holiday_date - current_date).days
            days_until[name] = days_diff

            if days_diff > 0 and days_diff < min_days_diff:
                min_days_diff = days_diff
                upcoming_holiday = name

        return upcoming_holiday, days_until

    async def validate_holiday_exists(self, holidays, holiday_name):
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
        normalized_holidays = {name.lower(): details for name, details in holidays.items()}
        if holiday_name.lower() in normalized_holidays:
            logger.debug(f"Holiday '{holiday_name}' found.")
            return True, None
        logger.warning(f"Holiday '{holiday_name}' does not exist.")
        return False, f"Holiday '{holiday_name}' does not exist!"

    async def remove_all_except_current_holiday_role(self, guild: discord.Guild, current_holiday_name: str):
        """
        Removes all holiday roles from members except for the role associated with the specified current holiday.

        Args:
        ----
            guild (discord.Guild): The guild from which to remove the roles.
            current_holiday_name (str): The name of the holiday whose role should not be removed.

        """
        if not guild or not current_holiday_name:
            logger.error("Invalid guild or holiday name provided.")
            return False, "Invalid input parameters."

        logger.info(
            f"Starting to remove all holiday roles except for '{current_holiday_name}' in guild '{guild.name}'."
        )

        try:
            holidays = await self.config.guild(guild).holidays()
            roles_removed = []
            for holiday_name, details in holidays.items():
                if holiday_name.lower() != current_holiday_name.lower():
                    formatted_role_name = f"{holiday_name} {details['date']}"
                    role = discord.utils.get(guild.roles, name=formatted_role_name)
                    if role:
                        await self.role_manager.delete_role_from_guild(guild, role)
                        roles_removed.append(role.name)
                        logger.debug(f"Removed role '{role.name}' associated with holiday '{holiday_name}'.")
                    else:
                        logger.warning(f"Role '{formatted_role_name}' not found.")

            if not roles_removed:
                logger.info("No roles were removed.")
                return True, "No roles needed to be removed."

            logger.info(f"All holiday roles except for '{current_holiday_name}' have been removed.")
            return True, f"Removed roles: {', '.join(roles_removed)}"
        except Exception as e:
            logger.exception(f"Failed to remove holiday roles due to an error: {e!s}")
            return False, f"An error occurred: {e!s}"
        # Final return statement to handle any missed cases
        logger.debug("Exiting remove_all_except_current_holiday_role method without specific action.")
        return True, "Completed without explicit action."

    async def apply_holiday_role(self, guild, holiday_name, dry_run):
        """
        Apply the specified holiday role to all members in the guild.

        Args:
        ----
            guild (discord.Guild): The guild where the role should be applied.
            holiday_name (str): The name of the holiday role to apply.
            dry_run (bool): Whether to simulate the action without making changes.

        Returns:
        -------
            tuple: (bool, str) indicating success and a message describing the action taken.

        """
        logger.debug(f"Attempting to apply holiday role for '{holiday_name}'. Dry run: {dry_run}")

        if dry_run:
            return True, f"[Dry Run] Would have applied holiday role '{holiday_name}'."

        try:
            async with self.config.guild(guild).holidays() as holidays:
                normalized_holidays = {name.lower(): details for name, details in holidays.items()}
                normalized_holiday_name = holiday_name.lower()

                if normalized_holiday_name not in normalized_holidays:
                    logger.error(f"Holiday '{holiday_name}' not found when applying role.")
                    return False, f"Holiday '{holiday_name}' does not exist."

                # Retrieve the original name with correct casing
                original_name = next(
                    (name for name in holidays if name.lower() == normalized_holiday_name), holiday_name
                )
                holiday_details = normalized_holidays[normalized_holiday_name]
                logger.debug(f"Holiday details retrieved: {holiday_details}")

                role = await self.role_manager.create_or_update_role(
                    guild,
                    original_name,
                    holiday_details["color"],
                    holiday_details["date"],
                    holiday_details.get("image"),
                )
            if role:
                await self.role_manager.assign_role_to_all_members(guild, role)
                await self.role_manager.move_role_to_top_priority(guild, role)
                return True, f"Holiday role '{original_name}' applied to all members."
            return False, "Failed to apply the holiday role."
        except discord.HTTPException as e:
            return False, f"Failed to apply holiday role due to an HTTP error: {e!s}"
