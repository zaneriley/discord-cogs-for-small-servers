from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import aiofiles
import aiohttp
import discord
from discord.ext import tasks

from utilities.date_utils import DateUtil

try:
    from redbot.core import Config, commands
except ModuleNotFoundError:
    Config = None
    commands = None

    class DummyConfig:

        """Dummy class for when the bot code is not available (local dev)."""

        def get_conf(*_args, **_kwargs):
            return None

        def __init__(self, *args, **kwargs):
            pass

    Config = DummyConfig

from utilities.discord_utils import fetch_and_save_guild_banner

from .holiday.holiday_calculator import (
    find_upcoming_holiday as calc_upcoming_holiday,
    compute_days_until_holiday,
)
from .holiday.holiday_calculator import (
    get_sorted_holidays as calc_sorted_holidays,
)
from .holiday.holiday_validator import (
    find_holiday,
    find_holiday_matches,
    validate_color,
    validate_date_format,
    validate_holiday_name,
)
from .holiday_announcer import HolidayAnnouncer
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

# Constants
MATCH_CONFIDENCE_THRESHOLD = 0.75
EXACT_MATCH_THRESHOLD = 0.9
PREMIUM_TIER_REQUIRED = 2
MIN_SEARCH_TERM_LENGTH = 2

# Constants for holiday announcement timing
DAYS_BEFORE_ANNOUNCEMENT = 7  # Number of days before a holiday to announce
SAME_DAY_THRESHOLD = 0  # Threshold for same-day checks
NEXT_DAY_THRESHOLD = 1  # Threshold for next-day checks
COPYWRITING_CHECK_DAYS = 21  # Check for missing copy 3 weeks in advance

# Define constants for proper date comparison
DATE_PARTS_EXPECTED_LENGTH = 2
MONTH_DAY_VALUE_MULTIPLIER = 100
INVALID_DATE_SORT_VALUE = 9999

# HTTP Status constants
HTTP_OK = 200

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
            "holidays": {},  # Empty dictionary - holidays will be loaded from holidays.json
            "dryrun": {
                "enabled": False,
                "channel_id": None,
            },
            "announcement_config": {
                "enabled": False,
                "channel_id": None,
                "mention_type": None,
                "role_id": None,
                "templates": {},  # Custom templates
                "last_announcements": {},  # Tracks when announcements were last sent
            },
            "banner_management": {
                "enabled": False,
                "original_banner_path": None,
                "is_holiday_banner_active": False,
                "holiday_banner_path": None,
            },
            "opt_in_users": [],
            "role_members": [],
            "last_checked_date": None,
            "seasonal_role": None,
            "applied_holidays": [],
        }
        self.config.register_guild(**default_guild)

        # Initialize the holiday announcer first since it loads from holidays.json
        self.holiday_announcer = HolidayAnnouncer(self.bot, self.config)

        # Initialize holiday service with the config
        self.holiday_service = HolidayService(self.config)
        self.role_manager = RoleManager(self.config)

        # Schedule migration of existing holidays from config to holidays.json
        self.bot.loop.create_task(self._migrate_holidays_to_json())

        logger.info("Seasonal roles cog initialized")

    async def _migrate_holidays_to_json(self):
        """Migrate existing holiday data from config to holidays.json if needed."""
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            try:
                # Get holidays from config
                config_holidays = await self.config.guild(guild).holidays()

                if config_holidays and not self.holiday_announcer.holidays_data:
                    logger.info(f"Migrating holidays for guild {guild.name} from config to holidays.json")

                    # Convert config format to holidays.json format
                    holidays_json = {"holidays": {}}
                    for name, details in config_holidays.items():
                        holidays_json["holidays"][name] = {
                            "date": details["date"],
                            "color": details["color"],
                        }
                        if "image" in details:
                            holidays_json["holidays"][name]["image"] = details["image"]
                        if "banner" in details:
                            holidays_json["holidays"][name]["banner"] = details["banner"]

                    # Save to holidays.json
                    cog_dir = Path(__file__).parent
                    holidays_file = cog_dir / "holidays.json"

                    with holidays_file.open("w") as f:
                        json.dump(holidays_json, f, indent=4)

                    logger.info(f"Migration complete. Holidays saved to {holidays_file}")

                    # Reload the holiday announcer's data
                    await self.holiday_announcer.reload_data_async()

                    # Clear the config holidays since they're now in holidays.json
                    await self.config.guild(guild).holidays.set({})
            except Exception:  # noqa: PERF203 - This is a migration method that runs rarely
                logger.exception(f"Error migrating holidays for guild {guild.name}")

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
        """
        Commands related to seasonal roles and holiday announcements.

        Commands:
        - member: Manage members who receive seasonal roles
        - holiday: Add, edit, and manage holidays
        - announce: Configure and send holiday announcements
        - forceholiday: Manually apply a holiday's role to members
        - checkholidays: Manually check for holidays right now
        - banner: Change the server banner
        - dryrun: Test seasonal features without affecting members
        """
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
            # Log current state
            logging.info("=== START list_holidays execution ===")
            logging.info(f"Command context: guild={ctx.guild.id}, channel={ctx.channel.id}, user={ctx.author.id}")
            logging.info(f"Holiday service type: {type(self.holiday_service).__name__}")
            logging.info(f"Repository type: {type(self.holiday_service.repository).__name__}")
            logging.info(f"Inner JsonRepo established: {hasattr(self.holiday_service.repository, 'json_repo')}")

            if hasattr(self.holiday_service.repository, "json_repo"):
                logging.info(f"JsonRepo data initialized: {self.holiday_service.repository.json_repo.data is not None}")

            # Log when retrieving holidays
            logging.info(f"Retrieving holidays for guild: {ctx.guild.id} - {ctx.guild.name}")
            holidays = await self.holiday_service.get_holidays(ctx.guild)
            logging.info(f"Retrieved holidays: {holidays}")

            # Direct testing of repository
            try:
                if hasattr(self.holiday_service.repository, "json_repo"):
                    logging.info("Testing direct repository access")
                    # Load directly from the file to compare
                    cog_dir = Path(__file__).parent
                    holidays_file = cog_dir / "holidays.json"

                    if holidays_file.exists():
                        with open(holidays_file, "r") as f:
                            direct_data = json.load(f)
                            direct_holidays = direct_data.get("holidays", {})
                            logging.info(f"Direct file access found {len(direct_holidays)} holidays")
                            logging.info(f"Direct vs Repository: {len(direct_holidays)} vs {len(holidays)}")
                    else:
                        logging.error(f"holidays.json not found at {holidays_file}")
            except Exception:
                logging.exception(f"Error during direct repository test")

            if not holidays:
                logging.warning(f"No holidays returned for guild {ctx.guild.id} - {ctx.guild.name}")
                await ctx.send("No holidays have been configured.")
                return

            # Test if sorted_holidays can be calculated correctly
            try:
                # Use the business logic to get sorted holidays
                logging.info("Calculating sorted_holidays")
                sorted_holidays = calc_sorted_holidays(holidays)
                logging.info(f"Sorted holidays result: {sorted_holidays}")

                logging.info("Calculating upcoming holiday")
                upcoming_holiday, days_until = calc_upcoming_holiday(holidays)
                logging.info(f"Upcoming holiday: {upcoming_holiday}, days until: {days_until}")
            except Exception:
                logging.exception(f"Error calculating holiday sort/upcoming")
                raise

            # Create embed messages
            logging.info("Creating embed messages for holidays")
            embeds = []
            for name, days in sorted_holidays:
                details = holidays[name]
                try:
                    color = int(details["color"].replace("#", ""), 16)
                    description = details["date"]
                    if name == upcoming_holiday:
                        description += f" - Upcoming in {days_until[name]} days"
                    elif days <= 0:
                        description += f" - Passed {-days} days ago"
                    embed = discord.Embed(description=description, color=color)
                    embed.set_author(name=name)
                    embeds.append(embed)
                except Exception:
                    logging.exception(f"Error creating embed for holiday {name}")

            # Send embeds to channel
            logging.info(f"Sending {len(embeds)} embeds to channel")
            for embed in embeds:
                await ctx.send(embed=embed)

            logging.info("=== END list_holidays execution: SUCCESS ===")

        except Exception:
            logging.exception(f"Error in list_holidays")
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

    async def _ensure_dryrun_enabled(self, ctx: commands.Context) -> bool:
        """
        Check if dry run mode is enabled for this guild.

        Args:
            ctx: The command context

        Returns:
            bool: True if dry run is enabled, False otherwise

        """
        # Check the guild configuration to see if dry run is enabled
        dryrun_config = await self.config.guild(ctx.guild).dryrun()
        dryrun_enabled = dryrun_config.get("enabled", False)

        if not dryrun_enabled:
            await ctx.send(
                "⚠️ Dry run mode is not enabled. "
                "Use `!seasonal dryrun toggle on` to enable it first."
            )
            return False

        return True

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.group(name="dryrun")
    async def seasonal_dryrun(self, ctx):
        """Dry run commands for testing seasonal features without making actual changes."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @seasonal_dryrun.command(name="toggle")
    async def dryrun_toggle(self, ctx, mode: str):
        """Toggle dry run mode on or off."""
        logger.info("dryrun_toggle command invoked")
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
            await self.config.guild(ctx.guild).dryrun.set_raw("enabled", value=enabled)
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
            logger.exception("Error in dryrun_toggle")
            await ctx.send("An error occurred while toggling dry run mode.")

    @seasonal_dryrun.command(name="role")
    async def dryrun_role(self, ctx, *, holiday_name: str):
        """Preview what role would be created/updated for a specific holiday."""
        # Ensure dry run is enabled
        if not await self._ensure_dryrun_enabled(ctx):
            return

        # Get holiday details and show role preview
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        # For partial matches with lower confidence, confirm with user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Preview cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Preview cancelled.")
                return

        # Show what the role would look like
        color_hex = holiday_details["color"]
        date = holiday_details["date"]
        embed = discord.Embed(
            title=f"Role Preview: {original_name}",
            description="This is what the role would look like if applied",
            color=int(color_hex[1:], 16)
        )

        embed.add_field(name="Role Name", value=f"{original_name} ({date})")
        embed.add_field(name="Color", value=color_hex)

        if "image" in holiday_details:
            embed.add_field(name="Icon", value=f"`{holiday_details['image']}`")

        # Show affected members count
        opt_in_users = await self.config.guild(ctx.guild).opt_in_users()
        embed.add_field(
            name="Members who would receive this role",
            value=f"{len(opt_in_users)} members"
        )

        await ctx.send(embed=embed)

    @seasonal_dryrun.command(name="announcements")
    async def dryrun_announcements(self, ctx, *, holiday_name: str):
        """
        Preview all announcements for a holiday (before, during, after).

        Parameters
        ----------
        ctx : discord.Context
            The invocation context.
        holiday_name : str
            The name of the holiday to preview announcements for.

        """
        # Ensure dry run is enabled
        if not await self._ensure_dryrun_enabled(ctx):
            return

        # Find the holiday
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        # For partial matches with lower confidence, confirm with user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Preview cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Preview cancelled.")
                return

        from .holiday.holiday_data import Holiday

        # Add logging to debug the Holiday object creation
        logger.debug(f"Creating Holiday object with original_name={original_name}, details={holiday_details}")

        # Parse the date string ("MM-DD") into month and day integers
        try:
            date_parts = holiday_details["date"].split("-")
            month = int(date_parts[0])
            day = int(date_parts[1])

            holiday_obj = Holiday(
                name=original_name,
                color=holiday_details.get("color", "#FFFFFF"),
                image=holiday_details.get("image", ""),
                month=month,
                day=day
            )
            logger.debug(f"Successfully created Holiday object: {holiday_obj}")
        except Exception as e:
            logger.exception("Failed to create Holiday object")
            await ctx.send(f"Error creating Holiday object: {e}")
            return

        # Get the announcement channel config
        announcement_config = await self.config.guild(ctx.guild).announcement_config()
        channel_id = announcement_config.get("channel_id")
        channel_mention = f"<#{channel_id}>" if channel_id else "No channel configured"

        # Display header info
        await ctx.send(f"# **Announcement Preview for {original_name}**")
        await ctx.send(f"Announcements would be sent to: {channel_mention}")

        # Show before announcement (7 days before)
        await ctx.send("\n## **7 DAYS BEFORE ANNOUNCEMENT**")
        await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="before",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=7,
            to_channel=True,
            ctx=ctx
        )

        # Show during announcement (day of)
        await ctx.send("\n## **DAY OF HOLIDAY ANNOUNCEMENT**")
        await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="during",
            user=ctx.author,
            guild_id=ctx.guild.id,
            to_channel=True,
            ctx=ctx
        )

        # Show after announcement (day after)
        await ctx.send("\n## **DAY AFTER HOLIDAY ANNOUNCEMENT**")
        await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="after",
            user=ctx.author,
            guild_id=ctx.guild.id,
            to_channel=True,
            ctx=ctx
        )

        await ctx.send("\n**Note:** These announcements would be sent automatically at the appropriate times.")

    @seasonal_dryrun.command(name="announcement_phase")
    async def dryrun_announce_phase(self, ctx, holiday_name: str, phase: str, days_until: int | None = None):
        """
        Preview a specific announcement phase for a holiday.

        Parameters
        ----------
        ctx : discord.Context
            The invocation context.
        holiday_name : str
            The name of the holiday to preview.
        phase : str
            One of 'before', 'during', or 'after'.
        days_until : int | None
            For 'before' phase, how many days until the holiday (default: 7).

        """
        # Ensure dry run is enabled
        if not await self._ensure_dryrun_enabled(ctx):
            return

        # Validate phase
        if phase not in ["before", "during", "after"]:
            await ctx.send("Invalid phase. Must be one of: 'before', 'during', or 'after'")
            return

        # Validate days_until for 'before' phase
        if phase == "before" and days_until is None:
            days_until = 7  # Default to 7 days before

        # Find the holiday
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        # For partial matches with lower confidence, confirm with user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Preview cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Preview cancelled.")
                return

        from .holiday.holiday_data import Holiday

        # Parse the date string ("MM-DD") into month and day integers
        try:
            date_parts = holiday_details["date"].split("-")
            month = int(date_parts[0])
            day = int(date_parts[1])

            holiday_obj = Holiday(
                name=original_name,
                color=holiday_details.get("color", "#FFFFFF"),
                image=holiday_details.get("image", ""),
                month=month,
                day=day
            )
            logger.debug(f"Successfully created Holiday object: {holiday_obj}")
        except Exception as e:
            logger.exception("Failed to create Holiday object")
            await ctx.send(f"Error creating Holiday object: {e}")
            return

        # Preview the announcement for the specific phase
        await ctx.send(f"**Previewing {phase} announcement for {original_name}:**")

        # Call the preview method with appropriate parameters
        success, message = await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_details,
            phase=phase,
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=days_until if phase == "before" else None,
            to_channel=True,
            ctx=ctx
        )

        if not success:
            await ctx.send(f"Failed to generate preview: {message}")

    @seasonal_dryrun.command(name="banner")
    async def dryrun_banner(self, ctx, *, holiday_name: str):
        """
        Preview what a holiday banner would look like without changing it.

        Parameters
        ----------
        ctx : discord.Context
            The invocation context.
        holiday_name : str
            The name of the holiday to preview banner for.

        """
        # Constants for Discord's recommended banner dimensions
        discord_banner_width = 960
        discord_banner_height = 540

        # Ensure dry run is enabled
        if not await self._ensure_dryrun_enabled(ctx):
            return

        # Find the holiday
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        # For partial matches with lower confidence, confirm with user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Preview cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Preview cancelled.")
                return

        # Check if banner is configured
        if "banner" not in holiday_details:
            await ctx.send(f"No banner configured for '{original_name}'. Use `/seasonal holiday edit {original_name} banner <path>` to add one.")
            return

        banner_path = holiday_details["banner"]

        # Create embed to display banner info
        embed = discord.Embed(
            title=f"Banner Preview for {original_name}",
            description=f"This is what the server banner would look like during the {original_name} holiday.",
            color=int(holiday_details["color"][1:], 16)
        )

        embed.add_field(name="Banner Path", value=f"`{banner_path}`", inline=False)

        # Check if file exists
        banner_file = Path(f"./assets/banners/{banner_path}")
        if banner_file.exists():
            embed.add_field(name="Status", value="✅ Banner file exists", inline=False)

            # Try to get the dimensions if it's an image file
            try:
                from PIL import Image
                with Image.open(banner_file) as img:
                    width, height = img.size
                    embed.add_field(
                        name="Dimensions",
                        value=f"{width} x {height} pixels",
                        inline=True
                    )

                    # Check if it meets Discord's banner requirements
                    if width != discord_banner_width or height != discord_banner_height:
                        dimensions_msg = (
                            f"{discord_banner_width}x{discord_banner_height}"
                        )
                        embed.add_field(
                            name="⚠️ Warning",
                            value=(
                                f"This banner doesn't match Discord's recommended "
                                f"dimensions of {dimensions_msg}."
                            ),
                            inline=False
                        )
            except (ImportError, OSError):
                embed.add_field(
                    name="Dimensions",
                    value="Unable to determine (not an image or PIL not installed)",
                    inline=True
                )

            # Attach the banner file to the message
            try:
                file = discord.File(banner_file, filename=banner_path)
                embed.set_image(url=f"attachment://{banner_path}")
                await ctx.send(embed=embed, file=file)
            except (OSError, discord.DiscordException) as e:
                embed.add_field(
                    name="Error",
                    value=f"Could not attach file: {e}",
                    inline=False
                )
                await ctx.send(embed=embed)
        else:
            embed.add_field(
                name="⚠️ Error",
                value=f"Banner file not found at `./assets/banners/{banner_path}`",
                inline=False
            )
            embed.add_field(
                name="Fix",
                value="Place the banner file in the correct location or update the banner path",
                inline=False
            )
            await ctx.send(embed=embed)

    @seasonal_dryrun.command(name="simulate")
    async def dryrun_simulate(self, ctx, *, holiday_name: str | None = None):
        """
        Simulates what would happen during a holiday without actually making any changes.

        This simulation shows:
        1. The day before the holiday (role opt-in, announcement)
        2. The day of the holiday (banner change, announcement)
        3. The day after the holiday (role removal, banner reset, announcement)

        Parameters
        ----------
        ctx : discord.Context
            The invocation context.
        holiday_name : str
            The name or partial name of the holiday to simulate.

        """
        logger.debug(f"dryrun_simulate command called by {ctx.author} in guild {ctx.guild.name} (ID: {ctx.guild.id})")
        logger.debug(f"Holiday name provided: {holiday_name}")

        if not await self._ensure_dryrun_enabled(ctx):
            logger.debug("Dry run mode not enabled, aborting simulation")
            return

        # If no holiday name provided, prompt with the selection menu
        if not holiday_name:
            await ctx.send("No holiday specified. Please use the selection menu to choose a holiday.")
            await self.select_holiday(ctx)
            return

        # Find the holiday with our improved find_holiday function
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        logger.debug(f"Retrieved {len(holidays)} holidays for guild {ctx.guild.id}")

        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)
        logger.debug(f"Found holiday: {original_name}, match score: {match_score}")

        if holiday_details:
            logger.debug(f"Holiday details found: {holiday_details}")
        else:
            logger.warning(f"No holiday details found for '{holiday_name}'")

        if not original_name:
            await ctx.send(f"No holiday found matching '{holiday_name}'.")
            logger.warning(f"No holiday found matching '{holiday_name}'")
            return

        # For partial matches with lower confidence, confirm with user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            logger.debug(f"Low confidence match ({match_score} < {MATCH_CONFIDENCE_THRESHOLD}), requesting confirmation")
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Simulation cancelled.")
                    logger.debug("User cancelled the simulation")
                    return
                logger.debug("User confirmed the holiday selection")
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Simulation cancelled.")
                logger.debug("Holiday confirmation timed out")
                return

        # Create Holiday object
        try:
            # Parse the date string ("MM-DD") into month and day integers
            date_parts = holiday_details["date"].split("-")
            logger.debug(f"Parsing date from {holiday_details['date']}")

            month = int(date_parts[0])
            day = int(date_parts[1])

            logger.debug(f"Parsed date parts: month={month}, day={day}")

            from .holiday.holiday_data import Holiday

            holiday_obj = Holiday(
                name=original_name,
                color=holiday_details.get("color", "#FFFFFF"),
                image=holiday_details.get("image", ""),
                month=month,
                day=day
            )
            logger.debug(f"Successfully created Holiday object for simulation: {holiday_obj}")

            # Debugging holiday object properties
            logger.debug(f"Holiday object properties: name={holiday_obj.name}, month={holiday_obj.month}, day={holiday_obj.day}")
            logger.debug(f"Holiday object color: {holiday_obj.color}, image: {holiday_obj.image}")
            if hasattr(holiday_obj, "date_start"):
                logger.debug(f"Holiday date_start: {holiday_obj.date_start}, date_end: {holiday_obj.date_end}")
        except Exception as e:
            logger.exception(f"Failed to create Holiday object for simulation")
            await ctx.send(f"Error creating Holiday object: {e}")
            return

        # Continue with the original implementation for simulation
        await ctx.send(f"## **SIMULATING HOLIDAY LIFECYCLE: {original_name}**")
        await ctx.send("This will show what would happen at each phase of the holiday.")

        # Define constants for simulation
        days_before_announcement = 7

        # Phase 1: Week before holiday
        await ctx.send("\n## **PHASE 1: DAYS BEFORE THE HOLIDAY**")
        await ctx.send(f"The following would happen {days_before_announcement} days before the holiday:")

        # Show role creation
        await ctx.send("**Actions:**")
        await ctx.send("- Holiday role would be created (if it doesn't exist)")
        await ctx.send("- Members would be able to opt-in to receive the role")

        # Show announcement
        await ctx.send("**Announcement that would be sent before the holiday:**")

        logger.debug(f"Calling preview_holiday_announcement for 'before' phase, days_until={days_before_announcement}")
        preview_result = await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="before",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=days_before_announcement,
            to_channel=True,
            ctx=ctx
        )
        logger.debug(f"Preview 'before' result: {preview_result}")

        # Phase 2: Day of holiday
        await ctx.send("\n## **PHASE 2: DAY OF THE HOLIDAY**")
        await ctx.send("The following would happen on the day of the holiday:")

        # Show banner change
        await ctx.send("**Actions:**")
        if "banner" in holiday_details:
            banner_path = holiday_details["banner"]
            await ctx.send(f"**Banner would change to:** `{banner_path}`")
            logger.debug(f"Banner would change to: {banner_path}")
        else:
            logger.debug("No banner specified in holiday details")

        # Show announcement
        await ctx.send("**Announcement that would be sent on the holiday:**")

        logger.debug(f"Calling preview_holiday_announcement for 'during' phase")
        preview_result = await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="during",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=0,
            to_channel=True,
            ctx=ctx
        )
        logger.debug(f"Preview 'during' result: {preview_result}")

        # Phase 3: Day after
        await ctx.send("\n## **PHASE 3: DAY AFTER THE HOLIDAY**")
        await ctx.send("The following would happen the day after the holiday:")

        # Show role/banner cleanup
        await ctx.send("**Actions:**")
        await ctx.send("- Holiday role would be removed from all members")
        await ctx.send("- Server banner would be restored to original (if changed)")

        # Show announcement
        await ctx.send("**Announcement that would be sent after the holiday:**")

        logger.debug(f"Calling preview_holiday_announcement for 'after' phase")
        preview_result = await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="after",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=-1,
            to_channel=True,
            ctx=ctx
        )
        logger.debug(f"Preview 'after' result: {preview_result}")

        # Final summary
        logger.debug(f"Completed holiday simulation for {original_name}")
        await ctx.send("\n## **SIMULATION COMPLETE**")
        await ctx.send("This simulation shows what would happen during an actual holiday without making real changes.")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="forceholiday")
    async def force_holiday(self, ctx: commands.Context, *holiday_name_parts: str) -> None:
        """
        Force apply a holiday by name (partial matching supported).

        Examples:
        !seasonal forceholiday spring      (matches Spring Blossom Festival)
        !seasonal forceholiday new year    (matches New Year's Celebration)

        """
        holiday_name = " ".join(holiday_name_parts).lower()
        guild = ctx.guild
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        dry_run_mode = await self.config.guild(guild).dry_run_mode()

        logger.debug(f"Processing forceholiday for '{holiday_name}' with dry run mode set to {dry_run_mode}.")

        # Use improved find_holiday function with partial matching
        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)

        if not original_name or not holiday_details:
            await ctx.send(f"No holiday found matching '{holiday_name}'.")
            return

        # For partial matches below a certain confidence, confirm with the user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Command cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Command cancelled.")
                return

        # Continue with original implementation
        try:
            asset_path = Path(__file__).parent / f"assets/guild-banner-non-holiday-{guild.id}.png"
            saved_path = await fetch_and_save_guild_banner(guild, asset_path)
            if saved_path:
                await self.config.guild(guild).banner_management.set_raw("original_banner_path", value=saved_path)
                logger.info("Original banner saved.")
            else:
                logger.error("Failed to save the original banner.")
                await ctx.send("Failed to save the original banner. Please check the logs for more details.")

            # Apply the holiday banner
            if "banner" in holiday_details:
                holiday_banner_path = Path(__file__).parent / holiday_details["banner"]
                try:
                    await self.change_server_banner(guild, holiday_banner_path)
                    logger.info(f"Updated guild banner for '{original_name}'.")
                except Exception as e:
                    logger.exception("Error updating guild banner")
                    await ctx.send(f"An error occurred while updating the guild banner for '{original_name}': {e}")
            else:
                await ctx.send(f"No banner specified for '{original_name}'.")

            # The validate_holiday_exists expects original find_holiday format, so we need to adapt
            exists, message = await self.holiday_service.validate_holiday_exists(holidays, original_name)
            if not exists:
                logger.error(f"Failed to find holiday: {message}")
                await ctx.send(message or "An error occurred.")
                return

            success, message = await self.holiday_service.remove_all_except_current_holiday_role(guild, original_name)
            if message:
                logger.debug(message)
                await ctx.send(message)
            if not success:
                logger.error("Failed to clear other holidays.")
                return

            success, message = await self.holiday_service.apply_holiday_role(guild, original_name)
            if message:
                logger.debug(message)
                await ctx.send(message)
            if not success:
                logger.error("Failed to apply holiday role.")

        except (discord.HTTPException, OSError, ValueError) as e:
            logger.exception("Error saving the original banner")
            await ctx.send(f"An error occurred while saving the original banner: {e}")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="banner")
    async def change_server_banner_command(self, ctx, url: str | None = None):
        """
        Change the server banner using either a URL or an uploaded/pasted image.

        Examples:
        - Upload/paste: !seasonal banner  (attach or paste an image with the command)
        - URL: !seasonal banner https://example.com/banner.png

        """
        # Check if guild has banner feature
        if "BANNER" not in ctx.guild.features:
            await ctx.send("This server does not have the banner feature. You need level 2 boost status to use banners.")
            return

        # Check for direct attachment or pasted image
        if not url and ctx.message.attachments:
            # Use the first attachment as the source
            url = ctx.message.attachments[0].url
            logger.debug(f"Using attachment URL: {url}")

        # Check for message reference (reply) with attachment
        if not url and ctx.message.reference:
            referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if referenced_message and referenced_message.attachments:
                url = referenced_message.attachments[0].url
                logger.debug(f"Using referenced message attachment URL: {url}")

        # If we still don't have a URL, prompt the user
        if not url:
            await ctx.send("Please provide a banner URL, upload an image, or paste an image along with the command.")
            return

        # Using the utility method to handle banner change
        save_path = await self.change_server_banner(ctx.guild, url)

        if save_path:
            # Ensure path is a string before storing in config
            save_path_str = str(save_path)
            logger.debug(f"Saving banner path to config: {save_path_str}")
            await self.config.guild(ctx.guild).banner_management.set_raw("original_banner_path", value=save_path_str)
            await ctx.send(f"Server banner changed successfully and original banner saved to {save_path_str}")
        else:
            await ctx.send("Failed to change the server banner. Make sure the URL is valid and the image meets Discord's requirements.")

    async def change_server_banner(self, guild, url):
        """
        Change the server banner and save the original banner.

        Args:
            guild: The guild to change the banner for
            url: The URL or path to the new banner image

        Returns:
            str: The path where the original banner was saved, or None if failed

        """
        if "BANNER" not in guild.features:
            logger.warning(f"Guild {guild.name} does not have the banner feature.")
            return None

        try:
            # Save original banner first
            from utilities.discord_utils import fetch_and_save_guild_banner

            asset_path = Path(__file__).parent / f"assets/guild-banner-non-holiday-{guild.id}.png"
            save_path = await fetch_and_save_guild_banner(guild, asset_path)

            if not save_path:
                logger.warning(f"Failed to save original banner for guild {guild.name}")
                return None

            # Handle the banner image using image_utils
            from utilities.image_utils import get_image_handler

            # Check if the URL is actually a local path
            if not url.startswith(("http://", "https://")):
                # Treat as local path
                image_path = Path(url)
                if not image_path.exists():
                    logger.error(f"Local image file not found: {url}")
                    return None

            # Get the appropriate image handler and fetch the image data
            try:
                image_handler = get_image_handler(url)
                banner_bytes = await image_handler.fetch_image_data()

                # Update the guild's banner
                dry_run_mode = await self.config.guild(guild).dryrun.get_raw("enabled", default=False)
                if not dry_run_mode:
                    await guild.edit(banner=banner_bytes)
                    logger.info(f"Changed banner for guild {guild.name}")
                else:
                    logger.info(f"[Dry Run] Would change banner for guild {guild.name}")

                return save_path
            except Exception:
                logger.exception("Error fetching or setting banner image")
                return None

        except Exception:
            logger.exception("Error changing server banner")
            return None

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

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="select")
    async def select_holiday(self, ctx: commands.Context):
        """
        Interactively select a holiday to view or manage.

        This command displays a numbered list of all configured holidays,
        prompts the user to select one by number, and then provides options
        to preview, apply, or show information about the selected holiday.
        """
        logger.debug(f"select_holiday command called by {ctx.author} in guild {ctx.guild.name} (ID: {ctx.guild.id})")
        # Use holiday_service instead of direct config access
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        logger.debug(f"Retrieved {len(holidays)} holidays for guild {ctx.guild.id}")

        # Log the structure of the first few holidays for debugging
        if holidays:
            sample_items = list(holidays.items())[:1]
            for name, details in sample_items:
                logger.debug(f"Holiday structure: {name} -> {details}")

        # Get sorted holidays for better display
        sorted_holidays = []
        try:
            from .holiday.holiday_calculator import get_sorted_holidays as calc_sorted_holidays
            holidays_list = calc_sorted_holidays(holidays)
            sorted_holidays = [(name, holidays[name], days) for name, days in holidays_list]
            logger.debug(f"Sorted {len(sorted_holidays)} holidays")
        except Exception as e:
            logger.error(f"Error sorting holidays: {e}")
            sorted_holidays = [(name, details, 0) for name, details in holidays.items()]
            logger.debug(f"Using fallback sorting with {len(sorted_holidays)} holidays")

        if not sorted_holidays:
            await ctx.send("No holidays are configured. Use `!seasonal holiday add` to add a holiday.")
            return

        # Format and send the list
        discord.Embed(
            title="Available Holidays",
            description="Select a holiday by number:",
            color=discord.Color.blue()
        )

        # Use numbered list for selection
        message_parts = ["**Available Holidays:**\n"]
        for i, (name, details, days) in enumerate(sorted_holidays, 1):
            # Use the display_name if available
            display_name = details.get("display_name", name)
            date = details.get("date", "Unknown date")
            emoji = "🔜" if days > 0 else "📅" if days == 0 else "✅"
            day_text = f"{days} days away" if days > 0 else "Today!" if days == 0 else f"{abs(days)} days ago"
            message_parts.append(f"`{i}.` {emoji} **{display_name}** ({date}) - {day_text}")

        # Split into chunks if needed (Discord has 2000 char limit)
        full_message = "\n".join(message_parts)
        if len(full_message) > 1900:  # Leave room for extra text
            message_parts = ["**Available Holidays:**\n"]
            for i, (name, details, days) in enumerate(sorted_holidays, 1):
                display_name = details.get("display_name", name)
                emoji = "🔜" if days > 0 else "📅" if days == 0 else "✅"
                message_parts.append(f"`{i}.` {emoji} **{display_name}**")
            full_message = "\n".join(message_parts)

        await ctx.send(full_message)

        # Wait for user's selection
        await ctx.send("Please enter the number of the holiday you want to select:")

        def check(m):
            # Check if message is from the author, in the same channel, and contains a valid number
            if m.author != ctx.author or m.channel != ctx.channel:
                return False

            try:
                num = int(m.content)
                return 1 <= num <= len(sorted_holidays)
            except ValueError:
                return False

        try:
            response = await self.bot.wait_for("message", check=check, timeout=30.0)

            # Get the selected holiday
            selection = int(response.content) - 1  # Convert to 0-indexed
            selected_name, selected_details, _ = sorted_holidays[selection]
            display_name = selected_details.get("display_name", selected_name)

            logger.debug(f"User selected holiday: {selected_name} (display_name: {display_name})")
            logger.debug(f"Holiday details: {selected_details}")

            # Create action menu
            menu_embed = discord.Embed(
                title=f"Holiday: {display_name}",
                description="Select an action:",
                color=discord.Color.green()
            )

            menu_embed.add_field(name="ℹ️ Info", value="View detailed information", inline=True)
            menu_embed.add_field(name="👁️ Preview", value="Preview how it will look", inline=True)
            menu_embed.add_field(name="✅ Apply", value="Apply this holiday now", inline=True)

            menu_message = await ctx.send(embed=menu_embed)

            # Add reaction options
            await menu_message.add_reaction("ℹ️")  # Info
            await menu_message.add_reaction("👁️")  # Preview
            await menu_message.add_reaction("✅")  # Apply

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == menu_message.id
                    and str(reaction.emoji) in ["ℹ️", "👁️", "✅"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=reaction_check
                )

                # Handle the reaction
                if str(reaction.emoji) == "ℹ️":  # Info
                    await self.show_holiday_info(ctx, selected_name, selected_details)
                elif str(reaction.emoji) == "👁️":  # Preview
                    await self.preview_holiday(ctx, selected_name)
                elif str(reaction.emoji) == "✅":  # Apply
                    await self.force_holiday(ctx, holiday_name=selected_name)

            except asyncio.TimeoutError:
                await menu_message.edit(content="Action selection timed out.")
                try:
                    await menu_message.clear_reactions()
                except discord.Forbidden:
                    pass

        except asyncio.TimeoutError:
            await ctx.send("Selection timed out.")

    @seasonal_announce.command(name="toggle")
    async def announce_toggle(self, ctx, setting: Optional[str] = None):
        """
        Enable or disable holiday announcements.

        This is an alias for the 'set' command.
        Use '!seasonal announce set' instead.

        Examples:

        !seasonal announce toggle enable
        !seasonal announce toggle disable
        !seasonal announce toggle

        """
        # Just forward to the set command
        await self.announce_set(ctx, setting)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="find")
    async def find_holidays(self, ctx: commands.Context, *, search_term: str):
        """
        Find holidays matching a search term.

        Args:
            ctx: The command context
            search_term: Text to search for in holiday names

        Examples:
            !seasonal find spring
            !seasonal find new year

        """
        if not search_term or len(search_term.strip()) < MIN_SEARCH_TERM_LENGTH:
            await ctx.send("Please provide a search term with at least 2 characters.")
            return

        # Use holiday_service instead of direct config access
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        if not holidays:
            await ctx.send("No holidays have been configured for this server.")
            return

        # Find all potential matches
        matches = find_holiday_matches(holidays, search_term, threshold=0.3)

        if not matches:
            await ctx.send(f"No holidays found matching '{search_term}'. Try a different search term.")
            return

        # Create an embed to show the results
        embed = discord.Embed(
            title=f"Holidays matching '{search_term}'",
            description=f"Found {len(matches)} matching holiday(s)",
            color=discord.Color.blue()
        )

        # Add each match to the embed
        for i, (name, details, score) in enumerate(matches, 1):
            confidence_percent = int(score * 100)
            date = details.get("date", "No date")
            display_name = details.get("display_name", name)

            # Special format for exact matches
            if score >= EXACT_MATCH_THRESHOLD:
                match_info = f"**Exact match!** - {date}"
            else:
                match_info = f"**{confidence_percent}% match** - {date}"

            # Create field for this holiday
            embed.add_field(
                name=f"{i}. {display_name}",
                value=f"{match_info}\nFull name: {name}",
                inline=False
            )

        # Add a footer with usage hint
        embed.set_footer(text="Use '!seasonal select' to interactively choose a holiday")

        await ctx.send(embed=embed)

        # For single exact matches or very high confidence matches, offer direct actions
        if len(matches) == 1 and matches[0][2] > EXACT_MATCH_THRESHOLD:
            name, details, _ = matches[0]
            display_name = details.get("display_name", name)

            action_msg = await ctx.send(
                f"Found exact match: **{display_name}**\n"
                f"What would you like to do with this holiday?\n"
                f"1️⃣ - Force apply the holiday now\n"
                f"2️⃣ - Preview the holiday\n"
                f"3️⃣ - Show holiday information"
            )

            # Add reaction options
            options = ["1️⃣", "2️⃣", "3️⃣"]
            for option in options:
                await action_msg.add_reaction(option)

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == action_msg.id
                    and str(reaction.emoji) in options
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )

                # Process the selected action
                emoji = str(reaction.emoji)
                if emoji == "1️⃣":
                    await ctx.send(f"Applying holiday: **{display_name}**...")
                    await self.force_holiday(ctx, holiday_name=name)
                elif emoji == "2️⃣":
                    await ctx.send(f"Previewing holiday: **{display_name}**...")
                    await self.dryrun_simulate(ctx, holiday_name=name)
                elif emoji == "3️⃣":
                    # Use the existing select_holiday logic to show detailed info
                    color_hex = details.get("color", "#000000")
                    try:
                        color = int(color_hex.replace("#", ""), 16)
                    except ValueError:
                        color = 0

                    info_embed = discord.Embed(
                        title=f"Holiday: {display_name}",
                        color=color
                    )

                    # Add fields for each property
                    for key, value in details.items():
                        # Skip complex nested objects like announcements
                        if key != "announcements" and not isinstance(value, dict):
                            info_embed.add_field(name=key, value=value, inline=False)

                    await ctx.send(embed=info_embed)

            except asyncio.TimeoutError:
                await ctx.send("Action selection timed out.")

    # New announcement command group
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.group(name="announce", aliases=["announcement", "announcements"])
    async def seasonal_announce(self, ctx):
        """
        Manually trigger holiday announcements.

        This command group allows you to manually trigger holiday announcements
        for a specific phase, with options to bypass date checks, preview the
        announcement, or use custom settings.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @seasonal_announce.command(name="channel")
    async def announce_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set or view the announcement channel.

        This sets where holiday announcements will be posted.
        If no channel is provided, displays the current channel.

        Examples:
        !seasonal announce channel #announcements
        !seasonal announce channel

        """
        if channel is None:
            # Display current channel
            current_channel_id = await self.config.guild(ctx.guild).announcement_config.get_raw("channel_id", default=None)
            if current_channel_id:
                current_channel = ctx.guild.get_channel(current_channel_id)
                if current_channel:
                    await ctx.send(f"The current announcement channel is {current_channel.mention}")
                else:
                    await ctx.send("The announcement channel is set but could not be found. It may have been deleted.")
            else:
                await ctx.send("No announcement channel has been set yet.")
            return

        # Set the channel
        success = await self.holiday_announcer.set_announcement_channel(ctx.guild.id, channel.id)
        if success:
            await ctx.send(f"Announcement channel set to {channel.mention}")
        else:
            await ctx.send("Failed to set announcement channel. Please try again.")

    @seasonal_announce.command(name="set")
    async def announce_set(self, ctx, setting: Optional[str] = None):
        """
        Set whether holiday announcements are enabled or disabled.

        Valid settings:
        - true, yes, on, enable, enabled (to enable announcements)
        - false, no, off, disable, disabled (to disable announcements)
        - status, show (to view current status)

        Examples:

        !seasonal announce set on
        !seasonal announce set off
        !seasonal announce set status

        """
        if setting is None or setting.lower() in ["status", "show"]:
            # Show current status
            is_enabled = await self.config.guild(ctx.guild).announcement_config.get_raw("enabled", default=False)
            status = "enabled" if is_enabled else "disabled"
            await ctx.send(f"Announcements are currently **{status}**.")
            return

        if setting.lower() in ["enable", "enabled", "on", "true", "yes"]:
            await self.holiday_announcer.set_announcement_enabled(ctx.guild.id, is_enabled=True)
            await ctx.send("✅ Holiday announcements have been **enabled**.")
        elif setting.lower() in ["disable", "disabled", "off", "false", "no"]:
            await self.holiday_announcer.set_announcement_enabled(ctx.guild.id, is_enabled=False)
            await ctx.send("❌ Holiday announcements have been **disabled**.")
        else:
            await ctx.send("Invalid setting. Please use options like 'enable', 'disable', or 'status'.")

    @seasonal_announce.command(name="before")
    async def announce_before(self, ctx, *, holiday_name: str):
        """
        Trigger the "before" phase announcement for a holiday.

        This announces an upcoming holiday (normally sent 7 days before).
        Use --force to bypass date eligibility checks.
        Use --preview to see the announcement without sending it.
        Use --channel to specify a custom channel.

        Examples:
        !seasonal announce before "Spring Festival"
        !seasonal announce before "New Year" --force
        !seasonal announce before "Kids Day" --preview

        """
        await self._handle_announcement(ctx, holiday_name, "before")

    @seasonal_announce.command(name="during")
    async def announce_during(self, ctx, *, holiday_name: str):
        """
        Trigger the "during" phase announcement for a holiday.

        This announces the holiday itself (normally sent on the day of).
        Use --force to bypass date eligibility checks.
        Use --preview to see the announcement without sending it.
        Use --channel to specify a custom channel.

        Examples:
        !seasonal announce during "Spring Festival"
        !seasonal announce during "New Year" --force
        !seasonal announce during "Kids Day" --preview

        """
        await self._handle_announcement(ctx, holiday_name, "during")

    @seasonal_announce.command(name="after")
    async def announce_after(self, ctx, *, holiday_name: str):
        """
        Trigger the "after" phase announcement for a holiday.

        This announces the end of a holiday (normally sent the day after).
        Use --force to bypass date eligibility checks.
        Use --preview to see the announcement without sending it.
        Use --channel to specify a custom channel.

        Examples:
        !seasonal announce after "Spring Festival"
        !seasonal announce after "New Year" --force
        !seasonal announce after "Kids Day" --preview

        """
        await self._handle_announcement(ctx, holiday_name, "after")

    async def _handle_announcement(self, ctx, holiday_name: str, phase: str):
        """
        Handle the announcement command flow for all phases.

        This helper method processes the announcement command options,
        validates the holiday, and calls the appropriate service methods.
        """
        # Parse command options
        options = holiday_name.split("--")
        holiday_name = options[0].strip()

        # Check for force flag
        force = any("force" in opt.lower().strip() for opt in options[1:]) if len(options) > 1 else False

        # Check for preview flag
        preview = any("preview" in opt.lower().strip() for opt in options[1:]) if len(options) > 1 else False

        # Check for channel option
        channel_id = None
        for opt in options[1:]:
            if "channel" in opt.lower().strip():
                parts = opt.split()
                if len(parts) > 1:
                    try:
                        # Handle channel mentions or raw IDs
                        channel_str = parts[-1].strip()
                        if channel_str.startswith("<#") and channel_str.endswith(">"):
                            channel_id = int(channel_str[2:-1])
                        else:
                            channel_id = int(channel_str)
                    except (ValueError, IndexError):
                        await ctx.send("Invalid channel format. Use a channel mention or ID.")
                        return

        # Verify permissions for force flag
        if force and not ctx.author.guild_permissions.administrator:
            await ctx.send("⚠️ Only administrators can use the --force flag.")
            return

        # Get holiday details
        holidays = await self.holiday_service.get_holidays(ctx.guild)
        original_name, holiday_details, match_score = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"No holiday found matching '{holiday_name}'.")
            return

        # For partial matches below a certain confidence, confirm with the user
        if match_score < MATCH_CONFIDENCE_THRESHOLD:
            confirm_msg = await ctx.send(
                f"Did you mean '{original_name}' ({holiday_details.get('date', 'unknown date')})? "
                f"React with ✅ to confirm or ❌ to cancel."
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == confirm_msg.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=30.0, check=reaction_check
                )
                if str(reaction.emoji) == "❌":
                    await ctx.send("Announcement cancelled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Announcement cancelled.")
                return

        # Create Holiday object from the details
        try:
            # Parse the date string ("MM-DD") into month and day integers
            date_parts = holiday_details["date"].split("-")
            month = int(date_parts[0])
            day = int(date_parts[1])

            # Create the Holiday object
            from .holiday.holiday_data import Holiday

            holiday_obj = Holiday(
                name=original_name,
                month=month,
                day=day,
                color=holiday_details.get("color", "#FFFFFF"),
                image=holiday_details.get("image", None),
                banner_url=holiday_details.get("banner", None)
            )
            logger.debug(f"Successfully created Holiday object: {holiday_obj}")
        except Exception as e:
            logger.exception("Failed to create Holiday object")
            await ctx.send(f"Error creating Holiday object: {e}")
            return

        # Show announcement details before proceeding
        status_embed = discord.Embed(
            title=f"Announcement Details: {original_name}",
            color=discord.Color.blue()
        )

        # Add holiday information
        status_embed.add_field(
            name="Holiday",
            value=f"**{original_name}**\nDate: {holiday_details['date']}",
            inline=False
        )

        # Add announcement phase
        phase_descriptions = {
            "before": "Upcoming holiday announcement (7 days before)",
            "during": "Holiday start announcement (day of)",
            "after": "Holiday end announcement (day after)"
        }
        status_embed.add_field(
            name="Phase",
            value=phase_descriptions.get(phase, phase),
            inline=False
        )

        # Add options used
        options_text = []
        if force:
            options_text.append("⚠️ **Force mode**: Date checks will be bypassed")
        if preview:
            options_text.append("🔍 **Preview mode**: Announcement will not be sent")
        if channel_id:
            channel = ctx.guild.get_channel(channel_id)
            channel_name = channel.mention if channel else f"Unknown ({channel_id})"
            options_text.append(f"📢 **Custom channel**: {channel_name}")

        if options_text:
            status_embed.add_field(
                name="Options",
                value="\n".join(options_text),
                inline=False
            )

        await ctx.send(embed=status_embed)

        # Confirm before proceeding
        confirm_text = "Send this announcement?" if not preview else "Generate this preview?"
        if force:
            confirm_text = f"⚠️ {confirm_text} (FORCE MODE)"

        confirm_msg = await ctx.send(f"{confirm_text} React with ✅ to confirm or ❌ to cancel.")
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def reaction_check(reaction, user):
            return (
                user == ctx.author
                and reaction.message.id == confirm_msg.id
                and str(reaction.emoji) in ["✅", "❌"]
            )

        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add", timeout=30.0, check=reaction_check
            )
            if str(reaction.emoji) == "❌":
                await ctx.send("Announcement cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Confirmation timed out. Announcement cancelled.")
            return

        # Call the service method to trigger the announcement
        success, message, status_reason = await self.holiday_announcer.trigger_announcement(
            holiday=holiday_obj,
            phase=phase,
            guild_id=ctx.guild.id,
            force=force,
            channel_id=channel_id,
            preview_only=preview,
            user_to_preview=ctx.author if preview else None
        )

        # Create a detailed response embed
        result_embed = discord.Embed(
            title="Announcement Result",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )

        if status_reason:
            result_embed.add_field(name="Details", value=status_reason, inline=False)

        await ctx.send(embed=result_embed)

    @tasks.loop(hours=1)
    async def check_holidays(self, guild, *, force: bool = False):
        """
        Check for upcoming holidays and handle announcements.

        This method runs every hour to check for holidays that need to be announced
        or applied. It uses the holidays from holidays.json as the single source of truth.

        Args:
            guild: The guild to check holidays for
            force: Whether to force holiday checks regardless of timing rules

        """
        try:
            # Skip processing if dry run is enabled
            dry_run_mode = await self.config.guild(guild).dryrun.get_raw("enabled", default=False)
            if dry_run_mode and not force:
                logger.debug(f"Skipping holiday check for {guild.name} due to dry run mode")
                return

            logger.debug(f"Checking holidays for guild {guild.name}")

            # Get holidays from the HolidayService which now uses holidays.json
            holidays = await self.holiday_service.get_holidays(guild)

            if not holidays:
                logger.debug(f"No holidays found for guild {guild.name}")
                return

            # Get the current date
            DateUtil.now()

            # Get the sorted holidays and find the upcoming one
            sorted_holidays = calc_sorted_holidays(holidays)
            upcoming_holiday, days_until = calc_upcoming_holiday(holidays)

            if not upcoming_holiday:
                logger.debug("No upcoming holidays found")
                return

            # Check for announcements that need to be sent (before, during, after phases)
            for holiday_name, _days in sorted_holidays:
                # Skip if no holiday name
                if not holiday_name:
                    continue

                # Get holiday details
                holiday_details = holidays.get(holiday_name)
                if not holiday_details:
                    continue

                # Create a holiday object for the service
                try:
                    from .holiday.holiday_data import Holiday

                    # Extract details
                    holiday_date = holiday_details.get("date")
                    if not holiday_date:
                        logger.warning(f"Holiday {holiday_name} has no date")
                        continue

                    # Parse date
                    date_parts = holiday_date.split("-")
                    if len(date_parts) != 2:
                        logger.warning(f"Invalid date format for {holiday_name}: {holiday_date}")
                        continue

                    month = int(date_parts[0])
                    day = int(date_parts[1])

                    # Create Holiday object
                    holiday_obj = Holiday(
                        name=holiday_name,
                        color=holiday_details.get("color", "#FFFFFF"),
                        image=holiday_details.get("image", ""),
                        month=month,
                        day=day
                    )

                    # Calculate days until
                    days_until = compute_days_until_holiday(holiday_date)

                    # Determine phase
                    DAYS_BEFORE_THRESHOLD = 7

                    # Check for "before" phase announcements
                    if 0 < days_until <= DAYS_BEFORE_THRESHOLD:
                        logger.debug(f"Holiday {holiday_name} is coming up in {days_until} days.")

                        # Send "before" announcement
                        if force or days_until == DAYS_BEFORE_THRESHOLD:
                            success, message, reason = await self.holiday_announcer.trigger_announcement(
                                holiday=holiday_obj,
                                phase="before",
                                guild_id=guild.id,
                                force=force
                            )
                            logger.info(f"Before announcement for {holiday_name}: {message}")

                    # Check for "during" phase
                    elif days_until == 0:
                        logger.debug(f"Holiday {holiday_name} is today!")

                        # Send "during" announcement
                        success, message, reason = await self.holiday_announcer.trigger_announcement(
                            holiday=holiday_obj,
                            phase="during",
                            guild_id=guild.id,
                            force=force
                        )
                        logger.info(f"During announcement for {holiday_name}: {message}")

                        # Apply holiday role
                        success, message = await self.holiday_service.apply_holiday_role(guild, holiday_name)
                        logger.info(f"Applying holiday role for {holiday_name}: {message}")

                        # Set banner if available
                        if "banner" in holiday_details and not dry_run_mode:
                            logger.debug(f"Setting banner for {holiday_name}")
                            banner_path = Path(__file__).parent / holiday_details["banner"]

                            if banner_path.exists():
                                try:
                                    from utilities.image_utils import LocalImageHandler

                                    image_handler = LocalImageHandler(str(banner_path))
                                    banner_bytes = await image_handler.fetch_image_data()

                                    await guild.edit(banner=banner_bytes)
                                    logger.info(f"Set holiday banner for {holiday_name}")
                                except Exception:
                                    logger.exception(f"Failed to set banner for {holiday_name}")

                    # Check for "after" phase
                    elif days_until == -1:
                        logger.debug(f"Holiday {holiday_name} was yesterday.")

                        # Send "after" announcement
                        success, message, reason = await self.holiday_announcer.trigger_announcement(
                            holiday=holiday_obj,
                            phase="after",
                            guild_id=guild.id,
                            force=force
                        )
                        logger.info(f"After announcement for {holiday_name}: {message}")

                        # Remove holiday role
                        await self.holiday_service.remove_all_except_current_holiday_role(guild, "")
                        logger.info(f"Removed holiday role for {holiday_name}")

                except Exception:
                    logger.exception(f"Error processing holiday {holiday_name}")
                    continue

        except Exception:
            logger.exception(f"Error checking holidays for guild {guild.name}")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="checkholidays")
    async def check_holidays_command(self, ctx):
        """
        Manually check for holidays right now.

        This command runs the holiday checking logic immediately
        to verify holiday announcements and role assignments.
        """
        await ctx.send("⏳ Manually checking holidays... Please wait.")

        try:
            # Call the check_holidays method directly with the current guild
            await self.check_holidays(ctx.guild, force=True)

            # Get today's date for context
            current_date = DateUtil.now()
            date_formatted = current_date.strftime("%B %d, %Y")

            # Get holidays from the service
            holidays = await self.holiday_service.get_holidays(ctx.guild)

            # Get the sorted holidays and find the upcoming one
            upcoming_holiday, days_until = calc_upcoming_holiday(holidays)

            # Create an embed with the results
            embed = discord.Embed(
                title="Holiday Check Results",
                description=f"Check completed on {date_formatted}",
                color=discord.Color.green()
            )

            if upcoming_holiday:
                embed.add_field(
                    name="Next Holiday",
                    value=f"**{upcoming_holiday}** in {days_until} days",
                    inline=False
                )
            else:
                embed.add_field(
                    name="No Upcoming Holidays",
                    value="No holidays found in the configuration.",
                    inline=False
                )

            # Add announcement status
            announcement_config = await self.config.guild(ctx.guild).announcement_config()
            is_enabled = announcement_config.get("enabled", False)
            channel_id = announcement_config.get("channel_id")

            if is_enabled and channel_id:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    embed.add_field(
                        name="Announcements",
                        value=f"✅ Enabled in {channel.mention}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Announcements",
                        value=f"⚠️ Enabled but channel not found (ID: {channel_id})",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Announcements",
                    value="❌ Disabled or not configured",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.exception("Error in manual holiday check")
            await ctx.send(f"⚠️ Error during holiday check: {e}")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="start")
    async def start_holiday(self, ctx: commands.Context, *holiday_name_parts: str) -> None:
        """
        Start a holiday in the appropriate phase based on the current date.
        This will set up roles, banners, and send the correct phase announcement.

        Examples:

        !seasonal start spring      (matches Spring Blossom Festival)
        !seasonal start new year    (matches New Year's Celebration)

        """
        holiday_name = " ".join(holiday_name_parts).lower()
        guild = ctx.guild

        # Check if dry run mode is enabled
        dry_run_mode = await self.config.guild(guild).dryrun.get_raw("enabled", default=False)
        logger.debug(f"Processing start command for '{holiday_name}' with dry run mode set to {dry_run_mode}.")

        # Get holidays from service
        holidays = await self.holiday_service.get_holidays(ctx.guild)

        # Validate that the holiday exists
        success, validate_message = await self.holiday_service.validate_holiday_exists(holidays, holiday_name)
        if not success:
            # If validation fails, send the error message
            await ctx.send(validate_message or f"Holiday '{holiday_name}' not found.")
            return

        # Get the matched holiday details
        original_name, holiday_details, _ = find_holiday(holidays, holiday_name)

        # Create a Holiday object for the service methods
        from .holiday.holiday_data import Holiday

        try:
            # Get holiday date
            holiday_date = holiday_details.get("date")
            if not holiday_date:
                await ctx.send(f"Error: No date found for holiday '{original_name}'")
                return

            # Use the calculator to determine days until
            days_until = compute_days_until_holiday(holiday_date)
            logger.debug(f"Days until {original_name}: {days_until}")

            # Determine the phase - this is a policy decision that could be moved to the service
            # Use constant instead of magic number
            DAYS_BEFORE_ANNOUNCEMENT = 7
            if days_until > DAYS_BEFORE_ANNOUNCEMENT:
                await ctx.send(f"Holiday {original_name} is more than {DAYS_BEFORE_ANNOUNCEMENT} days away ({days_until} days). Cannot start it yet.")
                return

            phase = "before" if days_until > 0 else "during"
            logger.debug(f"Starting holiday {original_name} in {phase} phase")

            # Create the Holiday object that the services expect
            date_parts = holiday_date.split("-")
            month = int(date_parts[0])
            day = int(date_parts[1])

            holiday_obj = Holiday(
                name=original_name,
                color=holiday_details.get("color", "#FFFFFF"),
                image=holiday_details.get("image", ""),
                month=month,
                day=day
            )

            # Handle the "during" phase with existing force_holiday command
            if phase == "during":
                await ctx.send(f"Starting holiday '{original_name}' in 'during' phase...")
                await self.force_holiday(ctx, holiday_name=original_name)
                return

            # For "before" phase:
            # 1. First remove all existing holiday roles except this one
            logger.debug(f"Removing all holiday roles except {original_name}")
            success, message = await self.holiday_service.remove_all_except_current_holiday_role(guild, original_name)
            if not success:
                logger.error(f"Failed to remove other holiday roles: {message}")
                # Continue anyway - this isn't a critical failure
            else:
                logger.debug(message)

            # 2. Save current banner if needed
            banner_management = await self.config.guild(guild).banner_management()
            if not banner_management.get("original_banner_path"):
                logger.debug("Saving current guild banner")
                asset_path = Path(__file__).parent / f"assets/guild-banner-non-holiday-{guild.id}.png"
                saved_path = await fetch_and_save_guild_banner(guild, asset_path)
                if saved_path:
                    # Convert Path to string to ensure it's JSON serializable
                    saved_path_str = str(saved_path)
                    await self.config.guild(guild).banner_management.set_raw("original_banner_path", value=saved_path_str)
                    logger.info(f"Original banner saved to {saved_path_str}.")
                else:
                    logger.error("Failed to save the original banner.")
                    await ctx.send("Failed to save the original banner. Please check the logs for more details.")

            # 3. Apply holiday role
            logger.debug(f"Applying holiday role for {original_name}")
            success, message = await self.holiday_service.apply_holiday_role(guild, original_name)
            if not success:
                await ctx.send(f"Error applying holiday role: {message}")
                return

            await ctx.send(message)

            # Check if there are any opt-in users
            opt_in_users = await self.config.guild(guild).opt_in_users()
            if not opt_in_users:
                logger.warning("No users have opted in, so role was created but not assigned to anyone")
                await ctx.send("⚠️ **No users have opted in!** The role was created but not assigned to anyone. "
                              "Use `!seasonal member add @user` to add users or `!seasonal member config everyone` "
                              "to add everyone in the server.")
            else:
                logger.debug(f"Role assigned to {len(opt_in_users)} users who have opted in")

            # 4. Set the holiday banner for "before" phase if one exists
            if "banner" in holiday_details:
                logger.debug(f"Setting banner for {original_name} using {holiday_details['banner']}")
                banner_path = Path(__file__).parent / holiday_details["banner"]

                if banner_path.exists():
                    try:
                        # Use image_utils for better image handling
                        from utilities.image_utils import LocalImageHandler

                        image_handler = LocalImageHandler(str(banner_path))
                        banner_bytes = await image_handler.fetch_image_data()

                        if not dry_run_mode:
                            await guild.edit(banner=banner_bytes)
                            logger.info(f"Set holiday banner for {original_name}")
                            await ctx.send(f"Set guild banner for {original_name}")
                        else:
                            logger.info(f"[Dry Run] Would set banner for {original_name}")
                            await ctx.send(f"[Dry Run] Would set banner for {original_name}")
                    except Exception as e:
                        logger.exception("Failed to set banner")
                        await ctx.send(f"Failed to set guild banner: {e}")
                else:
                    logger.warning(f"Banner file not found at {banner_path}")
            else:
                logger.debug(f"No banner specified for {original_name}")

            # 5. Send the announcement only if it hasn't been sent yet
            logger.debug(f"Checking if {original_name} announcement for '{phase}' phase has already been sent")
            last_announcement = await self.holiday_announcer.get_last_announcement(guild.id, original_name, phase)

            if last_announcement:
                logger.info(f"Announcement for {original_name} ({phase} phase) already sent on {last_announcement}")
                await ctx.send(f"Holiday '{original_name}' started successfully in '{phase}' phase. Announcement was already sent on {last_announcement}.")
            else:
                logger.debug(f"Triggering 'before' announcement for {original_name}")
                success, message, status_reason = await self.holiday_announcer.trigger_announcement(
                    holiday=holiday_obj,
                    phase="before",
                    guild_id=guild.id,
                    force=True  # Force the announcement even if it would normally be prevented
                )

                logger.debug(f"Announcement result: success={success}, message={message}, reason={status_reason}")

                if success:
                    await ctx.send(f"Holiday '{original_name}' started successfully in 'before' phase ({days_until} days until holiday)!")
                else:
                    await ctx.send(f"Holiday role and banner applied but announcement failed: {message}")

        except Exception as e:
            logger.exception("Error starting holiday")
            await ctx.send(f"An error occurred while starting the holiday: {e}")

    @seasonal.command(name="banner")
    async def change_server_banner_command(self, ctx, url: str | None = None):
        """
        Change the server banner using either a URL or an uploaded/pasted image.

        Examples:

        - Upload/paste: !seasonal banner  (attach or paste an image with the command)
        - URL: !seasonal banner https://example.com/banner.png

        """
        # Check if guild has banner feature
        if "BANNER" not in ctx.guild.features:
            await ctx.send("This server does not have the banner feature. You need level 2 boost status to use banners.")
            return

        # Check for direct attachment or pasted image
        if not url and ctx.message.attachments:
            # Use the first attachment as the source
            url = ctx.message.attachments[0].url
            logger.debug(f"Using attachment URL: {url}")

        # Check for message reference (reply) with attachment
        if not url and ctx.message.reference:
            referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if referenced_message and referenced_message.attachments:
                url = referenced_message.attachments[0].url
                logger.debug(f"Using referenced message attachment URL: {url}")

        # If we still don't have a URL, prompt the user
        if not url:
            await ctx.send("Please provide a banner URL, upload an image, or paste an image along with the command.")
            return

        # Using the utility method to handle banner change
        save_path = await self.change_server_banner(ctx.guild, url)

        if save_path:
            # Ensure path is a string before storing in config
            save_path_str = str(save_path)
            logger.debug(f"Saving banner path to config: {save_path_str}")
            await self.config.guild(ctx.guild).banner_management.set_raw("original_banner_path", value=save_path_str)
            await ctx.send(f"Server banner changed successfully and original banner saved to {save_path_str}")
        else:
            await ctx.send("Failed to change the server banner. Make sure the URL is valid and the image meets Discord's requirements.")

    async def change_server_banner(self, guild, url):
        """
        Change the server banner and save the original banner.

        Args:
            guild: The guild to change the banner for
            url: The URL or path to the new banner image

        Returns:
            str: The path where the original banner was saved, or None if failed

        """
        if "BANNER" not in guild.features:
            logger.warning(f"Guild {guild.name} does not have the banner feature.")
            return None

        try:
            # Save original banner first
            from utilities.discord_utils import fetch_and_save_guild_banner

            asset_path = Path(__file__).parent / f"assets/guild-banner-non-holiday-{guild.id}.png"
            save_path = await fetch_and_save_guild_banner(guild, asset_path)

            if not save_path:
                logger.warning(f"Failed to save original banner for guild {guild.name}")
                return None

            # Handle the banner image using image_utils
            from utilities.image_utils import get_image_handler

            # Check if the URL is actually a local path
            if not url.startswith(("http://", "https://")):
                # Treat as local path
                image_path = Path(url)
                if not image_path.exists():
                    logger.error(f"Local image file not found: {url}")
                    return None

            # Get the appropriate image handler and fetch the image data
            try:
                image_handler = get_image_handler(url)
                banner_bytes = await image_handler.fetch_image_data()

                # Update the guild's banner
                dry_run_mode = await self.config.guild(guild).dryrun.get_raw("enabled", default=False)
                if not dry_run_mode:
                    await guild.edit(banner=banner_bytes)
                    logger.info(f"Changed banner for guild {guild.name}")
                else:
                    logger.info(f"[Dry Run] Would change banner for guild {guild.name}")

                return save_path
            except Exception:
                logger.exception("Error fetching or setting banner image")
                return None

        except Exception:
            logger.exception("Error changing server banner")
            return None
