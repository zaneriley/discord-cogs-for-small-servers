import datetime
import logging
from utils.date_util import DateUtil

# Set up logger
log = logging.getLogger(__name__)

class HolidayService:
    async def check_holidays(self) -> int:
        """
        Check for upcoming or active holidays and take appropriate actions.

        This method serves as the main coordinator for holiday-related events:
        - Announces upcoming holidays (before phase)
        - Activates holidays when they start (during phase)
        - Deactivates holidays when they end (after phase)

        Returns:
            int: Number of holidays processed

        """
        log.debug("Checking holidays...")
        all_guilds = await self.bot.api_client.get("guilds")
        if not all_guilds:
            log.warning("Unable to fetch guilds from API. Skipping holiday check.")
            return 0

        bot_guild_ids = [guild.id for guild in self.bot.guilds]
        holidays = await self.holiday_repository.get_all_holidays()
        today = DateUtil.now()

        # Count how many holidays were processed
        processed = 0

        for guild_id in bot_guild_ids:
            log.debug(f"Checking holidays for guild {guild_id}")

            guild_config = await self.get_guild_config(guild_id)
            if not guild_config or not guild_config.get("enabled", False):
                log.debug(f"Seasonal roles not enabled for guild {guild_id}")
                continue

            for holiday in holidays:
                log.debug(f"Checking holiday: {holiday.name}")

                # Skip holidays that are disabled for this guild
                if holiday.name in guild_config.get("disabled_holidays", []):
                    log.debug(f"Holiday {holiday.name} is disabled for guild {guild_id}")
                    continue

                try:
                    date_start = DateUtil.str_to_date(holiday.date_start, year=today.year)
                    date_end = DateUtil.str_to_date(holiday.date_end, year=today.year)
                except Exception as e:
                    log.error(f"Failed to parse date for holiday {holiday.name}: {e}")
                    continue

                days_until = (date_start - today).days + 1
                current_date = today

                success_flag = False  # Track if any announcement was successful
                status_reason = None  # Collect reason if announcement checks fail

                # Check for before announcement (upcoming holidays)
                if days_until > 0 and days_until <= guild_config.get("announce_before_days", 7):
                    log.info(f"Holiday {holiday.name} is coming up in {days_until} days.")
                    success, message, reason = await self.holiday_announcer.trigger_announcement(
                        holiday=holiday,
                        phase="before",
                        guild_id=guild_id
                    )
                    log.info(f"Before announcement for {holiday.name}: {message}")

                    if success:
                        success_flag = True
                        processed += 1
                    else:
                        status_reason = reason

                # Check for during announcement and role assignment
                if date_start <= current_date <= date_end:
                    if current_date == date_start:
                        # Holiday is starting today
                        log.info(f"Holiday {holiday.name} is starting today!")

                        # Send the 'during' announcement
                        success, message, reason = await self.holiday_announcer.trigger_announcement(
                            holiday=holiday,
                            phase="during",
                            guild_id=guild_id
                        )
                        log.info(f"During announcement for {holiday.name}: {message}")

                        if success:
                            success_flag = True
                            processed += 1
                        else:
                            status_reason = reason

                    # Assign roles (even if we've already activated it, we still assign roles daily)
                    log.debug(f"Holiday {holiday.name} is active. Assigning roles.")

                    # Only assign roles if the announcement was successful or we didn't need to announce
                    if success_flag or current_date > date_start:
                        try:
                            assigned = await self.role_manager.assign_holiday_roles(guild_id, holiday)
                            log.info(f"Assigned {assigned} roles for holiday {holiday.name}")
                        except Exception as e:
                            log.error(f"Failed to assign roles for {holiday.name}: {e}")
                    else:
                        log.warning(f"Skipping role assignment for {holiday.name}: {status_reason}")

                # Check for after announcement and role removal
                elif current_date == date_end + datetime.timedelta(days=1):
                    # Holiday ended yesterday
                    log.info(f"Holiday {holiday.name} ended yesterday.")

                    # Send the 'after' announcement
                    success, message, reason = await self.holiday_announcer.trigger_announcement(
                        holiday=holiday,
                        phase="after",
                        guild_id=guild_id
                    )
                    log.info(f"After announcement for {holiday.name}: {message}")

                    if success:
                        success_flag = True
                        processed += 1
                    else:
                        status_reason = reason

                    # Remove roles only if the announcement was successful
                    if success_flag:
                        try:
                            removed = await self.role_manager.remove_holiday_roles(guild_id, holiday)
                            log.info(f"Removed {removed} roles for holiday {holiday.name}")
                        except Exception as e:
                            log.error(f"Failed to remove roles for {holiday.name}: {e}")
                    else:
                        log.warning(f"Skipping role removal for {holiday.name}: {status_reason}")

                # Special case: If the holiday is over and roles are still assigned
                elif current_date > date_end:
                    # Check if roles from this holiday are still assigned
                    try:
                        roles_exist = await self.role_manager.holiday_roles_exist(guild_id, holiday)
                        if roles_exist:
                            log.warning(f"Holiday {holiday.name} is over but roles still exist. Removing them.")
                            removed = await self.role_manager.remove_holiday_roles(guild_id, holiday)
                            log.info(f"Removed {removed} leftover roles for holiday {holiday.name}")
                    except Exception as e:
                        log.error(f"Failed to check/remove leftover roles for {holiday.name}: {e}")

        log.info(f"Holiday check completed. Processed {processed} holiday events.")
        return processed 