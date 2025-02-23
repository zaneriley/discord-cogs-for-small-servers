from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import TYPE_CHECKING

import discord
from PIL import Image

from utilities.discord_utils import fetch_user_avatar

if TYPE_CHECKING:
    from redbot.core import Config, commands

logger = logging.getLogger(__name__)


async def upload_avatar_as_emoji(
    guild: discord.Guild, user: discord.User, avatar_data: bytes, config: Config
) -> int | None:
    """
    Uploads a user's avatar as a guild emoji.
    """
    retry_attempts = 5
    backoff_delay = 2
    asset_exceeds_max_size = 50045
    http_status_rate_limited = 429
    max_size = 256  # Discord's maximum emoji size is 256x256 pixels

    allowed_role_ids = await config.get_raw("restrict_avatar_emojis_to_roles", default=None)
    allowed_roles = []
    if allowed_role_ids:
        for role_id in allowed_role_ids:
            role = guild.get_role(role_id)
            if role:
                allowed_roles.append(role)
            else:
                logger.warning(f"Role with ID {role_id} not found in the guild.")

    logger.info("Restricting avatar emojis to roles: %s", allowed_roles)

    image = Image.open(BytesIO(avatar_data))
    if image.size[0] > max_size or image.size[1] > max_size:
        image.thumbnail((max_size, max_size), Image.LANCZOS)
        with BytesIO() as output:
            image.save(output, format="PNG")
            avatar_data = output.getvalue()
    base_name = f"zzz_ui_avatar_{user.id}"
    emoji_name = base_name[:32] if len(base_name) > 32 else base_name.ljust(2, "_")

    existing_emoji = discord.utils.get(guild.emojis, name=emoji_name)

    for attempt in range(retry_attempts):
        try:
            if existing_emoji:
                await existing_emoji.delete()
            if allowed_roles:
                emoji = await guild.create_custom_emoji(name=emoji_name, image=avatar_data, roles=allowed_roles)
            else:
                emoji = await guild.create_custom_emoji(name=emoji_name, image=avatar_data)
        except discord.HTTPException as e:
            if e.code == asset_exceeds_max_size:
                logger.exception("Failed to upload avatar for %s", {user.display_name})
                raise
            if e.status == http_status_rate_limited:
                retry_after = int(e.response.headers.get("Retry-After", backoff_delay * (2**attempt)))
                logger.warning("Rate limited. Retrying in %s seconds", retry_after)
                await asyncio.sleep(retry_after)
            else:
                logger.exception("Failed to upload avatar for %s", {user.display_name})
                raise
        else:
            return emoji.id
    return None


async def update_avatar_emojis(bot, config):
    """
    Updates all user avatars as emojis in the specified guild and returns a mapping of user IDs to emoji IDs.
    """
    guild_id = await config.guild_id()
    guild = bot.get_guild(guild_id)
    if not guild:
        no_guild_msg = f"Guild with ID {guild_id} not found."
        raise ValueError(no_guild_msg)
    emoji_mapping = {}
    asset_exceeds_max_size = 50045
    for member in guild.members:
        try:
            avatar_data = await fetch_user_avatar(member)
            emoji_id = await upload_avatar_as_emoji(guild, member, avatar_data, config)
            emoji_mapping[member.id] = emoji_id
            await config.user(member).set_raw("emoji_id", value=emoji_id)
        except discord.HTTPException as e:
            if e.code == asset_exceeds_max_size:
                logger.exception("Failed to upload avatar for %s", {member.display_name})
                raise
            logger.exception("Failed to update avatar for %s", {member.display_name})
            raise
        except Exception:
            logger.exception("Failed to update avatar for %s", {member.display_name})
            raise
    return emoji_mapping


async def get_user_emoji(user: discord.User, config: Config, ctx: commands.Context) -> discord.Emoji | None:
    """
    Retrieves the stored emoji ID for a user.
    """
    emoji_id = await config.user(user).get_raw("emoji_id", default=None)
    if emoji_id:
        guild_id = await config.guild_id()
        guild = ctx.guild
        if guild is None:
            logger.error(f"Failed to find guild with ID {guild_id}")
            return None
        emoji = guild.get_emoji(emoji_id)
        if emoji:
            return emoji
        # This returns a blank emoji from our server. You'll likely need
        # to use your own default emoji instead if you want to update this.
    return discord.PartialEmoji(name="ui_blank", id=1244497311246192650)


def react_with_confidant_emojis(func):
    async def wrapper(self, ctx, *args, **kwargs):
        message = await func(self, ctx, *args, **kwargs)
        if isinstance(message, discord.Message):
            user_data = await self.config.user(ctx.author).all()
            for confidant_id in user_data.get("scores", {}):
                emoji = await self.confidants_manager.get_user_emoji(discord.Object(id=int(confidant_id)))
                if emoji:
                    try:
                        await message.add_reaction(emoji)
                    except discord.HTTPException as e:
                        logger.exception(f"Failed to add reaction for confidant {confidant_id}: {e!s}")
        return message

    return wrapper
