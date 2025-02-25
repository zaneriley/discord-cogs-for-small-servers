from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks

try:
    from redbot.core import Config, commands
except ModuleNotFoundError:
    Config = None

    def dummy_decorator_factory(*dargs, **dkwargs):
        def decorator(func):
            return DummyCommand(func)

        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return DummyCommand(dargs[0])
        return decorator

    def dummy_guild_only(*args, **dkwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]) and not dkwargs:
            return args[0]
        return decorator

    def dummy_has_permissions(*args, **dkwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]) and not dkwargs:
            return args[0]
        return decorator

    class DummyCommand:
        def __init__(self, func):
            self.func = func
            self.command = dummy_decorator_factory
            self.group = dummy_decorator_factory

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    class DummyCog:
        listener = staticmethod(dummy_decorator_factory)

    class DummyCommands:
        Cog = DummyCog
        command = dummy_decorator_factory
        group = dummy_decorator_factory
        listener = dummy_decorator_factory
        guild_only = dummy_guild_only
        has_permissions = dummy_has_permissions

    commands = DummyCommands()

from utilities.discord_utils import fetch_and_save_guild_banner
from utilities.image_utils import get_image_handler

from .holiday.holiday_calculator import (
    find_upcoming_holiday,
    get_sorted_holidays,
)
from .holiday.holiday_validator import (
    find_holiday,
    validate_color,
    validate_date_format,
    validate_holiday_name,
)
from .holiday_management import HolidayData, HolidayService
from .role_management import RoleManager

if TYPE_CHECKING:
    from redbot.core.bot import Red

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))
# Use Path for file path operations
image_path = Path("assets/your-image.png").resolve()
logger.debug(f"Absolute image path: {image_path}")

# Constants for magic numbers
DAYS_BEFORE_HOLIDAY = 7
PREMIUM_TIER_REQUIRED = 2

# Define a simple structure for holiday context
class HolidayContext:

    """Container for holiday processing context."""

    def __init__(self, name: str, details: dict, sorted_holidays: list, days_until: int):
        self.name = name
        self.details = details
        self.sorted_holidays = sorted_holidays
        self.days_until = days_until

# TODO: Make sure banner saving adds the date it was saved
# Make sure we update the "last updated date" in banner management
# The goal is the bot to handle kid's day on 5-5
class SeasonalRoles(commands.Cog):
    def __init__(self, bot: Red) -> None:
        """
        Initialize the RPG Cog.

        Args:
        ----
            bot (commands.Bot): The Red bot instance.

        """
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=IDENTIFIER, force_registration=True
        )
        self.config.register_guild()
        default_guild = {
            "notification_channel": None,
            "holidays": {
                "New Year's Celebration": {
                    "date": "01-01",
                    "color": "#D3B44B",
                    "image": "assets/new-years-01.png",
                },
                "Spring Blossom Festival": {
                    "date": "03-20",
                    "color": "#906D8D",
                    "image": "assets/spring-blossom-01.png",
                },
                "Kids Day": {
                    "date": "05-05",
                    "color": "#68855A",
                    "image": "assets/kids-day-01.png",
                    "banner": "assets/kids-day-banner-01.png",
                },
                "Midsummer Festival": {"date": "06-21", "color": "#4A6E8A"},
                "Star Festival": {"date": "07-07", "color": "#D4A13D"},
                "Friendship Day": {
                    "date": "08-02",
                    "color": "#8A6E5C",
                    "image": "assets/friendship-01.png",
                },
                "Harvest Festival": {"date": "09-22", "color": "#D37C40"},
                "Memories Festival": {"date": "10-15", "color": "#68855A"},
                "Spooky Festival": {
                    "date": "10-31",
                    "color": "#A8574E",
                    "image": "assets/spooky-01.png",
                },
                "Winter Festival": {
                    "date": "12-21",
                    "color": "#6C8893",
                    "image": "assets/winter-01.png",
                },
            },
            "seasonal_role": None,
            "applied_holidays": [],
            "last_checked_date": None,
            "opt_in_users": [],
            "role_members": [],  # tracking so it's more efficient to remove the role from everyone
            "dry_run_mode": True,
            "banner_management": {
                "original_banner_path": None,
                "holiday_banner_path": None,
                "last_banner_update": None,
                "is_holiday_banner_active": False,
            },
        }
        self.config.register_guild(**default_guild)
        self.holiday_service = HolidayService(self.config)
        self.role_manager = RoleManager(self.config)

        logger.info("Seasonal roles cog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        guild_id = GUILD_ID
        guild = self.bot.get_guild(guild_id)
        if not self.check_holidays.is_running():
            logger.debug("Starting check_holidays loop from on_ready")
            self.check_holidays.start(guild)
        else:
            logger.debug("check_holidays loop is already running")
        logger.info("Seasonal roles cog ready")

    def cog_unload(self):
        self.check_holidays.cancel()

    @commands.group(aliases=["seasonalroles", "sroles", "sr"])
    async def seasonal(self, ctx):
        """Commands related to seasonal roles."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid seasonal command passed.")

    @seasonal.group(name="member", aliases=["members"])
    async def member(self, ctx):
        """Subcommand group for managing member configurations."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid member command passed.")

    @member.command(name="add")
    async def member_add(self, ctx, member: discord.Member):
        """Adds a member to the opt-in list."""
        opt_in_users = await self.config.guild(ctx.guild).opt_in_users()
        if member.id not in opt_in_users:
            opt_in_users.append(member.id)
            await self.config.guild(ctx.guild).opt_in_users.set(opt_in_users)
            await ctx.send(
                f"{member.display_name} has been added to the {self.qualified_name}."
            )
        else:
            await ctx.send(
                f"{member.display_name} is already in the {self.qualified_name}."
            )

    @member.command(name="remove")
    async def member_remove(
        self, ctx, member: discord.Member | None, *, all_members: str | None = None
    ):
        """Removes a member or all members from the opt-in list."""
        if all_members and all_members.lower() in {"everyone", "all", "everybody"}:
            await self.config.guild(ctx.guild).opt_in_users.set([])
            await ctx.send("All members have been removed from the opt-in list.")
        elif member:
            opt_in_users = await self.config.guild(ctx.guild).opt_in_users()
            if member.id in opt_in_users:
                opt_in_users.remove(member.id)
                await self.config.guild(ctx.guild).opt_in_users.set(opt_in_users)
                await ctx.send(
                    f"{member.display_name} has been removed from the {self.qualified_name}."
                )
            else:
                await ctx.send(
                    f"{member.display_name} is not in the {self.qualified_name}."
                )
        else:
            await ctx.send(
                "Invalid command usage. Please specify a member or use 'everyone' to remove all."
            )

    @member.command(name="config")
    async def member_config(self, ctx, config_type: str):
        """Configures the opt-in list based on the given type: 'everyone' or a role name."""
        all_members_synonyms = {"everyone", "all", "everybody"}

        if config_type.lower() in all_members_synonyms:
            members = [member.id for member in ctx.guild.members if not member.bot]
            await ctx.send(f"Adding everyone to {self.qualified_name}...")
        else:
            role = discord.utils.get(ctx.guild.roles, name=config_type)
            if role:
                members = [member.id for member in role.members if not member.bot]
            else:
                await ctx.send(f"No role named {config_type} found.")
                return
        await self.config.guild(ctx.guild).opt_in_users.set(members)
        await ctx.send(f"Successfully added {config_type} to {self.qualified_name}.")

    @member.command(name="list")
    async def member_list(self, ctx):
        """Lists all members who have opted in."""
        opt_in_users = await self.config.guild(ctx.guild).opt_in_users()
        if not opt_in_users:
            await ctx.send("No members have opted in.")
            return

        # Fetching member objects from IDs
        members = [ctx.guild.get_member(user_id) for user_id in opt_in_users]
        # Filtering out None values if the member is not found in the guild
        members = [member for member in members if member is not None]

        if not members:
            await ctx.send(f"No valid members found in the {self.qualified_name}.")
            return

        # Creating a list of member names to display
        member_names = [member.display_name for member in members]
        member_list_str = ", ".join(member_names)

        # Sending the list of members
        await ctx.send(f"Opted-in members: {member_list_str}")

    @seasonal.group(aliases=["holidays"])
    async def holiday(self, ctx):
        """Commands related to holidays."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid holiday command passed.")

    async def validate_holiday(
        self, ctx: commands.Context, name: str, date: str, color: str
    ) -> bool:
        # Use the business logic validators
        if not validate_holiday_name(name):
            await ctx.send("Please provide a valid name for the holiday.")
            return False

        if not validate_color(color):
            await ctx.send("Please provide a valid hex color code (e.g., #FF0000).")
            return False

        if not validate_date_format(date):
            await ctx.send("Please provide a valid date in MM-DD format (e.g., 05-05).")
            return False

        return True

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @holiday.command(name="add")
    async def add_holiday(
        self,
        ctx: commands.Context,
        name: str,
        date: str,
        color: str,
        *,
        options: str = "",
    ) -> None:
        """
        Add a new holiday.

        Args:
        ----
            ctx: Command context
            name: Name of the holiday
            date: Date in MM-DD format
            color: Hex color code (e.g., #FF0000)
            options: Optional parameters in format "image=URL banner=URL"

        """
        valid = await self.validate_holiday(ctx, name, date, color)
        if not valid:
            return

        # Parse options string for image and banner
        image = None
        banner_url = None
        if options:
            options_parts = options.split()
            for part in options_parts:
                if "=" in part:
                    key, value = part.split("=", 1)
                    if key.lower() == "image":
                        image = value
                    elif key.lower() == "banner":
                        banner_url = value

        holiday_data = HolidayData(name, date, color, image, banner_url)
        success, message = await self.holiday_service.add_holiday(
            ctx.guild, holiday_data
        )
        await ctx.send(message)

        if success:
            await self.check_holidays(ctx.guild, force=True)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @holiday.command(name="edit")
    async def edit_holiday_command(
        self,
        ctx,
        name: str,
        date: str,
        color: str,
        *,
        options: str = "",
    ):
        """
        Edit an existing holiday's details.

        Args:
        ----
            ctx: Command context
            name: Name of the holiday to edit
            date: New date in MM-DD format
            color: New hex color code (e.g., #FF0000)
            options: Optional parameters in format "image=URL banner=URL"

        """
        valid = await self.validate_holiday(ctx, name, date, color)
        if not valid:
            return

        # Parse options string for image and banner
        image = None
        banner_url = None
        if options:
            options_parts = options.split()
            for part in options_parts:
                if "=" in part:
                    key, value = part.split("=", 1)
                    if key.lower() == "image":
                        image = value
                    elif key.lower() == "banner":
                        banner_url = value

        holiday_data = HolidayData(name, date, color, image, banner_url)
        success, message = await self.holiday_service.edit_holiday(
            ctx.guild, holiday_data
        )
        await ctx.send(message)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @holiday.command(name="remove")
    async def remove_holiday(self, ctx: commands.Context, name: str) -> None:
        """Remove an existing holiday."""
        success, message = await self.holiday_service.remove_holiday(ctx.guild, name)
        await ctx.send(message)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @holiday.command(name="list")
    async def list_holidays(self, ctx: commands.Context):
        """Lists all configured holidays along with their details."""
        try:
            logging.info(f"Holiday service looks like: {self.holiday_service}")
            holidays = await self.holiday_service.get_holidays(ctx.guild)
            if not holidays:
                await ctx.send("No holidays have been configured.")
                return

            # Use the business logic to get sorted holidays
            sorted_holidays = get_sorted_holidays(holidays)
            upcoming_holiday, days_until = find_upcoming_holiday(holidays)

            embeds = []
            for name, days in sorted_holidays:
                details = holidays[name]
                color = int(details["color"].replace("#", ""), 16)
                description = details["date"]
                if name == upcoming_holiday:
                    description += f" - Upcoming in {days_until[name]} days"
                elif days <= 0:
                    description += f" - Passed {-days} days ago"
                embed = discord.Embed(description=description, color=color)
                embed.set_author(name=name)
                embeds.append(embed)

            for embed in embeds:
                await ctx.send(embed=embed)

        except Exception:
            await ctx.send(
                "An error occurred while listing holidays. Please try again later."
            )
            logger.exception("Error listing holidays")

    async def add_holiday_role(
        self,
        ctx: commands.Context,
        name: str,
        date: str,
        color: str,
        image: str | None = None,
    ) -> discord.Role:
        valid = await self.validate_holiday(ctx, name, date, color)
        if not valid:
            return None

        role_manager = RoleManager(self.config)
        role = await role_manager.create_or_update_role(
            ctx.guild, name, color, date, image
        )
        if role:
            await ctx.send(
                f"Role '{name}' has been {'updated' if discord.utils.get(ctx.guild.roles, name=name) else 'created'}."
            )
        else:
            await ctx.send("Failed to create or update the role.")
        return role

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="dryrun")
    async def toggle_dry_run(self, ctx: commands.Context, mode: str):
        """Toggle dry run mode for seasonal role actions."""
        logger.info("toggle_dry_run command invoked")
        mode = mode.lower()
        if mode in ["enabled", "true", "on"]:
            enabled = True
        elif mode in ["disabled", "false", "off"]:
            enabled = False
        else:
            await ctx.send(
                "Invalid mode. Use 'enabled', 'true', 'on' to enable or 'disabled', 'false', 'off' to disable dry run mode."
            )
            return

        try:
            await self.config.guild(ctx.guild).dry_run_mode.set(enabled)
            mode_str = "enabled" if enabled else "disabled"
            if enabled:
                await ctx.send(
                    f"Dry run mode {mode_str}. Any actions will be simulated, and no real changes will be made."
                )
            else:
                await ctx.send(
                    f"Dry run mode {mode_str}. Actions will now make real changes."
                )
        except Exception:
            logger.exception("Error in toggle_dry_run")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="check")
    async def force_check_holidays(
        self, ctx: commands.Context, date_str: str | None = None
    ):
        """Force check holidays."""
        await self.check_holidays(ctx.guild, date_str=date_str, force=True)
        await ctx.send("Checked holidays for this guild.")

    @tasks.loop(hours=24)
    async def check_holidays(
        self, guild: discord.Guild | None = None, *, date_str: str | None = None, force: bool = False
    ):
        """
        Check for upcoming holidays and manage seasonal roles and banners accordingly.
        This task runs daily to check for upcoming holidays, create/update roles,
        and manage server banners based on configured holidays.
        """
        if guild is None:
            guild = self.guild
            logger.debug("No guild provided, using default guild.")

        try:
            # Get current date and holidays
            current_date = self._get_current_date(date_str)
            holidays = await self._get_guild_holidays(guild)
            if not holidays:
                return

            # Process holiday roles and banners
            sorted_holidays = get_sorted_holidays(holidays, current_date)
            upcoming_holiday, days_until = find_upcoming_holiday(holidays, current_date)

            logger.debug(f"Sorted holidays: {sorted_holidays}")
            banner_config = await self.config.guild(guild).banner_management()

            # Process each holiday based on its timing
            for name, days in sorted_holidays:
                holiday_details = holidays[name]
                days_until_holiday = days

                logger.debug(f"Holiday '{name}' is {days_until_holiday} days away.")

                # Save the original banner if within days before holiday and not already saved
                await self._manage_original_banner(guild, days_until_holiday, banner_config)

                holiday_context = HolidayContext(name, holiday_details, sorted_holidays, days_until_holiday)

                if days_until_holiday < 0 or days_until_holiday > DAYS_BEFORE_HOLIDAY:
                    # Past or far future holiday
                    await self._handle_past_holiday(guild, holiday_context, banner_config)
                elif 0 <= days_until_holiday <= DAYS_BEFORE_HOLIDAY:
                    # Current or upcoming holiday
                    await self._handle_upcoming_holiday(guild, name, holiday_details, days_until_holiday, force=force)
        except Exception:
            logger.exception("Error in check_holidays task")

    async def _get_guild_holidays(self, guild: discord.Guild):
        """Retrieve the configured holidays for the given guild."""
        holidays = None
        try:
            holidays = await self.config.guild(guild).holidays()
            if not holidays:
                logger.warning("No holidays configured for this guild.")
                return None
            logger.debug(f"Retrieved holidays: {holidays}")
        except Exception:
            logger.exception("Failed to retrieve holidays from config")
            return None

        return holidays

    def _get_current_date(self, date_str: str | None = None):
        """Get the current date or parse from the provided string."""
        if date_str:
            try:
                # Parse the provided date string (format should be YYYY-MM-DD)
                return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
            except ValueError:
                logger.exception(f"Invalid date format: {date_str}. Using current date instead.")

        # Use current date if no date string provided or if parsing failed
        return datetime.now(timezone.utc).date()

    async def _manage_original_banner(self, guild: discord.Guild, days_until_holiday: int, banner_config: dict):
        """Save the original banner if approaching a holiday and not already saved."""
        if (0 <= days_until_holiday <= DAYS_BEFORE_HOLIDAY and
            banner_config["original_banner_path"] is None):
            logger.debug("Attempting to save the original banner...")
            save_path = (
                Path(__file__).parent
                / f"assets/guild-banner-non-holiday-{guild.id}.png"
            )
            saved_path = await fetch_and_save_guild_banner(guild, str(save_path))
            if saved_path:
                await self.config.guild(guild).banner_management.set_raw(
                    "original_banner_path", value=saved_path
                )
                logger.info("Original banner saved.")

    async def _handle_past_holiday(
        self,
        guild: discord.Guild,
        holiday_context: HolidayContext,
        banner_config: dict | None = None
    ):
        """Handle a holiday that has passed or is too far in the future."""
        name = holiday_context.name
        holiday_details = holiday_context.details
        sorted_holidays = holiday_context.sorted_holidays
        days_until_holiday = holiday_context.days_until

        logger.debug(f"Handling past or far future holiday: {name}")

        # Remove the holiday role if it exists
        from .role.role_namer import generate_role_name
        role_name = generate_role_name(name, holiday_details["date"])
        role = discord.utils.get(guild.roles, name=role_name)

        if role:
            await self.role_manager.delete_role_from_guild(guild, role)
            logger.info(f"Role '{name}' has been removed from the guild.")

        # Restore original banner if this is the most recently passed holiday
        if days_until_holiday < 0 and name == sorted_holidays[0][0]:
            await self._restore_original_banner(guild, banner_config)

    async def _restore_original_banner(self, guild: discord.Guild, banner_config: dict):
        """Restore the original banner after a holiday ends."""
        original_banner_path = banner_config["original_banner_path"]
        if original_banner_path:
            await self.change_server_banner(guild, original_banner_path)
            logger.info("Restored the original banner.")

    async def _handle_upcoming_holiday(
        self,
        guild: discord.Guild,
        name: str,
        holiday_details: dict,
        days_until_holiday: int,
        *, force: bool = False
    ):
        """Handle a holiday that is upcoming or currently active."""
        logger.debug(f"Handling upcoming or current holiday: {name}")

        # Skip if not forced and not today
        if not force and days_until_holiday > 0:
            logger.debug(
                f"Skipping role application for '{name}' as it's not today and force is not enabled."
            )
            return

        # Create or update the holiday role
        await self._create_and_assign_holiday_role(guild, name, holiday_details)

        # Update guild banner if specified
        await self._update_holiday_banner(guild, name, holiday_details, days_until_holiday)

    async def _create_and_assign_holiday_role(
        self,
        guild: discord.Guild,
        name: str,
        holiday_details: dict
    ):
        """Create or update a holiday role and assign it to opted-in members."""
        role = await self.role_manager.create_or_update_role(
            guild,
            name,
            holiday_details["color"],
            holiday_details["date"],
            holiday_details.get("image"),
        )

        if role:
            await self.role_manager.assign_role_to_all_members(guild, role)
            logger.info(f"Applied holiday role for '{name}' to opted-in members.")
        else:
            logger.error(f"Failed to create or update role for '{name}'")

    async def _update_holiday_banner(
        self,
        guild: discord.Guild,
        name: str,
        holiday_details: dict,
        days_until_holiday: int
    ):
        """Update the guild banner with a holiday-specific banner if available."""
        if ("banner" in holiday_details and
            0 <= days_until_holiday <= DAYS_BEFORE_HOLIDAY):

            holiday_banner_path = holiday_details["banner"]
            await self.change_server_banner(guild, holiday_banner_path)
            await self.config.guild(guild).banner_management.set_raw(
                "is_holiday_banner_active", value=True
            )
            logger.info(f"Updated guild banner for '{name}' and set is_holiday_banner_active to True.")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="forceholiday")
    async def force_holiday(
        self, ctx: commands.Context, *holiday_name_parts: str
    ) -> None:
        holiday_name = " ".join(holiday_name_parts).lower()
        guild = ctx.guild
        holidays = await self.config.guild(guild).holidays()
        dry_run_mode = await self.config.guild(guild).dry_run_mode()

        logger.debug(
            f"Processing forceholiday for '{holiday_name}' with dry run mode set to {dry_run_mode}."
        )

        save_path = (
            Path(__file__).parent / f"assets/guild-banner-non-holiday-{guild.id}.png"
        )
        try:
            saved_path = await fetch_and_save_guild_banner(guild, str(save_path))
            if saved_path:
                await self.config.guild(guild).banner_management.set_raw(
                    "original_banner_path", value=saved_path
                )
                logger.info("Original banner saved.")
            else:
                logger.error("Failed to save the original banner.")
                await ctx.send(
                    "Failed to save the original banner. Please check the logs for more details."
                )
        except Exception:
            logger.exception("Error saving the original banner")
            await ctx.send(
                "An error occurred while saving the original banner. Please check the logs for more details."
            )

        # Use the business logic to find the holiday case-insensitively
        original_name, holiday_details = find_holiday(holidays, holiday_name)

        if original_name and holiday_details:
            logger.debug(
                f"Found holiday details for '{holiday_name}' as '{original_name}': {holiday_details}"
            )
            if "banner" in holiday_details:
                holiday_banner_path = Path(__file__).parent / holiday_details["banner"]
                try:
                    await self.change_server_banner(guild, str(holiday_banner_path))
                    logger.info(f"Updated guild banner for '{original_name}'.")
                except Exception:
                    logger.exception(
                        f"Error updating guild banner for '{original_name}'"
                    )
                    await ctx.send(
                        f"An error occurred while updating the guild banner for '{original_name}'. Please check the logs for more details."
                    )
            else:
                await ctx.send(f"No banner specified for '{original_name}'.")
        else:
            await ctx.send(f"No details found for the holiday '{holiday_name}'.")
            logger.error(f"No details found for the holiday '{holiday_name}'.")
            return

        (
            success,
            message,
        ) = await self.holiday_service.remove_all_except_current_holiday_role(
            guild, original_name
        )
        if message:
            logger.debug(message)
            await ctx.send(message)
        if not success:
            logger.error("Failed to clear other holidays.")
            return

        success, message = await self.holiday_service.apply_holiday_role(
            guild, original_name, dry_run_mode
        )
        if message:
            logger.debug(message)
            await ctx.send(message)
        if not success:
            logger.error("Failed to apply holiday role.")

    @check_holidays.before_loop
    async def before_check_holidays(self):
        await self.bot.wait_until_ready()
        self.guild = self.bot.get_guild(GUILD_ID)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="setbanner")
    async def set_banner(self, ctx: commands.Context, image_url: str | None = None):
        """
        Change the server's banner to the provided URL.
        """
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif not image_url:
            await ctx.send(
                "Please provide a URL to an image or attach an image to your message."
            )
            return

        if ctx.guild.premium_tier < PREMIUM_TIER_REQUIRED:
            await ctx.send(
                "This server needs to be at least level 2 boosted to change the banner."
            )
            return

        await ctx.send(f"Attempting to change the server banner to: {image_url}")
        result = await self.change_server_banner(ctx.guild, image_url)
        await ctx.send(result)

        if "successfully" in result.lower():
            # Save the banner path as the non-holiday banner
            save_path = (
                Path(__file__).parent
                / f"assets/guild-banner-non-holiday-{ctx.guild.id}.png"
            )
            await fetch_and_save_guild_banner(ctx.guild, str(save_path))
            await self.config.guild(ctx.guild).banner_management.set_raw(
                "original_banner_path", value=str(save_path)
            )

    async def change_server_banner(self, guild: discord.Guild, image_url: str) -> str:
        """
        Changes the server's banner to the provided image URL.
        """
        try:
            image_handler = get_image_handler()
            if not image_handler:
                return "Failed to initialize image handler."

            image_bytes = await image_handler.fetch_image(image_url)
            if not image_bytes:
                return f"Failed to fetch image from URL: {image_url}"

            await guild.edit(banner=image_bytes)

        except discord.HTTPException as e:
            return f"A Discord API error occurred: {e}"
        except (ValueError, TypeError, AttributeError) as e:
            return f"An error occurred processing the image: {e}"
        except Exception:
            logger.exception("Unexpected error changing server banner")
            return "An unexpected error occurred. Please check logs for details."
        else:
            return f"Successfully changed the server banner to {image_url}"

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Handles the event when a member joins the server by automatically adding them to the opt-in users list
        and assigning them any relevant holiday roles based on the current date.

        This method checks if the joining member is a bot and skips further processing if true. For non-bot members,
        it performs the following operations:
        1. Adds the member to the 'opt_in_users' list if they are not already included.
        2. Checks the current date against configured holidays in the guild's settings.
        3. Assigns the corresponding holiday role to the member if the current date matches any holiday date.
        """
        if member.bot:
            return  # Skip bots

        opt_in_users = await self.config.guild(member.guild).opt_in_users()

        if member.id not in opt_in_users:
            opt_in_users.append(member.id)
            await self.config.guild(member.guild).opt_in_users.set(opt_in_users)
            logger.info(f"Added {member.display_name} to opt-in users.")

        # Check and assign holiday roles using the existing method
        await self.check_holidays(member.guild, force=True)

    async def toggle_seasonal_role(self, ctx: commands.Context) -> None:
        """Toggle opting in/out from the seasonal role."""
        try:
            opt_in_users = await self.config.guild(ctx.guild).opt_in_users()
            opt_out_users = await self.config.guild(ctx.guild).opt_out_users()

            if ctx.author.id in opt_in_users:
                # User is opted in, so opt them out
                opt_in_users.remove(ctx.author.id)
                opt_out_users.append(ctx.author.id)
                await self.config.guild(ctx.guild).opt_in_users.set(opt_in_users)
                await self.config.guild(ctx.guild).opt_out_users.set(opt_out_users)
                await ctx.send(
                    f"{ctx.author.mention}, you have opted out from the seasonal role."
                )
            else:
                # User is not opted in, so opt them in
                opt_out_users.remove(
                    ctx.author.id
                ) if ctx.author.id in opt_out_users else None
                opt_in_users.append(ctx.author.id)
                await self.config.guild(ctx.guild).opt_in_users.set(opt_in_users)
                await self.config.guild(ctx.guild).opt_out_users.set(opt_out_users)
                await ctx.send(
                    f"{ctx.author.mention}, you have opted in to the seasonal role!"
                )

                # Check if there's a current holiday and if the member has its role.
                current_date = datetime.now(timezone.utc).date()
                holidays = await self.config.guild(ctx.guild).holidays()
                for holiday, details in holidays.items():
                    holiday_date = (
                        datetime.strptime(details["date"], "%m-%d")
                        .replace(tzinfo=timezone.utc)
                        .date()
                        .replace(year=current_date.year)
                    )
                    if current_date == holiday_date:
                        role = discord.utils.get(ctx.guild.roles, name=holiday)
                        if role:
                            await ctx.author.add_roles(role)
                            await ctx.send(f"You have been given the {role.name} role!")
        except Exception:
            logger.exception("Error toggling seasonal role")
            await ctx.send(
                "An error occurred while toggling your seasonal role preference."
            )
