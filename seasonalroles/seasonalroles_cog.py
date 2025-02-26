from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import discord

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
from .holiday_announcer import HolidayAnnouncer
from .holiday_management import HolidayData, HolidayService
from .role.role_namer import generate_role_name
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

# Constants for holiday announcement timing
DAYS_BEFORE_ANNOUNCEMENT = 7  # Number of days before a holiday to announce
SAME_DAY_THRESHOLD = 0  # Threshold for same-day checks
NEXT_DAY_THRESHOLD = 1  # Threshold for next-day checks
COPYWRITING_CHECK_DAYS = 21  # Check for missing copy 3 weeks in advance

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
            "announcement_config": {
                "enabled": False,
                "channel_id": None,
                "mention_type": None,  # can be null, "everyone", "here", "role"
                "role_id": None,       # only used if mention_type is "role"
                "templates": {},       # Custom templates by holiday name and phase
                "last_announcements": {} # Tracks when the last announcement was sent for each holiday/phase
            },
        }
        self.config.register_guild(**default_guild)
        self.holiday_service = HolidayService(self.config)
        self.role_manager = RoleManager(self.config)
        self.holiday_announcer = HolidayAnnouncer(self.bot, self.config)

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
            logger.exception("Error in dryrun_toggle")
            await ctx.send("An error occurred while toggling dry run mode.")

    @seasonal_dryrun.command(name="role")
    async def dryrun_role(self, ctx, *, holiday_name: str):
        """Preview what role would be created/updated for a specific holiday."""
        # Ensure dry run is enabled
        if not await self._ensure_dryrun_enabled(ctx):
            return

        # Get holiday details and show role preview
        holidays = await self.config.guild(ctx.guild).holidays()
        original_name, holiday_details = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
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
        holidays = await self.config.guild(ctx.guild).holidays()
        original_name, holiday_details = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        from .holiday.holiday_data import Holiday
        holiday_obj = Holiday(
            name=original_name,
            color=holiday_details.get("color", "#FFFFFF"),
            image=holiday_details.get("image", ""),
            date=holiday_details["date"]
        )

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
        holidays = await self.config.guild(ctx.guild).holidays()
        original_name, holiday_details = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        from .holiday.holiday_data import Holiday
        holiday_obj = Holiday(
            name=original_name,
            color=holiday_details.get("color", "#FFFFFF"),
            image=holiday_details.get("image", ""),
            date=holiday_details["date"]
        )

        # Preview the announcement for the specific phase
        await ctx.send(f"**Previewing {phase} announcement for {original_name}:**")

        # Call the preview method with appropriate parameters
        success, message = await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
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
        holidays = await self.config.guild(ctx.guild).holidays()
        original_name, holiday_details = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
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
    async def dryrun_simulate(self, ctx, *, holiday_name: str):
        """
        Simulate the entire lifecycle of a holiday without making actual changes.

        This command will show all actions that would be taken for a holiday:
        1. Seven days before the holiday (role creation, announcement)
        2. On the day of the holiday (banner change, announcement)
        3. The day after the holiday (role removal, banner reset, announcement)

        Parameters
        ----------
        ctx : discord.Context
            The invocation context.
        holiday_name : str
            The name of the holiday to simulate.

        """
        if not await self._ensure_dryrun_enabled(ctx):
            return

        # Find the holiday
        holidays = await self.config.guild(ctx.guild).holidays()
        original_name, holiday_details = find_holiday(holidays, holiday_name)

        if not original_name:
            await ctx.send(f"Holiday '{holiday_name}' not found.")
            return

        # Create Holiday object
        from .holiday.holiday_data import Holiday
        holiday_obj = Holiday(
            name=original_name,
            color=holiday_details.get("color", "#FFFFFF"),
            image=holiday_details.get("image", ""),
            date=holiday_details["date"]
        )

        await ctx.send(f"## **SIMULATING HOLIDAY LIFECYCLE: {original_name}**")
        await ctx.send("This will show what would happen at each phase of the holiday.")

        # Phase 1: 7 days before
        await ctx.send("\n## **PHASE 1: 7 DAYS BEFORE THE HOLIDAY**")
        await ctx.send("The following would happen 7 days before the holiday:")

        # Show role creation
        await ctx.send("**Actions:**")
        role_name = generate_role_name(original_name, holiday_details["date"])
        role_color = holiday_details.get("color", "#FFFFFF")
        await ctx.send(f"- Holiday role would be created: `{role_name}` with color `{role_color}`")

        estimated_members = len([m for m in ctx.guild.members if not m.bot])
        await ctx.send(f"- Approximately {estimated_members} members would receive this role")

        # Show announcement
        await ctx.send("**Announcement that would be sent 7 days before the holiday:**")

        await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="before",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=DAYS_BEFORE_ANNOUNCEMENT,
            to_channel=True,
            ctx=ctx
        )

        # Phase 2: Day of holiday
        await ctx.send("\n## **PHASE 2: DAY OF THE HOLIDAY**")
        await ctx.send("The following would happen on the day of the holiday:")

        # Show banner change
        await ctx.send("**Actions:**")
        if "banner" in holiday_details:
            banner_path = holiday_details["banner"]
            await ctx.send(f"**Banner would change to:** `{banner_path}`")

        # Show announcement
        await ctx.send("**Announcement that would be sent on the holiday:**")

        await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="during",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=0,
            to_channel=True,
            ctx=ctx
        )

        # Phase 3: Day after
        await ctx.send("\n## **PHASE 3: DAY AFTER THE HOLIDAY**")
        await ctx.send("The following would happen the day after the holiday:")

        # Show role/banner cleanup
        await ctx.send("**Actions:**")
        await ctx.send("- Holiday role would be removed from all members")
        await ctx.send("- Server banner would be restored to original (if changed)")

        # Show announcement
        await ctx.send("**Announcement that would be sent after the holiday:**")

        await self.holiday_announcer.preview_holiday_announcement(
            holiday=holiday_obj,
            phase="after",
            user=ctx.author,
            guild_id=ctx.guild.id,
            days_until=-1,
            to_channel=True,
            ctx=ctx
        )

        # Final summary
        await ctx.send("\n## **SIMULATION COMPLETE**")
        await ctx.send("This simulation shows what would happen during an actual holiday without making real changes.")
