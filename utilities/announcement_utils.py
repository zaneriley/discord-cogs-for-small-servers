from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import discord

# Import local utilities
from .discord_utils import send_discord_message

# Set up logger
logger = logging.getLogger("red.seasonalroles.announcement_utils")

# Constants
DEFAULT_COLOR = 0x7289DA  # Discord Blurple
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30  # seconds
BACKOFF_DELAY = 2  # seconds
HTTP_STATUS_RATE_LIMITED = 429

# Holiday styling constants
HOLIDAY_STYLES = {
    "christmas": {
        "before": {
            "color": 0xCC0000,  # Christmas Red
            "footer_text": "Christmas is coming!",
            "thumbnail_url": "https://i.imgur.com/ZDgirZT.png"  # Advent wreath
        },
        "during": {
            "color": 0x00AA00,  # Christmas Green
            "footer_text": "Merry Christmas!",
            "thumbnail_url": "https://i.imgur.com/8EPlgB0.png"  # Christmas tree
        },
        "after": {
            "color": 0x87CEEB,  # Sky Blue (winter)
            "footer_text": "Happy New Year!",
            "thumbnail_url": "https://i.imgur.com/pXHMGV8.png"  # Fireworks
        }
    },
    "halloween": {
        "before": {
            "color": 0xFFA500,  # Orange
            "footer_text": "Halloween is coming!",
            "thumbnail_url": "https://i.imgur.com/9nZTwZN.png"  # Pumpkin patch
        },
        "during": {
            "color": 0x663399,  # Purple
            "footer_text": "Happy Halloween!",
            "thumbnail_url": "https://i.imgur.com/JdgQVcN.png"  # Jack-o-lantern
        },
        "after": {
            "color": 0x8B4513,  # Brown (autumn)
            "footer_text": "Hope you had a great Halloween!",
            "thumbnail_url": "https://i.imgur.com/HPkRFVR.png"  # Fall leaves
        }
    }
    # Add more holidays as needed
}

async def validate_channel(
    bot: discord.Client,
    channel_id: int
) -> tuple[bool, str | None]:
    """
    Validates if a channel exists and if the bot has permission to send messages to it.

    Args:
        bot: The Discord bot client
        channel_id: The ID of the channel to validate

    Returns:
        A tuple containing (success, error_message)
        If successful, error_message will be None

    """
    error_msg = None

    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.NotFound:
                error_msg = f"Channel with ID {channel_id} not found"
            except discord.Forbidden:
                error_msg = f"Bot does not have permission to access channel {channel_id}"
            except discord.HTTPException as e:
                logger.exception("HTTP error when fetching channel")
                error_msg = f"Error fetching channel: {e!s}"

        if not error_msg and not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            error_msg = f"Channel {channel_id} is not a text channel, thread, or voice channel"

        if not error_msg:
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages:
                error_msg = f"Bot does not have permission to send messages in channel {channel_id}"
            elif not permissions.embed_links:
                error_msg = f"Bot does not have permission to embed links in channel {channel_id}"
    except Exception as e:
        logger.exception("Unexpected error validating channel")
        error_msg = f"Unexpected error: {e!s}"

    return (error_msg is None), error_msg

def get_mention_string(mention_type: str | None, mention_id: int | None) -> str:
    """
    Returns the appropriate mention string based on the mention type.

    Args:
        mention_type: The type of mention (can be 'everyone', 'here', 'role', 'user', or None)
        mention_id: The ID of the role or user to mention (only used when mention_type is 'role' or 'user')

    Returns:
        A string containing the appropriate mention text

    """
    if mention_type is None:
        return ""

    if mention_type.lower() == "everyone":
        return "@everyone"

    if mention_type.lower() == "here":
        return "@here"

    if mention_type.lower() == "role" and mention_id is not None:
        return f"<@&{mention_id}>"

    if mention_type.lower() == "user" and mention_id is not None:
        return f"<@{mention_id}>"

    # Default case if no conditions are met
    return ""

async def send_text_announcement(
    bot: discord.Client,
    channel_id: int,
    content: str,
    mention_type: str | None = None,
    mention_id: int | None = None,
    **kwargs
) -> tuple[bool, str | None]:
    """
    Sends a simple text announcement to a channel.

    Args:
        bot: The Discord bot client
        channel_id: The ID of the channel to send the announcement to
        content: The text content of the announcement
        mention_type: Optional, the type of mention (can be 'everyone', 'here', 'role', 'user', or None)
        mention_id: Optional, the ID of the role or user to mention
        **kwargs: Additional keyword arguments to pass to send_discord_message

    Returns:
        A tuple containing (success, error_message)
        If successful, error_message will be None

    """
    # Validate channel first
    valid, error = await validate_channel(bot, channel_id)
    if not valid:
        return False, error

    # Get the mention string if applicable
    mention = get_mention_string(mention_type, mention_id)

    # Combine mention and content if needed
    full_content = f"{mention}\n{content}" if mention else content

    # Send the message with rate limit protection
    for attempt in range(MAX_RETRIES):
        try:
            # Pass message_content parameter but don't pass embed since this is a text announcement
            success = await send_discord_message(
                bot, 
                channel_id, 
                message_content=full_content,
                role_id=mention_id if mention_type == "role" else None
            )
            if success:
                return True, None
            return False, "Failed to send message"  # noqa: TRY300
        except discord.HTTPException as e:
            if e.status == HTTP_STATUS_RATE_LIMITED:
                retry_after = int(e.response.headers.get("Retry-After", BACKOFF_DELAY * (2**attempt)))
                logger.warning("Rate limited. Retrying in %s seconds", retry_after)
                await asyncio.sleep(retry_after)
                # Continue the loop to retry
                if attempt == MAX_RETRIES - 1:
                    return False, f"Rate limited: Could not send message after {MAX_RETRIES} attempts"
            else:
                logger.exception("HTTP error sending text announcement to channel")
                return False, f"HTTP error sending announcement: {e!s}"
        except Exception as e:
            logger.exception("Error sending text announcement to channel")
            return False, f"Error sending announcement: {e!s}"

    # If we've exhausted all retries (though this should be handled in the loop)
    return False, f"Failed to send message after {MAX_RETRIES} attempts"

# Type alias for configuration parameters
EmbedParams = dict[str, Any]

async def create_embed_announcement(embed_config: EmbedParams) -> discord.Embed:
    """
    Creates a rich embed for announcements.

    Args:
        embed_config: Dictionary containing embed configuration with the following keys:
            - title: The title of the embed
            - description: The main text content of the embed
            - color: Optional, the color of the embed (default: Discord Blurple)
            - timestamp: Optional, whether to include a timestamp (default: True)
            - footer: Optional, dict with 'text' and optional 'icon_url' keys
            - thumbnail_url: Optional, URL of the thumbnail image
            - image_url: Optional, URL of the main image
            - author_name: Optional, name to display in the author field
            - author_icon_url: Optional, URL of the author icon
            - author_url: Optional, URL for the author name to link to
            - fields: Optional, list of field dictionaries with 'name', 'value', and 'inline' keys

    Returns:
        A Discord Embed object ready to be sent

    """
    logger.debug(f"Creating embed with config keys: {list(embed_config.keys())}")
    
    # Extract and log basic embed parameters
    title = embed_config.get("title", "")
    description = embed_config.get("description", "")
    color = embed_config.get("color", DEFAULT_COLOR)
    
    logger.debug(f"Basic embed parameters:")
    logger.debug(f"- Title: {title}")
    logger.debug(f"- Description: {description}")
    logger.debug(f"- Color: {color}")

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    # Add timestamp if requested
    if embed_config.get("timestamp", True):
        embed.timestamp = datetime.now(timezone.utc)
        logger.debug("Added timestamp to embed")

    # Add footer if provided
    footer = embed_config.get("footer", {})
    if isinstance(footer, dict) and "text" in footer:
        footer_text = footer["text"]
        footer_icon = footer.get("icon_url")
        logger.debug(f"Setting footer - Text: {footer_text}, Icon URL: {footer_icon}")
        embed.set_footer(text=footer_text, icon_url=footer_icon)
    elif isinstance(footer, str):
        # Handle legacy string footer
        logger.debug(f"Setting legacy string footer: {footer}")
        embed.set_footer(text=footer)
    else:
        logger.debug("No valid footer configuration found")

    # Add thumbnail if provided
    thumbnail_url = embed_config.get("thumbnail_url")
    if thumbnail_url:
        logger.debug(f"Setting thumbnail URL: {thumbnail_url}")
        embed.set_thumbnail(url=thumbnail_url)

    # Add main image if provided
    image_url = embed_config.get("image_url")
    if image_url:
        logger.debug(f"Setting main image URL: {image_url}")
        embed.set_image(url=image_url)

    # Add author if provided
    author_name = embed_config.get("author_name")
    if author_name:
        author_icon = embed_config.get("author_icon_url")
        author_url = embed_config.get("author_url")
        logger.debug(f"Setting author - Name: {author_name}, Icon URL: {author_icon}, URL: {author_url}")
        embed.set_author(name=author_name, icon_url=author_icon, url=author_url)

    # Add fields if provided
    fields = embed_config.get("fields", [])
    if fields:
        logger.debug(f"Adding {len(fields)} fields to embed")
        for field in fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", True)
            )

    logger.debug("Embed creation complete")
    return embed

# Type alias for announcement configuration
AnnouncementConfig = dict[str, Any]

async def send_embed_announcement(
    bot: discord.Client,
    channel_id: int,
    config: dict[str, Any],
    **kwargs
) -> tuple[bool, str | None]:
    """
    Sends a rich embed announcement to a channel.

    Args:
        bot: The Discord bot client
        channel_id: The ID of the channel to send the announcement to
        config: Dictionary containing announcement configuration with the following keys:
            - embed_params: Dictionary of parameters for creating the embed (see create_embed_announcement)
            - content: Optional, text content to include with the embed
            - mention_type: Optional, the type of mention
            - mention_id: Optional, the ID of the role or user to mention
        **kwargs: Additional keyword arguments to pass to send_discord_message

    Returns:
        A tuple containing (success, error_message)
        If successful, error_message will be None

    """
    # Validate channel first
    valid, error = await validate_channel(bot, channel_id)
    if not valid:
        return False, error

    # Extract parameters from config
    embed_params = config.get("embed_params", {})
    content = config.get("content")
    mention_type = config.get("mention_type")
    mention_id = config.get("mention_id")

    # Get the mention string if applicable
    mention = get_mention_string(mention_type, mention_id)

    # Combine mention and content if needed
    full_content = ""
    if mention and content:
        full_content = f"{mention}\n{content}"
    elif mention:
        full_content = mention
    elif content:
        full_content = content

    # Create the embed
    try:
        embed = await create_embed_announcement(embed_params)

        # Send the message with the embed, with rate limit protection
        for attempt in range(MAX_RETRIES):
            try:
                # Pass both the message content and the embed
                success = await send_discord_message(
                    bot, 
                    channel_id, 
                    message_content=full_content if full_content else "",
                    role_id=config.get("mention_id") if config.get("mention_type") == "role" else None,
                    embed=embed  # Pass the embed we created
                )
                if success:
                    return True, None
                return False, "Failed to send message"  # noqa: TRY300
            except discord.HTTPException as e:
                if e.status == HTTP_STATUS_RATE_LIMITED:
                    retry_after = int(e.response.headers.get("Retry-After", BACKOFF_DELAY * (2**attempt)))
                    logger.warning("Rate limited. Retrying in %s seconds", retry_after)
                    await asyncio.sleep(retry_after)
                    # Continue the loop to retry
                    if attempt == MAX_RETRIES - 1:
                        return False, f"Rate limited: Could not send message after {MAX_RETRIES} attempts"
                else:
                    logger.exception("HTTP error sending embed announcement to channel")
                    return False, f"HTTP error sending announcement: {e!s}"
            except Exception as e:
                logger.exception("Error sending embed announcement to channel")
                return False, f"Error sending announcement: {e!s}"

        # If we've exhausted all retries (though this should be handled in the loop)
        return False, f"Failed to send message after {MAX_RETRIES} attempts"
    except Exception as e:
        logger.exception("Error creating or sending embed announcement")
        return False, f"Error preparing announcement: {e!s}"

# Type alias for holiday announcement parameters
HolidayAnnouncementParams = dict[str, Any]

def apply_holiday_styling(
    holiday_name: str,
    phase: str,
    params: HolidayAnnouncementParams
) -> HolidayAnnouncementParams:
    """
    Apply holiday-specific styling to announcement parameters.

    Args:
        holiday_name: The name of the holiday
        phase: The phase of the holiday ("before", "during", or "after")
        params: The original announcement parameters

    Returns:
        The updated announcement parameters with holiday styling applied

    """
    holiday_lower = holiday_name.lower()
    phase_lower = phase.lower()

    # Create a copy of the params to avoid modifying the original
    result = params.copy()

    # Get holiday styles if available
    if holiday_lower in HOLIDAY_STYLES and phase_lower in HOLIDAY_STYLES[holiday_lower]:
        styles = HOLIDAY_STYLES[holiday_lower][phase_lower]

        # Apply styling, preserving any existing values in params
        for key, value in styles.items():
            if key not in result or result[key] is None:
                result[key] = value

    return result

async def send_holiday_announcement(
    bot: discord.Client,
    channel_id: int,
    config: AnnouncementConfig
) -> tuple[bool, str | None]:
    """
    Sends a holiday-specific announcement with appropriate styling.

    Args:
        bot: The Discord bot client
        channel_id: The ID of the channel to send the announcement to
        config: Dictionary containing announcement configuration with the following keys:
            - holiday_name: The name of the holiday
            - phase: The phase of the holiday ("before", "during", or "after")
            - embed_params: Dictionary of parameters for creating the announcement
            - content: Optional, text content to include with the embed
            - mention_type: Optional, the type of mention
            - mention_id: Optional, the ID of the role or user to mention
            - **kwargs: Additional keyword arguments to pass to send_discord_message

    Returns:
        A tuple containing (success, error_message)
        If successful, error_message will be None

    """
    # Extract parameters from config
    holiday_name = config.get("holiday_name", "")
    phase = config.get("phase", "during")
    announcement_params = config.get("embed_params", {})

    # Apply holiday-specific styling
    styled_params = apply_holiday_styling(holiday_name, phase, announcement_params)

    # Prepare the configuration for send_embed_announcement
    embed_config = config.copy()
    embed_config["embed_params"] = styled_params

    # Send the styled announcement
    return await send_embed_announcement(
        bot,
        channel_id,
        embed_config
    )

async def preview_announcement(
    user: discord.User | discord.Member,
    config: dict[str, Any],
    announcement_type: str = "text",
    *,
    is_holiday: bool = False
) -> tuple[bool, str | None]:
    """
    Sends a preview of an announcement to a user's DM.

    Args:
        user: The user to receive the preview
        config: Dictionary containing announcement configuration
        announcement_type: The type of announcement ("text", "embed", or "holiday")
        is_holiday: Whether this is a holiday announcement

    Returns:
        A tuple containing (success, error_message)
        If successful, error_message will be None

    """
    try:
        # Create a deep copy of the config to avoid modifying the original
        preview_config = config.copy()

        # Add a preview header to the message
        if announcement_type == "text":
            original_content = preview_config.get("content", "")
            preview_config["content"] = original_content
        elif "embed_params" in preview_config:
            # Add preview notice to embed title
            embed_params = preview_config.get("embed_params", {})
            original_title = embed_params.get("title", "")
            embed_params["title"] = original_title

            # Add footer note
            footer_text = embed_params.get("footer_text", "")
            embed_params["footer_text"] = f"{footer_text} | This is a preview" if footer_text else "This is a preview"

            preview_config["embed_params"] = embed_params

        # Try to send a DM to the user
        try:
            dm_channel = await user.create_dm()

            # Send the appropriate type of preview
            if announcement_type == "text":
                content = preview_config.get("content", "")
                await dm_channel.send(content)
            elif announcement_type == "embed" or (is_holiday and announcement_type == "holiday"):
                # Create the embed
                if is_holiday:
                    holiday_name = preview_config.get("holiday_name", "")
                    phase = preview_config.get("phase", "during")
                    embed_params = preview_config.get("embed_params", {})
                    styled_params = apply_holiday_styling(holiday_name, phase, embed_params)
                    preview_config["embed_params"] = styled_params

                embed = await create_embed_announcement(preview_config.get("embed_params", {}))
                content = preview_config.get("content")
                await dm_channel.send(content=content, embed=embed)

            return True, "Preview sent to your DMs. Check your direct messages."
        except discord.Forbidden:
            return False, "Could not send preview. Please make sure you have DMs enabled from server members."
        except Exception as e:
            logger.exception("Error sending preview DM")
            return False, f"Error sending preview: {e!s}"
    except Exception as e:
        logger.exception("Error preparing announcement preview")
        return False, f"Error preparing preview: {e!s}"
