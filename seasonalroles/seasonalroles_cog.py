import os
from typing import Optional


from datetime import datetime
import re
import discord
from discord.ext import tasks
from redbot.core.bot import Red
from redbot.core import Config, commands

import logging

from .holiday_management import HolidayService
from .role_management import RoleManager
from utilities.image_utils import get_image_handler
from utilities.discord_utils import fetch_and_save_guild_banner

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))
image_path = os.path.abspath(os.path.join("assets", "your-image.png"))
logger.debug(f"Absolute image path: {image_path}")

# IMAke sure banner saving adds the date it was saved
# Make sure we update the "last updated date" in banner management
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
                "Kids Day": {"date": "05-05", "color": "#68855A", "image": "assets/kids-day-01.png", "banner": "assets/kids-day-banner-01.png"},
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
                "is_holiday_banner_active": False
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

        role_manager = RoleManager(self.config)
        role = await role_manager.create_or_update_role(ctx.guild, name, color, image)
        if role:
            await ctx.send(f"Role '{name}' has been {'updated' if discord.utils.get(ctx.guild.roles, name=name) else 'created'}.")
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
    async def check_holidays(self, guild: Optional[discord.Guild] = None, date_str: Optional[str] = None, force: bool = False):
        if guild is None:
            guild = self.guild
            logger.debug("No guild provided, using default guild.")

        try:
            holidays = await self.config.guild(guild).holidays()
            logger.debug(f"Retrieved holidays: {holidays}")
        except Exception as e:
            logger.error(f"Failed to retrieve holidays from config: {e}")
            return

        current_date = datetime.now().date()
        logger.debug(f"Current date: {current_date}")

        # Sort holidays by date to manage overlapping or back-to-back holidays
        sorted_holidays = sorted(holidays.items(), key=lambda x: datetime.strptime(f"{current_date.year}-{x[1]['date']}", "%Y-%m-%d").date())

        banner_config = await self.config.guild(guild).banner_management()
        for i, (holiday_name, details) in enumerate(sorted_holidays):
            holiday_date_str = details['date']
            holiday_date = datetime.strptime(f"{current_date.year}-{holiday_date_str}", "%Y-%m-%d").date()
            days_until_holiday = (holiday_date - current_date).days
            logger.debug(f"Holiday '{holiday_name}' is {days_until_holiday} days away.")

            # Save the original banner if within 7 days and not already saved
            if days_until_holiday <= 7 and banner_config['original_banner_path'] is None:
                # TODO: CHANGE TO PROPER PATH, WILL BREAK ON OTHERS MACHINES
                save_path = f"/homelab/seasonalroles/assets/guild-banner-non-holiday-{guild.id}.png"
                saved_path = await fetch_and_save_guild_banner(guild, save_path)
                if saved_path:
                    await self.config.guild(guild).banner_management.set_raw('original_banner_path', value=saved_path)
                    logger.info("Original banner saved.")

            # Role and banner management
            if days_until_holiday < 0 or days_until_holiday > 7:
                role = discord.utils.get(guild.roles, name=holiday_name)
                if role:
                    await self.role_manager.delete_role_from_guild(guild, role)
                    logger.info(f"Role '{holiday_name}' has been removed from the guild.")
                if days_until_holiday < 0 and i == 0:  # Check if it's the first holiday past the current date
                    # Restore the original banner after the holiday ends
                    original_banner_path = banner_config['original_banner_path']
                    if original_banner_path:
                        await self.change_server_banner(guild, original_banner_path)
                        logger.info("Restored the original banner.")

            elif 0 <= days_until_holiday <= 7:
                if not force and days_until_holiday > 0:
                    logger.debug(f"Skipping role application for '{holiday_name}' as it's not today and force is not enabled.")
                    continue

                role = await self.role_manager.create_or_update_role(guild, holiday_name, details['color'], details['date'])
                if role:
                    await self.role_manager.assign_role_to_all_members(guild, role)
                    logger.info(f"Applied holiday role for '{holiday_name}' to opted-in members.")

                # Update the guild's banner if a holiday-specific banner is specified
                if 'banner' in details:
                    holiday_banner_path = details['banner']
                    await self.change_server_banner(guild, holiday_banner_path)
                    logger.info(f"Updated guild banner for '{holiday_name}'.")


    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @seasonal.command(name="forceholiday")
    async def force_holiday(self, ctx: commands.Context, *holiday_name_parts: str) -> None:
        holiday_name = " ".join(holiday_name_parts).lower()
        guild = ctx.guild
        holidays = await self.config.guild(guild).holidays()
        dry_run_mode = await self.config.guild(guild).dry_run_mode()

        logger.debug(f"Processing forceholiday for '{holiday_name}' with dry run mode set to {dry_run_mode}.")

        # TODO: Convert to helper functions like the role management code.
        # Retrieve and save the current banner if not already saved
        save_path = f"/homelab/seasonalroles/assets/guild-banner-non-holiday-{guild.id}.png"
        try:
            saved_path = await fetch_and_save_guild_banner(guild, save_path)
            if saved_path:
                await self.config.guild(guild).banner_management.set_raw('original_banner_path', value=saved_path)
                logger.info("Original banner saved.")
            else:
                logger.error("Failed to save the original banner.")
                await ctx.send("Failed to save the original banner. Please check the logs for more details.")
        except Exception as e:
            logger.error(f"Error saving the original banner: {e}")
            await ctx.send(f"An error occurred while saving the original banner: {e}")

        # Apply the holiday banner
        # Ensure holiday names are accessed in a case-insensitive manner
        holidays_lower = {key.lower(): value for key, value in holidays.items()}
        holiday_details = holidays_lower.get(holiday_name)

        if holiday_details:
            logger.debug(f"Found holiday details for '{holiday_name}': {holiday_details}")
            if 'banner' in holiday_details:
                holiday_banner_path = os.path.join(os.path.dirname(__file__), holiday_details['banner'])
                try:
                    await self.change_server_banner(guild, holiday_banner_path)
                    logger.info(f"Updated guild banner for '{holiday_name}'.")
                except Exception as e:
                    logger.error(f"Error updating guild banner for '{holiday_name}': {e}")
                    await ctx.send(f"An error occurred while updating the guild banner for '{holiday_name}': {e}")
            else:
                await ctx.send(f"No banner specified for '{holiday_name}'.")
        else:
            await ctx.send(f"No details found for the holiday '{holiday_name}'.")
            logger.error(f"No details found for the holiday '{holiday_name}'.")


        exists, message = await self.holiday_service.validate_holiday_exists(holidays, holiday_name)
        if not exists:
            logger.error(f"Failed to find holiday: {message}")
            await ctx.send(message or "An error occurred.")
            return
            

        success, message = await self.holiday_service.remove_all_except_current_holiday_role(guild, holiday_name)
        if message:
            logger.debug(message)
            await ctx.send(message)
        if not success:
            logger.error("Failed to clear other holidays.")
            return

        success, message = await self.holiday_service.apply_holiday_role(guild, holiday_name, dry_run_mode)
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
    @seasonal.command(name="banner")
    async def change_server_banner_command(self, ctx, url: str = None):
        """Command to change the server banner from a URL or an uploaded image."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("You need the 'Manage Server' permission to use this command.")
            return

        if ctx.guild.premium_tier < 2:
            await ctx.send("This server needs to be at least level 2 boosted to change the banner.")
            return

        # Determine the source of the image
        if not url and len(ctx.message.attachments) == 0:
            await ctx.send("Please provide a URL or upload an image.")
            return
        elif len(ctx.message.attachments) > 0:
            if url:
                await ctx.send("Please provide either a URL or an uploaded image, not both.")
                return
            url = ctx.message.attachments[0].url

        result = await self.change_server_banner(ctx.guild, url)
        await ctx.send(result)

    async def change_server_banner(self, guild, url):
        """Helper method to change the server banner using the image_utils handlers."""
        try:
            # Use the factory to get the appropriate image handler for the URL
            image_handler = get_image_handler(url)
            image_bytes = await image_handler.fetch_image_data()

            # Update the guild's banner
            await guild.edit(banner=image_bytes)
            return "Banner changed successfully!"
        except Exception as e:
            return f"An error occurred: {e}"

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

