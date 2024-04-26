import os
from typing import Any, Dict, Optional, Tuple


from datetime import datetime, timedelta
import re
import base64
import aiohttp
import discord
from discord.ext import tasks
from redbot.core.bot import Red
from redbot.core import Config, commands, app_commands

import logging

from .holiday_management import HolidayService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))
image_path = os.path.abspath(os.path.join("assets", "your-image.png"))
logger.debug(f"Absolute image path: {image_path}")

# Continue porting role comands to role_mangement. 
# Adding roles to members needs to be tested.
# Finally, refactor the image handling for role_icons and banners
# The goal is the bot to handle kid's day on 5-5
class SeasonalRoles(commands.Cog):
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
                "Kids Day": {"date": "05-05", "color": "#68855A", "banner": "assets/kids-day-banner-01.png"},
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
        }
        self.config.register_guild(**default_guild)
        self.holiday_service = HolidayService(self.config)

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
            await ctx.send(f"{member.display_name} has been added to the {self.qualified_name}.")
        else:
            await ctx.send(f"{member.display_name} is already in the {self.qualified_name}.")

    @member.command(name="remove")
    async def member_remove(self, ctx, member: Optional[discord.Member], *, all_members: str = None):
        """Removes a member or all members from the opt-in list."""
        if all_members and all_members.lower() in {"everyone", "all", "everybody"}:
            await self.config.guild(ctx.guild).opt_in_users.set([])
            await ctx.send("All members have been removed from the opt-in list.")
        elif member:
            opt_in_users = await self.config.guild(ctx.guild).opt_in_users()
            if member.id in opt_in_users:
                opt_in_users.remove(member.id)
                await self.config.guild(ctx.guild).opt_in_users.set(opt_in_users)
                await ctx.send(f"{member.display_name} has been removed from the {self.qualified_name}.")
            else:
                await ctx.send(f"{member.display_name} is not in the {self.qualified_name}.")
        else:
            await ctx.send("Invalid command usage. Please specify a member or use 'everyone' to remove all.")

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
        if not name:
            await ctx.send("Please provide a name for the holiday.")
            return False

        if not color or not color.startswith("#") or len(color) != 7:
            await ctx.send("Please provide a valid hex color code.")
            return False

        # Add check for if format of date is weird
        if not date or not re.match(r"\d{2}-\d{2}", date):
            await ctx.send("Please provide a valid date.")
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
        image: Optional[str] = None,
        banner_url: Optional[str] = None
    ) -> None:
        """Add a new holiday."""
        valid = await self.validate_holiday(ctx, name, date, color)
        if not valid:
            return

        success, message = await self.holiday_service.add_holiday(ctx.guild, name, date, color, image, banner_url)
        await ctx.send(message)

        if success:
            await self.check_holidays(ctx, ctx.guild, date)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @holiday.command(name="edit")
    async def edit_holiday_command(self, ctx, name: str, date: str, color: str, image: Optional[str] = None, banner_url: Optional[str] = None):
        """Edit an existing holiday's details."""
        valid = await self.validate_holiday(ctx, name, date, color)
        if not valid:
            return

        success, message = await self.holiday_service.edit_holiday(ctx.guild, name, date, color, image, banner_url)
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
            sorted_holidays, upcoming_holiday, days_until = await self.holiday_service.get_sorted_holidays(ctx.guild)
            if not sorted_holidays:
                await ctx.send("No holidays have been configured.")
                return

            embeds = []
            for name, _ in sorted_holidays:
                details = await self.config.guild(ctx.guild).holidays.get_raw(name)
                color = int(details["color"].replace("#", ""), 16)
                description = details["date"]
                if name == upcoming_holiday:
                    description += " - Upcoming in " + str(days_until[name]) + " days"
                elif days_until[name] <= 0:
                    description += " - Passed " + str(-days_until[name]) + " days ago"
                embed = discord.Embed(description=description, color=color)
                embed.set_author(name=name)
                embeds.append(embed)

            for embed in embeds:
                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send("An error occurred while listing holidays. Please try again later.")
            logger.error(f"Error listing holidays: {e}")

    async def add_holiday_role(
        self,
        ctx: commands.Context,
        name: str,
        date: str,
        color: str,
        image: Optional[str] = None,
    ) -> discord.Role:
        valid = await self.validate_holiday(ctx, name, date, color)
        if not valid:
            return None
        existing_role = discord.utils.get(ctx.guild.roles, name=name)
        if not existing_role:
            role_args = {"name": name, "color": discord.Color(int(color[1:], 16))}

        if image and "ROLE_ICONS" in ctx.guild.features:
            script_dir = os.path.dirname(__file__)  # Directory of the current script
            image_path = os.path.join(script_dir, image)
            logger.debug(f"Checking image path: {image_path}")
            if os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as img_file:
                        img_data = img_file.read()
                        img_b64 = base64.b64encode(img_data).decode("utf-8")
                        role_args["display_icon"] = img_data
                        logger.debug(
                            f"Image data for {name} role successfully encoded."
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to process the image data for {name} role: {e}"
                    )
                    await ctx.send(
                        "An error occurred while processing the holiday role image."
                    )
                    return None
            else:
                logger.error(f"Image file not found at path: {image_path}")
                await ctx.send("Image file not found.")
                return None

        try:
            # Creating the role
            role = await ctx.guild.create_role(**role_args)
            logger.debug(f"Created role {role.name} with icon in {ctx.guild.name}")
            await self.set_seasonal_role_to_top(ctx.guild, role)
            logger.debug(f"Set the seasonal role '{role.name}' to the top.")
            await ctx.send(f"Holiday role '{name}' with icon added successfully!")
            return role
        except discord.Forbidden:
            logger.error("Lack of permissions to create or modify roles.")
            await ctx.send("I don't have permissions to create or modify roles.")
        except discord.NotFound:
            logger.error(
                "Resource not found. The role or user might have been deleted."
            )
            await ctx.send("Failed to find the specified resource.")
        except discord.HTTPException as e:
            logger.error(f"HTTP error occurred: {e}")
            await ctx.send("An error occurred due to a server-side issue.")
        except TypeError as e:
            logger.error(f"TypeError occurred: {e}")
            await ctx.send(
                "An invalid type was provided for creating or modifying a role."
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            await ctx.send("An unexpected error occurred.")

    async def set_seasonal_role_to_top(
        self, guild: discord.Guild, role: discord.Role
    ) -> None:
        bot_member = guild.me  # The bot's member object in the guild
        bot_roles = sorted(
            bot_member.roles, key=lambda x: x.position, reverse=True
        )  # Sort roles by position
        highest_bot_role = bot_roles[0]  # The highest role the bot has

        if highest_bot_role.position > 1:
            # Set the seasonal role position to one less than the bot's highest role
            new_position = highest_bot_role.position - 1
            positions = {role: new_position}
            try:
                await guild.edit_role_positions(positions)
                logger.debug(
                    f"Seasonal role '{role.name}' set to position {new_position}."
                )
            except Exception as e:
                logger.error(f"Error setting position of seasonal role: {e}")
        else:
            logger.warning(
                "Bot does not have sufficient role hierarchy to set the seasonal role position."
            )

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
                    f"Dry run mode {mode_str}. Actions will now make real changes."
                )
            else:
                await ctx.send(
                    f"Dry run mode {mode_str}. Any actions will be simulated, and no real changes will be made."
                )
        except Exception as e:
            logger.error(f"Error in toggle_dry_run: {e}")

    #TODO TURN INTO SLASH COMMAND
    async def toggle_seasonal_role(self, ctx: commands.Context) -> None:
        """Toggle opting in/out from the seasonal role."""

        opt_out_users = await self.config.guild(ctx.guild).opt_out_users()

        if ctx.author.id in opt_out_users:
            opt_out_users.remove(ctx.author.id)
            # Check if there's a current holiday and if the member has its role.
            current_date = datetime.now().date()
            holidays = await self.config.guild(ctx.guild).holidays()
            for holiday, details in holidays.items():
                holiday_date = (
                    datetime.strptime(details["date"], "%m-%d")
                    .date()
                    .replace(year=current_date.year)
                )
                if current_date == holiday_date:
                    role = discord.utils.get(ctx.guild.roles, name=holiday)
                    if role and role in ctx.author.roles:
                        await ctx.author.add_roles(role)
            await ctx.respond("You have opted in to the seasonal role.")
        else:
            opt_out_users.append(ctx.author.id)

            # Check if there's a current holiday and if the member has its role.
            current_date = datetime.now().date()
            holidays = await self.config.guild(ctx.guild).holidays()
            for holiday, details in holidays.items():
                holiday_date = (
                    datetime.strptime(details["date"], "%m-%d")
                    .date()
                    .replace(year=current_date.year)
                )
                if current_date == holiday_date:
                    role = discord.utils.get(ctx.guild.roles, name=holiday)
                    if role and role in ctx.author.roles:
                        await ctx.author.remove_roles(role)
            await ctx.respond("You have opted out from the seasonal role.")

        await self.config.guild(ctx.guild).opt_out_users.set(opt_out_users)

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="check")
    async def force_check_holidays(
        self, ctx: commands.Context, date_str: Optional[str] = None
    ):
        """Force check holidays."""
        await self.check_holidays(ctx.guild, date_str=date_str, force=True)
        await ctx.send("Checked holidays for this guild.")

    @tasks.loop(hours=24)
    async def check_holidays(
        self,
        guild: Optional[discord.Guild] = None,
        date_str: Optional[str] = None,
        force: bool = False,
    ):
        """Check holidays and apply/remove roles if needed."""
        logger.debug("Starting check_holidays loop")

        # If guild is not provided, use the guild set in before_check_holidays
        if guild is None:
            guild = self.guild

        if guild is None:
            logger.error("Guild not set for check_holidays task.")
            return
    
        # Determine Target Date with Error Handling
        try:
            if date_str:
                target_date = (
                    datetime.strptime(date_str, "%m-%d")
                    .date()
                    .replace(year=datetime.now().year)
                )
                logger.debug(f"Using provided date: {target_date}")
            else:
                target_date = datetime.now().date()
                logger.debug(f"Using current date: {target_date}")
        except ValueError:
            logger.error("Invalid date format provided.")
            return

        last_checked_date_str = await self.config.guild(guild).last_checked_date()
        if not force and last_checked_date_str:
            last_checked_date = datetime.strptime(
                last_checked_date_str, "%Y-%m-%d"
            ).date()
            if last_checked_date >= target_date:
                logger.debug(
                    "Last checked date is greater than or equal to target date, skipping"
                )
                return  # This date was already checked, skip

        try:
            logger.debug("Checking holidays")
            holidays: Dict[str, Dict[str, Any]] = await self.config.guild(
                guild
            ).holidays()
            logger.debug(f"Holidays: {holidays}")

            # Determine which holiday is starting, ending, or ongoing
            starting_holiday = None
            ended_holidays = []
            ongoing_holiday = None
            holiday_details = None

            for holiday, details in holidays.items():
                holiday_date = (
                    datetime.strptime(details["date"], "%m-%d")
                    .date()
                    .replace(year=target_date.year)
                )
                # Check if a holiday is starting
                if target_date == (holiday_date - timedelta(days=7)):
                    starting_holiday = holiday
                    holiday_details = details

                # Check for an ongoing holiday
                elif (
                    (holiday_date - timedelta(days=7))
                    <= target_date
                    < (holiday_date + timedelta(days=1))
                ):
                    ongoing_holiday = holiday
                    holiday_details = details

                else:
                    ended_holidays.append(holiday)

            logger.debug(f"Starting holiday: {starting_holiday}")
            logger.debug(f"Ending holiday: {ended_holidays}")
            logger.debug(f"Ongoing holiday: {ongoing_holiday}")
            logger.debug(f"Holiday details: {holiday_details}")

            # Apply role for starting or ongoing holiday
            if starting_holiday or ongoing_holiday:
                holiday = starting_holiday if starting_holiday else ongoing_holiday
                logger.debug(f"Starting or ongoing holiday detected: {holiday}")
                role = discord.utils.get(guild.roles, name=holiday)
                logger.debug(f"Role: {role}")
                if not role:
                    logger.debug("Role not found, creating")
                    role = await self.add_holiday_role(
                        ctx,
                        holiday,
                        holiday_details.get("date"),
                        holiday_details.get("color"),
                        holiday_details.get("image"),
                    )
                    await self.apply_role_to_all(guild, role)

            # Remove role for ended holidays
            if len(ended_holidays) > 0:
                for ended_holiday in ended_holidays:
                    role = discord.utils.get(guild.roles, name=ended_holiday)
                    if role:
                        logger.debug(f"Stale ended holiday detected: {ended_holiday}")
                        logger.debug("Role found, removing")
                        await self.remove_role_from_all(guild, role)
                        await role.delete()

            # Save the last checked date
            await self.config.guild(guild).last_checked_date.set(
                target_date.strftime("%Y-%m-%d")
            )

        except Exception as e:
            logger.error(f"Error in check_holidays loop: {e}")

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="forceholiday")
    async def force_holiday(
        self, ctx: commands.Context, *holiday_name_parts: str
    ) -> None:
        """Force a specific holiday role, removing and deleting all other holiday roles."""
        holiday_name = " ".join(holiday_name_parts).lower()
        logger.info(
            f"Attempting to force holiday role for '{holiday_name}' in guild {ctx.guild.name}"
        )

        guild: discord.Guild = ctx.guild
        holidays: Dict[str, Any] = await self.config.guild(guild).holidays()
        dry_run_mode: bool = await self.config.guild(guild).dry_run_mode()

        matched_holiday_name = next(
            (h for h in holidays if h.lower() == holiday_name), None
        )
        if matched_holiday_name is None:
            logger.warning(f"Holiday '{holiday_name}' not found in guild {guild.name}")
            await ctx.send(f"Holiday '{holiday_name}' does not exist!")
            return

        holiday_details = holidays[matched_holiday_name]

        # Remove and delete all other holiday roles first
        for holiday, details in holidays.items():
            if holiday.lower() != holiday_name:
                role_to_delete = discord.utils.get(guild.roles, name=holiday)
                if role_to_delete:
                    if dry_run_mode:
                        message = f"[Dry Run] Would have deleted holiday role '{holiday}' in guild {guild.name}"
                        await ctx.send(message)
                        logger.info(message)
                    else:
                        await self.delete_role(guild, role_to_delete)

        # Apply the new holiday role
        if dry_run_mode:
            message = f"[Dry Run] Would have applied holiday role '{matched_holiday_name}' in guild {guild.name}"
            logger.info(message)
            await ctx.send(message)
        else:
            role = await self.add_holiday_role(
                ctx,
                matched_holiday_name,
                holiday_details["date"],
                holiday_details["color"],
                holiday_details["image"],
            )
            if role:
                await self.apply_role_to_all(guild, role)
                logger.info(
                    f"Successfully applied holiday role '{matched_holiday_name}' in guild {guild.name}"
                )
                await ctx.send(
                    f"Forced holiday role '{matched_holiday_name}' applied to all members."
                )
            else:
                logger.error(
                    f"Failed to create or find role for holiday '{matched_holiday_name}' in guild {guild.name}"
                )
                await ctx.send("Failed to apply the holiday role.")

    async def delete_role(self, guild: discord.Guild, role: discord.Role) -> None:
        """Deletes a role from a guild."""
        try:
            await role.delete()
            logger.debug(f"Deleted role {role.name} in guild {guild.name}")
        except Exception as e:
            logger.error(f"Error deleting role {role.name} in guild {guild.name}: {e}")

    @check_holidays.before_loop
    async def before_check_holidays(self):
        await self.bot.wait_until_ready()
        self.guild = self.bot.get_guild(GUILD_ID)

    async def update_role(
        self, guild: discord.Guild, holiday_details: Dict[str, Any]
    ) -> None:
        """Update the role's appearance based on the holiday details."""
        logger.debug(
            f"Updating role for {guild.name} with holiday {holiday_details['name']}"
        )

        try:
            dry_run_mode = await self.config.guild(guild).dry_run_mode()

            if dry_run_mode:
                role_id = await self.config.guild(guild).seasonal_role()
                role = discord.utils.get(guild.roles, id=role_id)
                if role:
                    try:
                        await role.edit(
                            name=holiday_details["name"],
                            color=discord.Color(holiday_details["color"]),
                        )
                        # Add logic here to change the role's image if Discord supports it in the future.
                    except discord.Forbidden:
                        logger.error(
                            f"Permission error when trying to edit role in {guild.name}"
                        )
            else:
                logger.info(
                    f"Would have updated role in {guild.name} to {holiday_details['name']}"
                )
        except Exception as e:
            logger.error(f"Error updating role for guild {guild.name}: {e}")

    async def apply_role_to_all(self, guild: discord.Guild, role: discord.Role) -> None:
        dry_run_mode = await self.config.guild(guild).dry_run_mode()
        if dry_run_mode:
            logger.info(
                f"Would have applied role to {len(guild.members)} members in {guild.name}"
            )
        else:
            opt_out_users = await self.config.guild(guild).opt_out_users()
            for member in guild.members:
                if member.id not in opt_out_users:
                    try:
                        await member.add_roles(role)
                        logger.debug(
                            f"Added role {role.name} to {member.name} in {guild.name}"
                        )
                    except discord.Forbidden:
                        logger.error(
                            f"Permission error when trying to add role to member {member.name} in {guild.name}"
                        )

    async def remove_role_from_all(
        self, guild: discord.Guild, role: discord.Role
    ) -> None:
        dry_run_mode = await self.config.guild(guild).dry_run_mode()
        if dry_run_mode:
            for member in guild.members:
                try:
                    await member.remove_roles(role)
                    logger.debug(
                        f"Removed role {role.name} from {member.name} in {guild.name}"
                    )
                except discord.Forbidden:
                    logger.error(
                        f"Permission error when trying to remove role from member {member.name} in {guild.name}"
                    )
        else:
            logger.info(
                f"Would have removed role from {len(guild.members)} members in {guild.name}"
            )

    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="banner")
    async def change_server_banner_command(self, ctx, url: str):
        """Command to change the server banner."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("You need the 'Manage Server' permission to use this command.")
            return

        if ctx.guild.premium_tier < 2:
            await ctx.send("This server needs to be at least level 2 boosted to change the banner.")
            return

        result = await self.change_server_banner(ctx.guild, url)
        await ctx.send(result)

    async def change_server_banner(self, guild, url):
        """Helper method to change the server banner."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        await guild.edit(banner=image_bytes)
                        return "Banner changed successfully!"
                    else:
                        return "Failed to download the image from the provided URL."
        except Exception as e:
            return f"An error occurred: {e}"

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Assign the active holiday role to the joining member if they haven't opted out."""

        current_date = datetime.now().date()

        # Get the active holiday from the configuration.
        active_holiday = await self.config.guild(member.guild).active_holiday()

        # If there's an active holiday.
        if active_holiday:
            role = discord.utils.get(member.guild.roles, name=active_holiday)
            if role:
                # Check if the member has opted out from seasonal roles.
                opt_out_users = await self.config.guild(member.guild).opt_out_users()
                if member.id not in opt_out_users:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        logger.error(
                            f"Permission error when trying to add role for {member.name} in {member.guild.name}"
                        )
                else:
                    logger.info(
                        f"{member.name} has opted out from the seasonal role in {member.guild.name}. Skipping role assignment."
                    )
            else:
                logger.warning(
                    f"Role for active holiday '{active_holiday}' not found in {member.guild.name}."
                )
        else:
            logger.info(
                f"No active holiday currently in {member.guild.name}. Skipping role assignment for {member.name}."
            )
