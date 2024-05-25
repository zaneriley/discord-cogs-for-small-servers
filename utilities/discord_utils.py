import logging
import os
from collections.abc import Callable

import aiohttp
import discord
from discord import ForumTag, HTTPException, NotFound, TextChannel
from discord.ext.commands import Context
from discord.ui import Item, Modal, View

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
        logger.error(f"Channel {channel_id} not found. Context: {ctx}")
    except HTTPException:
        await ctx.send(THREAD_CREATION_ERROR)
        logger.error(f"HTTPException while creating thread in channel {channel_id}.")
    except AttributeError as ae:
        logger.error(f"AttributeError: {ae}. Object: {thread}")
    except Exception as e:
        logger.error(f"Unexpected error creating thread in channel {channel_id}: {e} Thread object: {thread}")
        await ctx.send(THREAD_CREATION_ERROR)


SEND_MESSAGE_ERROR = "An error occurred while sending the message."
ROLE_NOT_FOUND_ERROR = "The provided role ID was not found."
CHANNEL_TYPE_ERROR = "Provided channel is not a text channel."


async def send_discord_message(
    ctx: Context, channel_id: int, message_content: str, role_id: int | None = None
) -> str:
    """
    Sends a scheduled message to a specified channel.
    If a role_id is provided, it mentions the role in the message.
    :param ctx: Command context
    :param channel_id: The ID of the channel to send the message to
    :param message_content: The content of the message
    :param role_id: The ID of the role to mention, optional
    :return: Status message
    """
    channel = ctx.guild.get_channel(channel_id)
    if not channel:
        await ctx.send("Invalid channel ID or channel not found.")
        return "Invalid channel ID."

    if not isinstance(channel, TextChannel):
        await ctx.send(CHANNEL_TYPE_ERROR)
        return CHANNEL_TYPE_ERROR

    # Preparing Message
    if role_id:
        role = ctx.guild.get_role(role_id)
        if not role:
            await ctx.send(ROLE_NOT_FOUND_ERROR)
            return ROLE_NOT_FOUND_ERROR
        role_mention = f"<@&{role_id}>"
        message_content = f"{role_mention}\n{message_content}"

    # Sending Message
    try:
        await channel.send(message_content)
    except HTTPException:
        await ctx.send(SEND_MESSAGE_ERROR)
        logger.exception("HTTPException while sending message to channel %s", {channel.id})
        return SEND_MESSAGE_ERROR
    except Exception:
        logger.exception("Unexpected error sending message to channel %s", {channel.id})
        await ctx.send(SEND_MESSAGE_ERROR)
        return SEND_MESSAGE_ERROR
    else:
        return "Message sent successfully."


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
                raise ValueError("Too many items provided for the modal.")
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
        logger.error(f"HTTP error while creating modal {custom_id}: {http_err}")
        if on_error_callback:
            await on_error_callback(ctx, http_err)
        return None
    except ValueError as val_err:
        logger.error(f"Value error while creating modal {custom_id}: {val_err}")
        if on_error_callback:
            await on_error_callback(ctx, val_err)
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating modal {custom_id}: {e}")
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
                else:
                    logger.error(f"Failed to fetch guild banner: HTTP {response.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Client error occurred while fetching the guild banner: {e}")
        return None
    except Exception as e:
        logger.error(f"General error fetching guild banner: {e}")
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
