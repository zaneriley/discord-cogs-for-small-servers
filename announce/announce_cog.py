"""
Main module for the Announce cog.

This module contains the Announce cog class with commands for creating
and managing announcements in Discord servers.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import humanize_list

from utilities.announcement_utils import (
    send_embed_announcement,
    send_text_announcement,
)

if TYPE_CHECKING:
    from redbot.core.bot import Red

# Set up logging
log = logging.getLogger("red.announce")

# Constants
IDENTIFIER = int(os.getenv("ANNOUNCE_IDENTIFIER", "889977665544"))
DEFAULT_COLOR = 0x3498DB  # Blue
MAX_SCHEDULE_DAYS = 30  # Maximum days in advance to schedule
MAX_HISTORY_ENTRIES = 100
MAX_DISPLAY_COUNT = 25
MIN_DISPLAY_COUNT = 10
MAX_CUSTOM_DAYS_INTERVAL = 365


class Announce(commands.Cog):

    """
    Announcement system for Discord servers.

    Create and manage announcements, including:
    - Text announcements
    - Rich embed announcements
    - Scheduled announcements
    - Recurring announcements
    - Announcement templates
    """

    def __init__(self, bot: Red) -> None:
        """Initialize the Announce cog."""
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=IDENTIFIER, force_registration=True
        )

        # Default guild settings
        default_guild = {
            "channels": {},  # channel_id: friendly_name
            "default_channel": None,  # Default channel ID for announcements
            "templates": {},  # name: template_data
            "scheduled": [],  # List of scheduled announcements
            "recurring": {},  # id: recurring_data
            "history": [],  # List of previous announcements (limited to 100)
            "permissions": {
                "roles": [],  # List of role IDs that can use this cog
                "users": []   # List of user IDs that can use this cog
            }
        }
        self.config.register_guild(**default_guild)

        # Start background tasks
        self._schedule_task = self.check_scheduled_announcements.start()

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        if self._schedule_task:
            self._schedule_task.cancel()

    # Utility methods
    async def _has_announce_permissions(self, ctx: commands.Context) -> bool:
        """Check if user has permission to use announce commands."""
        if await self.bot.is_owner(ctx.author):
            return True

        if ctx.author.guild_permissions.administrator:
            return True

        # Check if user has a permitted role
        config = await self.config.guild(ctx.guild).permissions()
        allowed_roles = config.get("roles", [])
        allowed_users = config.get("users", [])

        if ctx.author.id in allowed_users:
            return True

        author_roles = [role.id for role in ctx.author.roles]
        return any(role_id in allowed_roles for role_id in author_roles)

    async def _can_manage_announce(self, ctx: commands.Context) -> bool:
        """Check if user can manage announcement settings."""
        if await self.bot.is_owner(ctx.author):
            return True
        return ctx.author.guild_permissions.administrator

    # Background tasks
    @tasks.loop(minutes=1)
    async def check_scheduled_announcements(self):
        """Check for and send scheduled announcements."""
        try:
            all_guilds = self.bot.guilds
            now = datetime.now(timezone.utc)

            for guild in all_guilds:
                # Get scheduled announcements
                scheduled = await self.config.guild(guild).scheduled()
                if not scheduled:
                    continue

                # Check each announcement
                to_send = []
                to_keep = []

                for announcement in scheduled:
                    scheduled_time = datetime.fromisoformat(announcement["time"])

                    # If it's time to send
                    if now >= scheduled_time:
                        to_send.append(announcement)
                    else:
                        to_keep.append(announcement)

                # Update scheduled list before sending
                if to_send:
                    await self.config.guild(guild).scheduled.set(to_keep)

                    # Send each announcement
                    for announcement in to_send:
                        await self._send_scheduled_announcement(guild, announcement)

                    # Add to history
                    await self._add_to_history(guild, to_send)

                    # Handle recurring
                    await self._reschedule_recurring(guild, to_send)
        except Exception as e:
            log.exception(f"Error in scheduled announcements task: {e}")

    @check_scheduled_announcements.before_loop
    async def before_check_scheduled(self):
        """Wait until bot is ready before starting task."""
        await self.bot.wait_until_ready()

    async def _send_scheduled_announcement(self, guild: discord.Guild, announcement: dict):
        """Send a scheduled announcement."""
        try:
            channel_id = announcement.get("channel_id")
            channel = guild.get_channel(channel_id)

            if not channel:
                log.error(f"Could not find channel {channel_id} for scheduled announcement in guild {guild.id}")
                return

            if announcement.get("type") == "embed":
                await send_embed_announcement(
                    self.bot,
                    channel_id,
                    announcement.get("content", ""),
                    title=announcement.get("title"),
                    description=announcement.get("description"),
                    color=announcement.get("color", DEFAULT_COLOR),
                    thumbnail=announcement.get("thumbnail"),
                    image=announcement.get("image"),
                    fields=announcement.get("fields", []),
                    mention_type=announcement.get("mention_type"),
                    mention_id=announcement.get("mention_id")
                )
            else:
                await send_text_announcement(
                    self.bot,
                    channel_id,
                    announcement.get("content", ""),
                    mention_type=announcement.get("mention_type"),
                    mention_id=announcement.get("mention_id")
                )

            log.info(f"Sent scheduled announcement in guild {guild.id}, channel {channel_id}")

        except Exception as e:
            log.exception(f"Error sending scheduled announcement: {e}")

    async def _add_to_history(self, guild: discord.Guild, announcements: list[dict]):
        """Add sent announcements to history."""
        async with self.config.guild(guild).history() as history:
            for announcement in announcements:
                # Add timestamp
                announcement["sent_at"] = datetime.now(timezone.utc).isoformat()

                # Add to history
                history.append(announcement)

                # Trim if needed
                if len(history) > MAX_HISTORY_ENTRIES:
                    history.pop(0)

    async def _reschedule_recurring(self, guild: discord.Guild, sent_announcements: list[dict]):
        """Reschedule recurring announcements."""
        recurring = await self.config.guild(guild).recurring()
        scheduled = await self.config.guild(guild).scheduled()

        for announcement in sent_announcements:
            recurring_id = announcement.get("recurring_id")
            if not recurring_id or recurring_id not in recurring:
                continue

            recurrence = recurring[recurring_id]
            schedule_type = recurrence.get("type", "daily")

            # Create new schedule time
            sent_time = datetime.fromisoformat(announcement["time"])

            if schedule_type == "daily":
                next_time = sent_time + timedelta(days=1)
            elif schedule_type == "weekly":
                next_time = sent_time + timedelta(days=7)
            elif schedule_type == "monthly":
                # Set to same day next month
                next_month = sent_time.month + 1
                next_year = sent_time.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1

                # Handle month length differences
                try:
                    next_time = sent_time.replace(year=next_year, month=next_month)
                except ValueError:
                    # Handle edge case (e.g., Jan 31 -> Feb 28)
                    last_day = 28
                    if next_month == 2:
                        if next_year % 4 == 0 and (next_year % 100 != 0 or next_year % 400 == 0):
                            last_day = 29
                    else:
                        last_day = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][next_month]

                    next_time = sent_time.replace(year=next_year, month=next_month, day=last_day)
            else:
                # Custom interval in days
                interval = recurrence.get("interval", 1)
                next_time = sent_time + timedelta(days=interval)

            # Create new scheduled announcement
            new_announcement = announcement.copy()
            new_announcement["time"] = next_time.isoformat()

            # Add to scheduled
            scheduled.append(new_announcement)

        # Save updated schedule
        await self.config.guild(guild).scheduled.set(scheduled)

    # Command groups
    @commands.group()
    @commands.guild_only()
    async def announce(self, ctx: commands.Context):
        """Commands for the announcement system."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # Channel management commands
    @announce.group(name="channel", aliases=["channels"])
    @commands.guild_only()
    async def announce_channel(self, ctx: commands.Context):
        """Manage announcement channels."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @announce_channel.command(name="add")
    @commands.guild_only()
    async def channel_add(self, ctx: commands.Context, channel: discord.TextChannel, *, name: str | None = None):
        """
        Add a channel to the announcement channels list.

        Parameters
        ----------
        channel: The channel to add
        name: Optional friendly name for the channel

        """
        if not await self._can_manage_announce(ctx):
            return await ctx.send("You don't have permission to manage announcement channels.")

        # Check bot permissions in the channel
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages:
            return await ctx.send(f"I don't have permission to send messages in {channel.mention}.")

        # Use channel name if not provided
        channel_name = name or channel.name

        async with self.config.guild(ctx.guild).channels() as channels:
            channels[str(channel.id)] = channel_name

        await ctx.send(f"Added {channel.mention} as an announcement channel with name: `{channel_name}`")

        # If no default channel is set, set this as default
        default_channel = await self.config.guild(ctx.guild).default_channel()
        if default_channel is None:
            await self.config.guild(ctx.guild).default_channel.set(channel.id)
            await ctx.send(f"{channel.mention} has also been set as the default announcement channel.")
            return None
        return None

    @announce_channel.command(name="remove")
    @commands.guild_only()
    async def channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Remove a channel from the announcement channels list.

        Parameters
        ----------
        channel: The channel to remove

        """
        if not await self._can_manage_announce(ctx):
            return await ctx.send("You don't have permission to manage announcement channels.")

        async with self.config.guild(ctx.guild).channels() as channels:
            if str(channel.id) not in channels:
                return await ctx.send(f"{channel.mention} is not in the announcement channels list.")

            del channels[str(channel.id)]

        # If this was the default channel, clear that setting
        default_channel = await self.config.guild(ctx.guild).default_channel()
        if default_channel == channel.id:
            await self.config.guild(ctx.guild).default_channel.set(None)
            await ctx.send(f"{channel.mention} was removed and was also the default channel. Please set a new default.")
            return None
        await ctx.send(f"{channel.mention} has been removed from the announcement channels list.")
        return None

    @announce_channel.command(name="list")
    @commands.guild_only()
    async def channel_list(self, ctx: commands.Context):
        """List all announcement channels."""
        channels = await self.config.guild(ctx.guild).channels()
        default_channel = await self.config.guild(ctx.guild).default_channel()

        if not channels:
            return await ctx.send("No announcement channels have been configured yet.")

        lines = []
        for channel_id, name in channels.items():
            channel = ctx.guild.get_channel(int(channel_id))
            if channel:
                is_default = " (DEFAULT)" if int(channel_id) == default_channel else ""
                lines.append(f"• {channel.mention} - `{name}`{is_default}")
            else:
                # Channel no longer exists
                async with self.config.guild(ctx.guild).channels() as current_channels:
                    if channel_id in current_channels:
                        del current_channels[channel_id]

        if not lines:
            return await ctx.send("No valid announcement channels found.")

        message = "**Announcement Channels:**\n" + "\n".join(lines)

        await ctx.send(message)
        return None

    @announce_channel.command(name="default")
    @commands.guild_only()
    async def channel_default(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Set the default announcement channel.

        Parameters
        ----------
        channel: The channel to set as default

        """
        if not await self._can_manage_announce(ctx):
            return await ctx.send("You don't have permission to manage announcement channels.")

        # Make sure the channel is in our list
        channels = await self.config.guild(ctx.guild).channels()
        if str(channel.id) not in channels:
            # Add it to the list first
            channel_name = channel.name
            async with self.config.guild(ctx.guild).channels() as channels_edit:
                channels_edit[str(channel.id)] = channel_name

            await ctx.send(f"Added {channel.mention} to announcement channels.")

        # Set as default
        await self.config.guild(ctx.guild).default_channel.set(channel.id)
        await ctx.send(f"{channel.mention} has been set as the default announcement channel.")
        return None

    # Basic announcement commands
    @announce.command(name="text")
    @commands.guild_only()
    async def send_text(self, ctx: commands.Context, channel: discord.TextChannel | None = None, *, content: str):
        """
        Send a text announcement to a channel.

        Parameters
        ----------
        channel: Optional channel to send to (uses default if not specified)
        content: The announcement message

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to send announcements.")

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Check permissions
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages:
            return await ctx.send(f"I don't have permission to send messages in {channel.mention}.")

        # Send the announcement
        result, error = await send_text_announcement(
            self.bot,
            channel_id,
            content
        )

        if result:
            await ctx.send(f"Announcement sent to {channel.mention}!")

            # Add to history
            announcement = {
                "type": "text",
                "channel_id": channel_id,
                "content": content,
                "sent_by": ctx.author.id,
                "sent_at": datetime.now(timezone.utc).isoformat()
            }

            async with self.config.guild(ctx.guild).history() as history:
                history.append(announcement)
                if len(history) > MAX_HISTORY_ENTRIES:
                    history.pop(0)
                    return None
                return None
        else:
            await ctx.send(f"Failed to send announcement: {error}")
            return None

    @announce.command(name="embed")
    @commands.guild_only()
    async def send_embed(self, ctx: commands.Context, channel: discord.TextChannel | None = None, *, title_and_desc: str):
        """
        Send an embed announcement to a channel.

        Format: [p]announce embed [channel] Title | Description

        Parameters
        ----------
        channel: Optional channel to send to (uses default if not specified)
        title_and_desc: The title and description, separated by a pipe (|)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to send announcements.")

        # Parse title and description
        if "|" not in title_and_desc:
            return await ctx.send("You must provide both a title and description separated by a pipe (|).")

        parts = title_and_desc.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Check permissions
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            missing = []
            if not permissions.send_messages:
                missing.append("Send Messages")
            if not permissions.embed_links:
                missing.append("Embed Links")
            return await ctx.send(f"I don't have the following permissions in {channel.mention}: {humanize_list(missing)}")

        # Send the announcement
        result, error = await send_embed_announcement(
            self.bot,
            channel_id,
            None,  # No content for basic embeds
            title=title,
            description=description,
            color=DEFAULT_COLOR
        )

        if result:
            await ctx.send(f"Embed announcement sent to {channel.mention}!")

            # Add to history
            announcement = {
                "type": "embed",
                "channel_id": channel_id,
                "title": title,
                "description": description,
                "color": DEFAULT_COLOR,
                "sent_by": ctx.author.id,
                "sent_at": datetime.now(timezone.utc).isoformat()
            }

            async with self.config.guild(ctx.guild).history() as history:
                history.append(announcement)
                if len(history) > MAX_HISTORY_ENTRIES:
                    history.pop(0)
                    return None
                return None
        else:
            await ctx.send(f"Failed to send announcement: {error}")
            return None

    # Permission management commands
    @announce.group(name="perm", aliases=["perms", "permission", "permissions"])
    @commands.guild_only()
    async def announce_perms(self, ctx: commands.Context):
        """Manage announcement permissions."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @announce_perms.command(name="addrole")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def perm_add_role(self, ctx: commands.Context, role: discord.Role):
        """
        Add a role that can use announcement commands.

        Parameters
        ----------
        role: The role to add

        """
        async with self.config.guild(ctx.guild).permissions.roles() as roles:
            if role.id in roles:
                return await ctx.send(f"The role {role.name} already has announcement permissions.")

            roles.append(role.id)

        await ctx.send(f"The role {role.name} can now use announcement commands.")
        return None

    @announce_perms.command(name="removerole")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def perm_remove_role(self, ctx: commands.Context, role: discord.Role):
        """
        Remove a role's announcement permissions.

        Parameters
        ----------
        role: The role to remove

        """
        async with self.config.guild(ctx.guild).permissions.roles() as roles:
            if role.id not in roles:
                return await ctx.send(f"The role {role.name} doesn't have announcement permissions.")

            roles.remove(role.id)

        await ctx.send(f"The role {role.name} can no longer use announcement commands.")
        return None

    @announce_perms.command(name="adduser")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def perm_add_user(self, ctx: commands.Context, user: discord.Member):
        """
        Add a user who can use announcement commands.

        Parameters
        ----------
        user: The user to add

        """
        async with self.config.guild(ctx.guild).permissions.users() as users:
            if user.id in users:
                return await ctx.send(f"{user.display_name} already has announcement permissions.")

            users.append(user.id)

        await ctx.send(f"{user.display_name} can now use announcement commands.")
        return None

    @announce_perms.command(name="removeuser")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def perm_remove_user(self, ctx: commands.Context, user: discord.Member):
        """
        Remove a user's announcement permissions.

        Parameters
        ----------
        user: The user to remove

        """
        async with self.config.guild(ctx.guild).permissions.users() as users:
            if user.id not in users:
                return await ctx.send(f"{user.display_name} doesn't have announcement permissions.")

            users.remove(user.id)

        await ctx.send(f"{user.display_name} can no longer use announcement commands.")
        return None

    @announce_perms.command(name="list")
    @commands.guild_only()
    async def perm_list(self, ctx: commands.Context):
        """List all roles and users with announcement permissions."""
        perms = await self.config.guild(ctx.guild).permissions()

        role_ids = perms.get("roles", [])
        user_ids = perms.get("users", [])

        if not role_ids and not user_ids:
            return await ctx.send("No custom permissions configured. Only server administrators can use announcement commands.")

        embed = discord.Embed(
            title="Announcement Permissions",
            color=DEFAULT_COLOR
        )

        # List roles
        role_mentions = []
        for role_id in role_ids:
            role = ctx.guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)

        if role_mentions:
            embed.add_field(
                name="Roles with permissions",
                value="\n".join(role_mentions) if role_mentions else "None",
                inline=False
            )

        # List users
        user_mentions = []
        for user_id in user_ids:
            user = ctx.guild.get_member(user_id)
            if user:
                user_mentions.append(user.mention)

        if user_mentions:
            embed.add_field(
                name="Users with permissions",
                value="\n".join(user_mentions) if user_mentions else "None",
                inline=False
            )

        # Add note about administrators
        embed.set_footer(text="Server administrators always have permission to use announcement commands.")

        await ctx.send(embed=embed)
        return None

    # Template management commands
    @announce.group(name="template", aliases=["templates", "tmpl"])
    @commands.guild_only()
    async def announce_template(self, ctx: commands.Context):
        """Manage announcement templates."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @announce_template.command(name="add")
    @commands.guild_only()
    async def template_add(self, ctx: commands.Context, name: str, *, content: str):
        """
        Add a text announcement template.

        Parameters
        ----------
        name: The template name (no spaces)
        content: The template content

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to manage announcement templates.")

        # Validate name (alphanumeric and underscores only)
        if not re.match(r"^[a-zA-Z0-9_]+$", name):
            return await ctx.send("Template name must contain only letters, numbers, and underscores.")

        async with self.config.guild(ctx.guild).templates() as templates:
            if name in templates:
                return await ctx.send(f"A template named `{name}` already exists. Use `{ctx.prefix}announce template edit` to modify it.")

            # Create template
            templates[name] = {
                "type": "text",
                "content": content,
                "created_by": ctx.author.id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "modified_at": datetime.now(timezone.utc).isoformat()
            }

        await ctx.send(f"Template `{name}` has been created.")
        return None

    @announce_template.command(name="addembed")
    @commands.guild_only()
    async def template_add_embed(self, ctx: commands.Context, name: str, *, title_and_desc: str):
        """
        Add an embed announcement template.

        Format: [p]announce template addembed name Title | Description

        Parameters
        ----------
        name: The template name (no spaces)
        title_and_desc: The title and description, separated by a pipe (|)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to manage announcement templates.")

        # Validate name (alphanumeric and underscores only)
        if not re.match(r"^[a-zA-Z0-9_]+$", name):
            return await ctx.send("Template name must contain only letters, numbers, and underscores.")

        # Parse title and description
        if "|" not in title_and_desc:
            return await ctx.send("You must provide both a title and description separated by a pipe (|).")

        parts = title_and_desc.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        async with self.config.guild(ctx.guild).templates() as templates:
            if name in templates:
                return await ctx.send(f"A template named `{name}` already exists. Use `{ctx.prefix}announce template edit` to modify it.")

            # Create template
            templates[name] = {
                "type": "embed",
                "title": title,
                "description": description,
                "color": DEFAULT_COLOR,
                "created_by": ctx.author.id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "modified_at": datetime.now(timezone.utc).isoformat()
            }

        await ctx.send(f"Embed template `{name}` has been created.")
        return None

    @announce_template.command(name="edit")
    @commands.guild_only()
    async def template_edit(self, ctx: commands.Context, name: str, *, content: str):
        """
        Edit a text announcement template.

        Parameters
        ----------
        name: The template name
        content: The new template content

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to manage announcement templates.")

        async with self.config.guild(ctx.guild).templates() as templates:
            if name not in templates:
                return await ctx.send(f"Template `{name}` does not exist.")

            template = templates[name]

            # Check that it's a text template
            if template.get("type") != "text":
                return await ctx.send(f"Template `{name}` is not a text template. Use `{ctx.prefix}announce template editembed` instead.")

            # Update template
            template["content"] = content
            template["modified_by"] = ctx.author.id
            template["modified_at"] = datetime.now(timezone.utc).isoformat()

            templates[name] = template

        await ctx.send(f"Template `{name}` has been updated.")
        return None

    @announce_template.command(name="editembed")
    @commands.guild_only()
    async def template_edit_embed(self, ctx: commands.Context, name: str, *, title_and_desc: str):
        """
        Edit an embed announcement template.

        Format: [p]announce template editembed name Title | Description

        Parameters
        ----------
        name: The template name
        title_and_desc: The new title and description, separated by a pipe (|)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to manage announcement templates.")

        # Parse title and description
        if "|" not in title_and_desc:
            return await ctx.send("You must provide both a title and description separated by a pipe (|).")

        parts = title_and_desc.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        async with self.config.guild(ctx.guild).templates() as templates:
            if name not in templates:
                return await ctx.send(f"Template `{name}` does not exist.")

            template = templates[name]

            # Check that it's an embed template
            if template.get("type") != "embed":
                return await ctx.send(f"Template `{name}` is not an embed template. Use `{ctx.prefix}announce template edit` instead.")

            # Update template
            template["title"] = title
            template["description"] = description
            template["modified_by"] = ctx.author.id
            template["modified_at"] = datetime.now(timezone.utc).isoformat()

            templates[name] = template

        await ctx.send(f"Embed template `{name}` has been updated.")
        return None

    @announce_template.command(name="color", aliases=["colour"])
    @commands.guild_only()
    async def template_color(self, ctx: commands.Context, name: str, color: discord.Color):
        """
        Set the color for an embed template.

        Parameters
        ----------
        name: The template name
        color: The color (can be hex code like #FF0000 or color name like 'red')

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to manage announcement templates.")

        async with self.config.guild(ctx.guild).templates() as templates:
            if name not in templates:
                return await ctx.send(f"Template `{name}` does not exist.")

            template = templates[name]

            # Check that it's an embed template
            if template.get("type") != "embed":
                return await ctx.send(f"Template `{name}` is not an embed template. Colors only apply to embed templates.")

            # Update color
            template["color"] = color.value
            template["modified_by"] = ctx.author.id
            template["modified_at"] = datetime.now(timezone.utc).isoformat()

            templates[name] = template

        # Create a sample embed to show the color
        embed = discord.Embed(
            title="Color Preview",
            description=f"Template `{name}` color has been set to this.",
            color=color
        )

        await ctx.send(embed=embed)
        return None

    @announce_template.command(name="delete", aliases=["remove"])
    @commands.guild_only()
    async def template_delete(self, ctx: commands.Context, name: str):
        """
        Delete an announcement template.

        Parameters
        ----------
        name: The template name to delete

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to manage announcement templates.")

        async with self.config.guild(ctx.guild).templates() as templates:
            if name not in templates:
                return await ctx.send(f"Template `{name}` does not exist.")

            del templates[name]

        await ctx.send(f"Template `{name}` has been deleted.")
        return None

    @announce_template.command(name="list")
    @commands.guild_only()
    async def template_list(self, ctx: commands.Context):
        """List all announcement templates."""
        templates = await self.config.guild(ctx.guild).templates()

        if not templates:
            return await ctx.send("No announcement templates have been created yet.")

        # Group by type
        text_templates = []
        embed_templates = []

        for name, data in templates.items():
            template_type = data.get("type", "text")
            if template_type == "embed":
                embed_templates.append(name)
            else:
                text_templates.append(name)

        # Create embed
        embed = discord.Embed(
            title="Announcement Templates",
            description=f"Total: {len(templates)} templates",
            color=DEFAULT_COLOR
        )

        if text_templates:
            text_templates.sort()
            embed.add_field(
                name=f"Text Templates ({len(text_templates)})",
                value="\n".join([f"• `{name}`" for name in text_templates]) or "None",
                inline=False
            )

        if embed_templates:
            embed_templates.sort()
            embed.add_field(
                name=f"Embed Templates ({len(embed_templates)})",
                value="\n".join([f"• `{name}`" for name in embed_templates]) or "None",
                inline=False
            )

        embed.set_footer(text=f"Use {ctx.prefix}announce template view <name> to see template details")

        await ctx.send(embed=embed)
        return None

    @announce_template.command(name="view", aliases=["show", "get"])
    @commands.guild_only()
    async def template_view(self, ctx: commands.Context, name: str):
        """
        View the details of a template.

        Parameters
        ----------
        name: The template name to view

        """
        templates = await self.config.guild(ctx.guild).templates()

        if name not in templates:
            return await ctx.send(f"Template `{name}` does not exist.")

        template = templates[name]
        template_type = template.get("type", "text")

        # Show different information based on template type
        if template_type == "embed":
            # Preview the embed
            embed = discord.Embed(
                title=template.get("title", ""),
                description=template.get("description", ""),
                color=template.get("color", DEFAULT_COLOR)
            )

            # Add template information
            created_at = datetime.fromisoformat(template.get("created_at", datetime.now(timezone.utc).isoformat()))
            created_by = ctx.guild.get_member(template.get("created_by"))
            created_by_name = created_by.display_name if created_by else "Unknown"

            embed.add_field(
                name="Template Information",
                value=f"**Name:** `{name}`\n"
                      f"**Type:** Embed\n"
                      f"**Created by:** {created_by_name}\n"
                      f"**Created at:** {created_at.strftime('%Y-%m-%d %H:%M UTC')}",
                inline=False
            )

            await ctx.send(content="**Template Preview:**", embed=embed)
            return None
        # Show text template
        embed = discord.Embed(
            title=f"Template: {name}",
            description="Text Announcement Template",
            color=DEFAULT_COLOR
        )

        # Add template content
        content = template.get("content", "")
        embed.add_field(
            name="Content",
            value=content if len(content) <= 1024 else f"{content[:1021]}...",
            inline=False
        )

        # Add template information
        created_at = datetime.fromisoformat(template.get("created_at", datetime.now(timezone.utc).isoformat()))
        created_by = ctx.guild.get_member(template.get("created_by"))
        created_by_name = created_by.display_name if created_by else "Unknown"

        embed.add_field(
            name="Template Information",
            value=f"**Type:** Text\n"
                  f"**Created by:** {created_by_name}\n"
                  f"**Created at:** {created_at.strftime('%Y-%m-%d %H:%M UTC')}",
            inline=False
        )

        # If content is too long, send it as a file
        if len(content) > 1024:
            await ctx.send(embed=embed)

            # Send full content in a file
            fp = discord.File(
                filename=f"{name}_template.txt",
                fp=content.encode()
            )
            await ctx.send(content="**Full template content:**", file=fp)
            return None
        await ctx.send(embed=embed)
        return None

    @announce_template.command(name="use")
    @commands.guild_only()
    async def template_use(self, ctx: commands.Context, name: str, channel: discord.TextChannel | None = None):
        """
        Use a template to send an announcement.

        Parameters
        ----------
        name: The template name to use
        channel: Optional channel to send to (uses default if not specified)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to send announcements.")

        templates = await self.config.guild(ctx.guild).templates()

        if name not in templates:
            return await ctx.send(f"Template `{name}` does not exist.")

        template = templates[name]
        template_type = template.get("type", "text")

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Check permissions
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages:
            return await ctx.send(f"I don't have permission to send messages in {channel.mention}.")

        if template_type == "embed" and not permissions.embed_links:
            return await ctx.send(f"I don't have permission to send embeds in {channel.mention}.")

        # Send the announcement based on type
        if template_type == "embed":
            result, error = await send_embed_announcement(
                self.bot,
                channel_id,
                None,  # No content for basic embeds
                title=template.get("title", ""),
                description=template.get("description", ""),
                color=template.get("color", DEFAULT_COLOR)
            )
        else:
            result, error = await send_text_announcement(
                self.bot,
                channel_id,
                template.get("content", "")
            )

        if result:
            await ctx.send(f"Template announcement sent to {channel.mention}!")

            # Add to history
            announcement = {
                "type": template_type,
                "channel_id": channel_id,
                "template_name": name,
                "sent_by": ctx.author.id,
                "sent_at": datetime.now(timezone.utc).isoformat()
            }

            # Add specific fields based on type
            if template_type == "embed":
                announcement["title"] = template.get("title", "")
                announcement["description"] = template.get("description", "")
                announcement["color"] = template.get("color", DEFAULT_COLOR)
            else:
                announcement["content"] = template.get("content", "")

            async with self.config.guild(ctx.guild).history() as history:
                history.append(announcement)
                if len(history) > MAX_HISTORY_ENTRIES:
                    history.pop(0)
                    return None
                return None
        else:
            await ctx.send(f"Failed to send announcement: {error}")
            return None

    # Scheduled announcement commands
    @announce.group(name="schedule", aliases=["sched"])
    @commands.guild_only()
    async def announce_schedule(self, ctx: commands.Context):
        """Schedule announcements for later."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @announce_schedule.command(name="text")
    @commands.guild_only()
    async def schedule_text(self, ctx: commands.Context, channel: discord.TextChannel | None, date_and_time: str, *, content: str):
        """
        Schedule a text announcement.

        Parameters
        ----------
        channel: Channel to send to (uses default if not specified)
        date_and_time: When to send the announcement (YYYY-MM-DD HH:MM)
        content: The announcement message

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to schedule announcements.")

        # Parse the date and time
        try:
            # Add timezone if not specified
            if "T" not in date_and_time and " " in date_and_time:
                date_and_time = date_and_time.replace(" ", "T")

            if "+" not in date_and_time and "-" not in date_and_time[-6:]:
                date_and_time = f"{date_and_time}+00:00"

            scheduled_time = datetime.fromisoformat(date_and_time)

            # Check if time is in the past
            if scheduled_time < datetime.now(timezone.utc):
                return await ctx.send("Cannot schedule announcements in the past.")

            # Check if time is too far in the future
            max_time = datetime.now(timezone.utc) + timedelta(days=MAX_SCHEDULE_DAYS)
            if scheduled_time > max_time:
                return await ctx.send(f"Cannot schedule announcements more than {MAX_SCHEDULE_DAYS} days in advance.")
        except ValueError:
            return await ctx.send("Invalid date format. Please use YYYY-MM-DD HH:MM format.")

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Create the scheduled announcement
        announcement = {
            "type": "text",
            "channel_id": channel_id,
            "content": content,
            "time": scheduled_time.isoformat(),
            "scheduled_by": ctx.author.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat()
        }

        # Add to scheduled list
        async with self.config.guild(ctx.guild).scheduled() as scheduled:
            scheduled.append(announcement)

        # Format time for display
        local_time = scheduled_time.strftime("%Y-%m-%d %H:%M UTC")

        await ctx.send(f"Text announcement scheduled for {local_time} in {channel.mention}.")
        return None

    @announce_schedule.command(name="embed")
    @commands.guild_only()
    async def schedule_embed(self, ctx: commands.Context, channel: discord.TextChannel | None, date_and_time: str, *, title_and_desc: str):
        """
        Schedule an embed announcement.

        Format: [p]announce schedule embed [channel] YYYY-MM-DD HH:MM Title | Description

        Parameters
        ----------
        channel: Channel to send to (uses default if not specified)
        date_and_time: When to send the announcement (YYYY-MM-DD HH:MM)
        title_and_desc: The title and description, separated by a pipe (|)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to schedule announcements.")

        # Parse title and description
        if "|" not in title_and_desc:
            return await ctx.send("You must provide both a title and description separated by a pipe (|).")

        parts = title_and_desc.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        # Parse the date and time
        try:
            # Add timezone if not specified
            if "T" not in date_and_time and " " in date_and_time:
                date_and_time = date_and_time.replace(" ", "T")

            if "+" not in date_and_time and "-" not in date_and_time[-6:]:
                date_and_time = f"{date_and_time}+00:00"

            scheduled_time = datetime.fromisoformat(date_and_time)

            # Check if time is in the past
            if scheduled_time < datetime.now(timezone.utc):
                return await ctx.send("Cannot schedule announcements in the past.")

            # Check if time is too far in the future
            max_time = datetime.now(timezone.utc) + timedelta(days=MAX_SCHEDULE_DAYS)
            if scheduled_time > max_time:
                return await ctx.send(f"Cannot schedule announcements more than {MAX_SCHEDULE_DAYS} days in advance.")
        except ValueError:
            return await ctx.send("Invalid date format. Please use YYYY-MM-DD HH:MM format.")

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Create the scheduled announcement
        announcement = {
            "type": "embed",
            "channel_id": channel_id,
            "title": title,
            "description": description,
            "color": DEFAULT_COLOR,
            "time": scheduled_time.isoformat(),
            "scheduled_by": ctx.author.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat()
        }

        # Add to scheduled list
        async with self.config.guild(ctx.guild).scheduled() as scheduled:
            scheduled.append(announcement)

        # Format time for display
        local_time = scheduled_time.strftime("%Y-%m-%d %H:%M UTC")

        await ctx.send(f"Embed announcement scheduled for {local_time} in {channel.mention}.")
        return None

    @announce_schedule.command(name="template")
    @commands.guild_only()
    async def schedule_template(self, ctx: commands.Context, template_name: str, channel: discord.TextChannel | None, date_and_time: str):
        """
        Schedule an announcement using a template.

        Parameters
        ----------
        template_name: Name of the template to use
        channel: Channel to send to (uses default if not specified)
        date_and_time: When to send the announcement (YYYY-MM-DD HH:MM)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to schedule announcements.")

        # Check if template exists
        templates = await self.config.guild(ctx.guild).templates()
        if template_name not in templates:
            return await ctx.send(f"Template `{template_name}` does not exist.")

        template = templates[template_name]
        template_type = template.get("type", "text")

        # Parse the date and time
        try:
            # Add timezone if not specified
            if "T" not in date_and_time and " " in date_and_time:
                date_and_time = date_and_time.replace(" ", "T")

            if "+" not in date_and_time and "-" not in date_and_time[-6:]:
                date_and_time = f"{date_and_time}+00:00"

            scheduled_time = datetime.fromisoformat(date_and_time)

            # Check if time is in the past
            if scheduled_time < datetime.now(timezone.utc):
                return await ctx.send("Cannot schedule announcements in the past.")

            # Check if time is too far in the future
            max_time = datetime.now(timezone.utc) + timedelta(days=MAX_SCHEDULE_DAYS)
            if scheduled_time > max_time:
                return await ctx.send(f"Cannot schedule announcements more than {MAX_SCHEDULE_DAYS} days in advance.")
        except ValueError:
            return await ctx.send("Invalid date format. Please use YYYY-MM-DD HH:MM format.")

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Create the scheduled announcement
        announcement = {
            "type": template_type,
            "channel_id": channel_id,
            "template_name": template_name,
            "time": scheduled_time.isoformat(),
            "scheduled_by": ctx.author.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat()
        }

        # Add template-specific data
        if template_type == "embed":
            announcement["title"] = template.get("title", "")
            announcement["description"] = template.get("description", "")
            announcement["color"] = template.get("color", DEFAULT_COLOR)
        else:
            announcement["content"] = template.get("content", "")

        # Add to scheduled list
        async with self.config.guild(ctx.guild).scheduled() as scheduled:
            scheduled.append(announcement)

        # Format time for display
        local_time = scheduled_time.strftime("%Y-%m-%d %H:%M UTC")

        await ctx.send(f"Template announcement scheduled for {local_time} in {channel.mention}.")
        return None

    @announce_schedule.command(name="list")
    @commands.guild_only()
    async def schedule_list(self, ctx: commands.Context):
        """List all scheduled announcements."""
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to view scheduled announcements.")

        scheduled = await self.config.guild(ctx.guild).scheduled()
        if not scheduled:
            return await ctx.send("No announcements are currently scheduled.")

        # Sort by scheduled time
        scheduled.sort(key=lambda x: x.get("time", ""))

        # Create embed
        embed = discord.Embed(
            title="Scheduled Announcements",
            description=f"Total: {len(scheduled)} announcements",
            color=DEFAULT_COLOR
        )

        # Add entries (up to 10 to prevent overflow)
        for i, announcement in enumerate(scheduled[:10]):
            # Get basic info
            announcement_type = announcement.get("type", "text")
            scheduled_time = datetime.fromisoformat(announcement.get("time", datetime.now(timezone.utc).isoformat()))
            channel_id = announcement.get("channel_id")
            channel = ctx.guild.get_channel(channel_id)
            channel_mention = channel.mention if channel else f"Unknown Channel ({channel_id})"

            # Create title and description for the field
            if "template_name" in announcement:
                title = f"#{i+1}: Template `{announcement.get('template_name')}`"
            elif announcement_type == "embed":
                title = f"#{i+1}: Embed - {announcement.get('title', 'No Title')[:20]}"
            else:
                title = f"#{i+1}: Text Announcement"

            # Format time
            local_time = scheduled_time.strftime("%Y-%m-%d %H:%M UTC")

            # Create description
            description = f"**Time:** {local_time}\n**Channel:** {channel_mention}\n**Type:** {announcement_type.capitalize()}"

            embed.add_field(
                name=title,
                value=description,
                inline=False
            )

        # Add note if there are more
        if len(scheduled) > 10:
            embed.set_footer(text=f"Showing 10 of {len(scheduled)} scheduled announcements.")

        await ctx.send(embed=embed)
        return None

    @announce_schedule.command(name="cancel")
    @commands.guild_only()
    async def schedule_cancel(self, ctx: commands.Context, index: int):
        """
        Cancel a scheduled announcement.

        Parameters
        ----------
        index: The number of the announcement to cancel (from the list)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to cancel scheduled announcements.")

        async with self.config.guild(ctx.guild).scheduled() as scheduled:
            if not scheduled:
                return await ctx.send("No announcements are currently scheduled.")

            # Check if index is valid
            if index < 1 or index > len(scheduled):
                return await ctx.send(f"Invalid announcement number. Use `{ctx.prefix}announce schedule list` to see the valid numbers.")

            # Get the announcement to remove
            announcement = scheduled[index-1]
            scheduled_time = datetime.fromisoformat(announcement.get("time", datetime.now(timezone.utc).isoformat()))

            # Remove it
            scheduled.pop(index-1)

        # Format time for display
        local_time = scheduled_time.strftime("%Y-%m-%d %H:%M UTC")

        await ctx.send(f"Cancelled announcement #{index} scheduled for {local_time}.")
        return None

    @announce_schedule.command(name="cancelall")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def schedule_cancel_all(self, ctx: commands.Context):
        """Cancel all scheduled announcements."""
        scheduled = await self.config.guild(ctx.guild).scheduled()
        if not scheduled:
            return await ctx.send("No announcements are currently scheduled.")

        # Confirm
        count = len(scheduled)
        confirm_msg = await ctx.send(f"Are you sure you want to cancel all {count} scheduled announcements? Reply with 'yes' to confirm.")

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.lower() == "yes"

        try:
            await self.bot.wait_for("message", check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await confirm_msg.edit(content="Cancellation aborted.")

        # Clear the scheduled list
        await self.config.guild(ctx.guild).scheduled.set([])

        await ctx.send(f"Cancelled all {count} scheduled announcements.")
        return True

    # Recurring announcement commands
    @announce.group(name="recurring", aliases=["recur"])
    @commands.guild_only()
    async def announce_recurring(self, ctx: commands.Context):
        """Set up recurring announcements."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @announce_recurring.command(name="add")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def recurring_add(self, ctx: commands.Context, template_name: str, channel: discord.TextChannel | None,
                           schedule_type: str, *, start_time: str | None = None):
        """
        Add a recurring announcement using a template.

        Parameters
        ----------
        template_name: Name of the template to use
        channel: Channel to send to (uses default if not specified)
        schedule_type: When to repeat (daily, weekly, monthly, or a number of days)
        start_time: When to send the first announcement (YYYY-MM-DD HH:MM). If not specified, starts tomorrow.

        """
        # Check if template exists
        templates = await self.config.guild(ctx.guild).templates()
        if template_name not in templates:
            return await ctx.send(f"Template `{template_name}` does not exist.")

        template = templates[template_name]
        template_type = template.get("type", "text")

        # Validate schedule type
        valid_types = ["daily", "weekly", "monthly"]
        if schedule_type.lower() not in valid_types:
            # Check if it's a number
            try:
                days = int(schedule_type)
                if days < 1 or days > MAX_CUSTOM_DAYS_INTERVAL:
                    return await ctx.send(f"Custom day interval must be between 1 and {MAX_CUSTOM_DAYS_INTERVAL} days.")
                schedule_type = str(days)  # Store as string for consistency
            except ValueError:
                return await ctx.send(f"Invalid schedule type. Must be one of: {', '.join(valid_types)}, or a number of days.")

        # Parse the start time if provided, otherwise default to tomorrow
        if start_time:
            try:
                # Add timezone if not specified
                if "T" not in start_time and " " in start_time:
                    start_time = start_time.replace(" ", "T")

                if "+" not in start_time and "-" not in start_time[-6:]:
                    start_time = f"{start_time}+00:00"

                scheduled_time = datetime.fromisoformat(start_time)

                # Check if time is in the past
                if scheduled_time < datetime.now(timezone.utc):
                    return await ctx.send("Cannot schedule announcements in the past.")
            except ValueError:
                return await ctx.send("Invalid date format. Please use YYYY-MM-DD HH:MM format.")
        else:
            # Default to tomorrow at current time
            scheduled_time = datetime.now(timezone.utc) + timedelta(days=1)

        # Get the channel to use
        channel_id = None
        if channel:
            channel_id = channel.id
        else:
            default_channel = await self.config.guild(ctx.guild).default_channel()
            if default_channel:
                channel_id = default_channel
                channel = ctx.guild.get_channel(default_channel)
            else:
                return await ctx.send("No default announcement channel set. Please specify a channel or set a default.")

        if not channel:
            return await ctx.send("The channel no longer exists.")

        # Generate ID for this recurring announcement
        recurring_id = str(int(datetime.now(timezone.utc).timestamp()))

        # Create the recurring announcement configuration
        recurrence = {
            "type": schedule_type.lower(),
            "template_name": template_name,
            "channel_id": channel_id,
            "created_by": ctx.author.id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # If it's a custom interval, add that
        if schedule_type.isdigit():
            recurrence["type"] = "custom"
            recurrence["interval"] = int(schedule_type)

        # Add to recurring list
        async with self.config.guild(ctx.guild).recurring() as recurring:
            recurring[recurring_id] = recurrence

        # Create the first scheduled instance
        announcement = {
            "type": template_type,
            "channel_id": channel_id,
            "template_name": template_name,
            "recurring_id": recurring_id,
            "time": scheduled_time.isoformat(),
            "scheduled_by": ctx.author.id,
            "scheduled_at": datetime.now(timezone.utc).isoformat()
        }

        # Add template-specific data
        if template_type == "embed":
            announcement["title"] = template.get("title", "")
            announcement["description"] = template.get("description", "")
            announcement["color"] = template.get("color", DEFAULT_COLOR)
        else:
            announcement["content"] = template.get("content", "")

        # Add to scheduled list
        async with self.config.guild(ctx.guild).scheduled() as scheduled:
            scheduled.append(announcement)

        # Format time for display
        local_time = scheduled_time.strftime("%Y-%m-%d %H:%M UTC")
        schedule_desc = schedule_type if schedule_type.lower() in valid_types else f"every {schedule_type} days"

        await ctx.send(f"Recurring announcement added using template `{template_name}`.\n"
                      f"• First announcement: {local_time}\n"
                      f"• Repeats: {schedule_desc}\n"
                      f"• Channel: {channel.mention}\n"
                      f"• ID: `{recurring_id}`")
        return True

    @announce_recurring.command(name="list")
    @commands.guild_only()
    async def recurring_list(self, ctx: commands.Context):
        """List all recurring announcements."""
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to view recurring announcements.")

        recurring = await self.config.guild(ctx.guild).recurring()
        if not recurring:
            return await ctx.send("No recurring announcements are set up.")

        # Create embed
        embed = discord.Embed(
            title="Recurring Announcements",
            description=f"Total: {len(recurring)} recurring announcements",
            color=DEFAULT_COLOR
        )

        # Add entries
        for recurring_id, data in recurring.items():
            # Get basic info
            template_name = data.get("template_name", "Unknown")
            schedule_type = data.get("type", "daily")
            channel_id = data.get("channel_id")
            channel = ctx.guild.get_channel(channel_id)
            channel_mention = channel.mention if channel else f"Unknown Channel ({channel_id})"

            # Format recurrence type
            if schedule_type == "custom":
                interval = data.get("interval", 1)
                recurrence = f"Every {interval} days"
            else:
                recurrence = f"{schedule_type.capitalize()}"

            # Create the field
            embed.add_field(
                name=f"Template: `{template_name}`",
                value=f"**Schedule:** {recurrence}\n"
                      f"**Channel:** {channel_mention}\n"
                      f"**ID:** `{recurring_id[:8]}...`",
                inline=True
            )

        # Add note about canceling
        embed.set_footer(text=f"Use {ctx.prefix}announce recurring remove <id> to remove a recurring announcement.")

        await ctx.send(embed=embed)
        return True

    @announce_recurring.command(name="remove")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def recurring_remove(self, ctx: commands.Context, recurring_id: str):
        """
        Remove a recurring announcement.

        Parameters
        ----------
        recurring_id: The ID of the recurring announcement to remove

        """
        # Find the full ID if partial ID was provided
        full_id = None
        recurring = await self.config.guild(ctx.guild).recurring()

        for rec_id in recurring:
            if rec_id.startswith(recurring_id):
                if full_id:
                    return await ctx.send("Multiple recurring announcements match that ID. Please provide more digits.")
                full_id = rec_id

        if not full_id:
            return await ctx.send("No recurring announcement found with that ID.")

        # Remove from recurring list
        async with self.config.guild(ctx.guild).recurring() as recurring:
            recurrence_data = recurring.pop(full_id, None)

        if not recurrence_data:
            return await ctx.send("Failed to remove recurring announcement.")

        # Remove future scheduled instances
        async with self.config.guild(ctx.guild).scheduled() as scheduled:
            # Find and remove all scheduled instances with this recurring ID
            scheduled_filtered = [a for a in scheduled if a.get("recurring_id") != full_id]
            removed_count = len(scheduled) - len(scheduled_filtered)

            # Update the list
            scheduled.clear()
            scheduled.extend(scheduled_filtered)

        template_name = recurrence_data.get("template_name", "unknown")
        await ctx.send(f"Removed recurring announcement for template `{template_name}` with ID `{full_id}`.\n"
                      f"Also removed {removed_count} scheduled future announcements.")
        return True

    # History commands
    @announce.group(name="history")
    @commands.guild_only()
    async def announce_history(self, ctx: commands.Context):
        """View announcement history."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @announce_history.command(name="list")
    @commands.guild_only()
    async def history_list(self, ctx: commands.Context, count: int = MIN_DISPLAY_COUNT):
        """
        List recent announcements.

        Parameters
        ----------
        count: Number of announcements to show (default 10, max 25)

        """
        if not await self._has_announce_permissions(ctx):
            return await ctx.send("You don't have permission to view announcement history.")

        if count < 1:
            count = MIN_DISPLAY_COUNT
        elif count > MAX_DISPLAY_COUNT:
            count = MAX_DISPLAY_COUNT

        history = await self.config.guild(ctx.guild).history()
        if not history:
            return await ctx.send("No announcements have been sent yet.")

        # Sort by sent time, most recent first
        history.sort(key=lambda x: x.get("sent_at", ""), reverse=True)

        # Create embed
        embed = discord.Embed(
            title="Recent Announcements",
            description=f"Showing {min(count, len(history))} of {len(history)} announcements",
            color=DEFAULT_COLOR
        )

        # Add entries
        for i, announcement in enumerate(history[:count]):
            # Get basic info
            announcement_type = announcement.get("type", "text")
            sent_time = datetime.fromisoformat(announcement.get("sent_at", datetime.now(timezone.utc).isoformat()))
            channel_id = announcement.get("channel_id")
            channel = ctx.guild.get_channel(channel_id)
            channel_mention = channel.mention if channel else f"Unknown Channel ({channel_id})"

            # Create title for the field
            if "template_name" in announcement:
                title = f"Template: `{announcement.get('template_name')}`"
            elif announcement_type == "embed":
                title = f"Embed: {announcement.get('title', 'No Title')[:20]}"
            else:
                title = "Text Announcement"

            # Format time
            local_time = sent_time.strftime("%Y-%m-%d %H:%M UTC")

            # Create description
            description = f"**Sent:** {local_time}\n**Channel:** {channel_mention}\n**Type:** {announcement_type.capitalize()}"

            embed.add_field(
                name=title,
                value=description,
                inline=(i % 2 == 0) # Alternate between inline and not
            )

        await ctx.send(embed=embed)
        return True

    @announce_history.command(name="clear")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def history_clear(self, ctx: commands.Context):
        """Clear the announcement history."""
        # Confirm
        history = await self.config.guild(ctx.guild).history()
        count = len(history)

        if not count:
            return await ctx.send("Announcement history is already empty.")

        confirm_msg = await ctx.send(f"Are you sure you want to clear {count} announcements from history? Reply with 'yes' to confirm.")

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.lower() == "yes"

        try:
            await self.bot.wait_for("message", check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await confirm_msg.edit(content="Clearing history cancelled.")

        # Clear the history
        await self.config.guild(ctx.guild).history.set([])

        await ctx.send(f"Cleared {count} announcements from history.")
        return True

    # Additional commands for scheduling, templates, and advanced functionality
    # will be added in future implementations.
