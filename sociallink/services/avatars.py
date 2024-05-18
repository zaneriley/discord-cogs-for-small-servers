import asyncio
import logging
from io import BytesIO

import aiohttp
import discord
from PIL import Image

logger = logging.getLogger(__name__)


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


async def upload_avatar_as_emoji(guild, user, avatar_data):
    """
    Uploads a user's avatar as a guild emoji.
    """
    retry_attempts = 5
    backoff_delay = 2
    asset_exceeds_max_size = 50045
    http_status_rate_limited = 429
    max_size = 256  # Discord's maximum emoji size is 256x256 pixels

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
            emoji = await guild.create_custom_emoji(name=emoji_name, image=avatar_data)
        except discord.HTTPException as e:
            if e.code == asset_exceeds_max_size:
                logger.exception("Failed to upload avatar for %s", {user.display_name})
                return None
            if e.status == http_status_rate_limited:
                retry_after = int(e.response.headers.get("Retry-After", backoff_delay * (2**attempt)))
                logger.warning("Rate limited. Retrying in %s seconds", retry_after)
                await asyncio.sleep(retry_after)
            else:
                logger.exception("Failed to upload avatar for %s", {user.display_name})
                return None
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
        raise ValueError("Guild not found")
    emoji_mapping = {}
    asset_exceeds_max_size = 50045
    for member in guild.members:
        try:
            avatar_data = await fetch_user_avatar(member)
            emoji_id = await upload_avatar_as_emoji(guild, member, avatar_data)
            emoji_mapping[member.id] = emoji_id
            await config.user(member).set_raw("emoji_id", value=emoji_id)
        except discord.HTTPException as e:
            if e.code == asset_exceeds_max_size:
                logger.exception("Failed to upload avatar for %s", {member.display_name})
            else:
                logger.exception("Failed to update avatar for %s", {member.display_name})
        except Exception:
            logger.exception("Failed to update avatar for %s", {member.display_name})
    return emoji_mapping


async def get_user_emoji(bot, config, user):
    """
    Retrieves the stored emoji ID for a user.
    """
    emoji_id = await config.user(user).get_raw("emoji_id", default=None)
    if emoji_id:
        guild_id = await config.guild_id()
        guild = bot.get_guild(guild_id)
        if guild is None:
            logger.error(f"Failed to find guild with ID {guild_id}")
            return None
        return guild.get_emoji(emoji_id)
    return None


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
