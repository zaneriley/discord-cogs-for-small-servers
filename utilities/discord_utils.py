from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Union, Optional

import aiofiles
import aiohttp
import discord
from discord import ForumTag, HTTPException, NotFound, TextChannel
from discord.ui import Item, Modal, View

from utilities.image_utils import get_image_handler
from redbot.core.bot import Red

if TYPE_CHECKING:
    from collections.abc import Callable

    from discord.ext.commands import Context

logger = logging.getLogger(__name__)

DEFAULT_THREAD_NAME = "Hello World Thread"
DEFAULT_THREAD_MESSAGE = "This is the first message in the thread."
THREAD_CREATION_ERROR = "An error occurred while creating the thread."


async def is_server_owner(bot, user_id: int) -> bool:
    """
    Checks if the given user ID belongs to a server owner.

    Args:
    ----
        bot: The bot instance.
        user_id: The ID of the user to check.

    Returns:
    -------
        True if the user is a server owner, False otherwise.

    """
    user = await bot.fetch_user(user_id)
    if user.bot:
        return False

    return any(guild.owner_id == user_id for guild in bot.guilds)


async def create_discord_thread(
    ctx: Context,
    channel_id: int,
    thread_name: str = DEFAULT_THREAD_NAME,
    thread_content: str = DEFAULT_THREAD_MESSAGE,
    tags: list[ForumTag] | None = None,
) -> None:
    """
    Create a thread in the specified Discord channel.

    :param ctx: Command context
    :param channel_id: ID of the Discord channel
    :param thread_name: Name of the thread to be created
    :param thread_content: Initial message for the thread
    :param tags: List of tags to be added to the thread
    """
    logger.info(f"Entering create_discord_thread with context: {ctx}, channel_id: {channel_id}")
    logger.debug(f"Type of ctx: {type(ctx)}, Type of channel_id: {type(channel_id)}")
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.send("Invalid channel ID or not a text channel.")
        return

    try:
        thread = await channel.create_thread(name=thread_name, content=thread_content)
        await thread.send(thread_content)  # Send the message to the thread

        # Debug log to print attributes of the ThreadWithMessage object
        logger.debug(f"Attributes of ThreadWithMessage object: {dir(thread)}")

        logger.info(f"Created thread {thread} in channel {channel_id}.")
        logger.debug(f"Type of thread: {type(thread)}")
        logger.debug(f"thread.id: {thread.id}, thread.name: {thread.name}, thread.content: {thread.content}")

        # Get the "Movie Club" tag
        movie_club_tag = None
        for tag in channel.available_tags:
            if tag.name == "Movie Club":
                movie_club_tag = tag
                break

        # If the tag was found, apply it to the thread
        if movie_club_tag:
            await thread.edit(applied_tags=[movie_club_tag])
        else:
            logger.warning(f"'Movie Club' tag not found in channel {channel_id}.")

        # If there are additional tags, apply them as well
        if tags:
            for tag in tags:
                await thread.add_tag(tag)

    except NotFound:
        await ctx.send("Channel not found.")
        logger.exception(f"Channel {channel_id} not found. Context: {ctx}")
    except HTTPException:
        await ctx.send(THREAD_CREATION_ERROR)
        logger.exception(f"HTTPException while creating thread in channel {channel_id}.")
    except AttributeError as ae:
        logger.exception(f"AttributeError: {ae}. Object: {thread}")
    except Exception as e:
        logger.exception(f"Unexpected error creating thread in channel {channel_id}: {e} Thread object: {thread}")
        await ctx.send(THREAD_CREATION_ERROR)


SEND_MESSAGE_ERROR = "An error occurred while sending the message."
ROLE_NOT_FOUND_ERROR = "The provided role ID was not found."
CHANNEL_TYPE_ERROR = "Provided channel is not a text channel."


async def send_discord_message(
    bot_or_ctx: Union[Context, Red], 
    channel_id: int, 
    message_content: str = "",
    role_id: Optional[int] = None,
    embed: Optional[discord.Embed] = None  # Add embed parameter
) -> str:
    """
    Sends a message to a specified channel with optional embed and role mention.
    
    Args:
        bot_or_ctx: Discord bot or command context
        channel_id: The ID of the channel to send the message to
        message_content: The text content of the message (optional)
        role_id: The ID of the role to mention (optional)
        embed: A Discord Embed object to include (optional)
        
    Returns:
        A status message string indicating success or failure
    """
    # Determine if we have a Context or a Bot
    is_context = hasattr(bot_or_ctx, 'guild')
    
    # Get the channel based on what we're working with
    if is_context:
        ctx = bot_or_ctx
        channel = ctx.guild.get_channel(channel_id)
    else:
        bot = bot_or_ctx
        channel = bot.get_channel(channel_id)
        
        # If channel not found, try fetching it
        if not channel:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.NotFound:
                return "Invalid channel ID."
            except discord.Forbidden:
                return "Bot does not have permission to access channel."
            except Exception as e:
                logger.exception("Error fetching channel")
                return f"Error accessing channel: {str(e)}"

    if not channel:
        if is_context:
            await ctx.send("Invalid channel ID or channel not found.")
        return "Invalid channel ID."

    # Check if channel is proper type
    if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
        if is_context:
            await ctx.send(CHANNEL_TYPE_ERROR)
        return CHANNEL_TYPE_ERROR

    # Add role mention if needed
    content = message_content
    if role_id:
        guild = channel.guild
        role = guild.get_role(role_id)
        if not role:
            if is_context:
                await ctx.send(ROLE_NOT_FOUND_ERROR)
            return ROLE_NOT_FOUND_ERROR
        
        # Add role mention to content
        content = f"<@&{role_id}>\n{content}" if content else f"<@&{role_id}>"

    # Ensure we have either content or embed (Discord requires at least one)
    if not content and not embed:
        return "Cannot send an empty message. Provide content or embed."
        
    # Send the message - using Discord's API directly with proper parameters
    try:
        await channel.send(content=content, embed=embed)
        return "Message sent successfully."
    except discord.HTTPException as e:
        error_msg = f"HTTP error sending message: {str(e)}"
        if is_context:
            await ctx.send(SEND_MESSAGE_ERROR)
        logger.exception(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error sending message: {str(e)}"
        if is_context:
            await ctx.send(SEND_MESSAGE_ERROR)
        logger.exception(error_msg)
        return error_msg


MAX_ITEMS_LIMIT = 25  # Define a constant for the maximum number of items


async def create_discord_modal(
    ctx: Context,
    title: str,
    items: list[Item] | None = None,
    timeout: float | None = None,
    custom_id: str | None = None,
    wait_for_interaction: bool = False,
    on_submit_callback: Callable[[Context], None] | None = None,
    on_error_callback: Callable[[Context, Exception], None] | None = None,
) -> Modal | None:
    """
    Create and display a Discord modal.

    :param ctx: Command context
    :param title: Title of the modal
    :param items: List of UI items to add to the modal
    :param timeout: Timeout for the modal
    :param custom_id: Custom ID for the modal
    :param wait_for_interaction: Whether to wait for user interaction
    :param on_submit_callback: Custom callback for modal submission
    :param on_error_callback: Custom callback for errors
    :return: The modal instance or None if there's an error
    """
    logger.debug(f"Attempting to create modal with custom_id: {custom_id}")

    try:
        # Initialize the modal
        modal = Modal(title=title, timeout=timeout, custom_id=custom_id)
        logger.debug(f"Modal initialized with title: {title}")

        # Add items to the modal with validation
        if items:
            if len(items) > MAX_ITEMS_LIMIT:
                logger.error(f"Too many items provided for modal with custom_id: {custom_id}")
                msg = "Too many items provided for the modal."
                raise ValueError(msg)
            for item in items:
                modal.add_item(item)
            logger.debug(f"{len(items)} items added to modal with custom_id: {custom_id}")

        # Define or set callbacks
        if on_submit_callback:
            modal.on_submit = on_submit_callback
        if on_error_callback:
            modal.on_error = on_error_callback

        # Display the modal
        await ctx.response.send_modal(modal)
        logger.debug(f"Modal with custom_id: {custom_id} displayed to user.")

        # Optionally wait for interaction
        if wait_for_interaction:
            await modal.wait()
            logger.debug(f"Interaction completed for modal with custom_id: {custom_id}")

        return modal

    except HTTPException as http_err:
        logger.exception(f"HTTP error while creating modal {custom_id}: {http_err}")
        if on_error_callback:
            await on_error_callback(ctx, http_err)
        return None
    except ValueError as val_err:
        logger.exception(f"Value error while creating modal {custom_id}: {val_err}")
        if on_error_callback:
            await on_error_callback(ctx, val_err)
        return None
    except Exception as e:
        logger.exception(f"Unexpected error creating modal {custom_id}: {e}")
        if on_error_callback:
            await on_error_callback(ctx, e)
        return None


async def fetch_and_save_guild_banner(guild, save_path):
    if guild.banner is None:
        logger.error("Guild does not have a banner.")
        return None

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    logger.info(f"os.path.dirname(save_path): {os.path.dirname(save_path)}")
    banner_url = str(guild.banner)  # Ensure the URL is a string
    logger.info(f"Guild: {guild} \n Banner URL: {banner_url} \n Save path: {save_path}")

    try:
        # Validate the URL format (simple check)
        if not banner_url.startswith("http"):
            logger.error("Invalid URL format.")
            return None

        # Ensure the session is properly managed with async with
        async with aiohttp.ClientSession() as session:
            async with session.get(banner_url) as response:
                if response.status == 200:
                    with open(save_path, "wb") as f:
                        f.write(await response.read())
                    logger.info(f"Banner successfully saved to {save_path}")
                    return save_path
                logger.error(f"Failed to fetch guild banner: HTTP {response.status}")
                return None
    except aiohttp.ClientError as e:
        logger.exception(f"Client error occurred while fetching the guild banner: {e}")
        return None
    except Exception as e:
        logger.exception(f"General error fetching guild banner: {e}")
        return None


async def restore_guild_banner(guild, file_path, *, delete_after_restore=False):
    """Restores the guild's banner from a saved file."""
    try:
        async with aiofiles.open(file_path, "rb") as file:
            image_data = await file.read()
        await guild.edit(banner=image_data)
        logger.info("Guild banner restored successfully.")
        if delete_after_restore:
            os.remove(file_path)
            logger.info(f"Banner file {file_path} deleted after restoration.")
    except FileNotFoundError:
        logger.exception("Banner file not found.")
    except Exception:
        logger.exception("Failed to restore guild banner:")
        raise


async def fetch_user_avatar(user):
    """
    Fetches the avatar for a user.
    """
    http_ok = 200
    avatar_url = user.display_avatar.url
    async with aiohttp.ClientSession() as session, session.get(avatar_url) as response:
        if response.status == http_ok:
            return await response.read()

        logger.exception("Failed to download avatar from: %s", avatar_url)
        return None


async def create_or_update_role(guild: discord.Guild, role_name: str, image_source: str):
    # Fetch the role if it exists
    role = discord.utils.get(guild.roles, name=role_name)

    # Fetch image data for the role icon
    image_handler = get_image_handler(image_source)
    image_data = await image_handler.fetch_image_data()

    if role:
        # If the role exists, update it with the new icon
        try:
            await role.edit(display_icon=image_data, reason="Updating role icon")
            logger.info("Updated role %s with new icon.", role.name)
        except discord.Forbidden:
            logger.exception("Bot does not have permission to edit roles.")
        except discord.HTTPException:
            logger.exception("Failed to edit role:")
    else:
        # If the role does not exist, create it with the icon
        try:
            role = await guild.create_role(
                name=role_name, display_icon=image_data, reason="Creating new role with icon"
            )
            logger.info("Created new role %s with a new icon.", role.name)
        except discord.Forbidden:
            logger.exception("Bot does not have permission to create roles.")
        except discord.HTTPException:
            logger.exception("Failed to create role:")


class PaginatorView(View):
    def __init__(self, pages, timeout=180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        self.back_button = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.primary)
        self.page_button = discord.ui.Button(
            label=f"{self.current_page + 1} of {len(self.pages)}", style=discord.ButtonStyle.secondary, disabled=True
        )
        self.forward_button = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.primary)
        self.back_button.callback = self.previous_button_callback
        self.forward_button.callback = self.next_button_callback
        self.add_item(self.back_button)
        self.add_item(self.page_button)
        self.add_item(self.forward_button)
        self.update_buttons()
        logger.info("Paginator initialized with %d pages", len(self.pages))

    async def previous_button_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            logger.debug("Previous button pressed on page %d", self.current_page + 1)
            self.current_page -= 1
            logger.debug("Moving to previous page %d", self.current_page + 1)
            self.update_buttons()
            await interaction.response.edit_message(content=self.pages[self.current_page], view=self)
            logger.debug("Edit message call completed")  # Log after the call
        else:
            logger.debug("Already on the first page")

    async def next_button_callback(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            logger.debug("Next button pressed on page %d", self.current_page + 1)
            self.current_page += 1
            logger.debug("Moving to next page %d", self.current_page + 1)
            self.update_buttons()
            await interaction.response.edit_message(content=self.pages[self.current_page], view=self)
            logger.debug("Edit message call completed")  # Log after the call
        else:
            logger.debug("Already on the last page")

    def update_buttons(self):
        self.page_button.label = f"{self.current_page + 1} of {len(self.pages)}"
        self.back_button.disabled = self.current_page == 0
        self.forward_button.disabled = self.current_page == len(self.pages) - 1

        logger.debug(
            "Button states updated. Back: %s, Page: %s, Forward: %s",
            "disabled" if self.back_button.disabled else "enabled",
            self.page_button.label,
            "disabled" if self.forward_button.disabled else "enabled",
        )

    async def on_timeout(self):
        # remove buttons on timeout
        message = await self.interaction.original_response()
        await message.edit(view=None)
