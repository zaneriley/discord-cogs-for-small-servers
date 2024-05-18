import asyncio
import logging
from io import BytesIO

import aiohttp
import discord
from PIL import Image

# from utilities.discord_utils import fetch_user_avatar

logger = logging.getLogger(__name__)


class ConfidantsManager:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    async def fetch_user_avatar(self, user):
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

    async def upload_avatar_as_emoji(self, guild, user, avatar_data):
        """
        Uploads a user's avatar as a guild emoji.
        """
        # Resize the image if it exceeds the maximum size
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

    async def update_avatar_emojis(self):
        """
        Updates all user avatars as emojis in the specified guild and returns a mapping of user IDs to emoji IDs.
        """
        guild_id = await self.config.guild_id()
        guild = self.bot.get_guild(guild_id)
        if not guild:
            raise ValueError("Guild not found")
        emoji_mapping = {}
        asset_exceeds_max_size = 50045
        for member in guild.members:
            try:
                avatar_data = await self.fetch_user_avatar(member)
                emoji_id = await self.upload_avatar_as_emoji(guild, member, avatar_data)
                emoji_mapping[member.id] = emoji_id
                await self.config.user(member).set_raw("emoji_id", value=emoji_id)
            except discord.HTTPException as e:
                if e.code == asset_exceeds_max_size:
                    logger.exception("Failed to upload avatar for %s", {member.display_name})
                else:
                    logger.exception("Failed to update avatar for %s", {member.display_name})
            except Exception:
                logger.exception("Failed to update avatar for %s", {member.display_name})
        return emoji_mapping

    async def get_user_emoji(self, user):
        """
        Retrieves the stored emoji ID for a user.
        """
        emoji_id = await self.config.user(user).get_raw("emoji_id", default=None)
        if emoji_id:
            guild_id = await self.config.guild_id()
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                logger.error(f"Failed to find guild with ID {guild_id}")
                return None
            return guild.get_emoji(emoji_id)
        return None

    async def create_confidant_embed(
        self, username: str, journal_entry: str, rank: int, stars: str, avatar_url: str, level_up: bool = False
    ) -> discord.Embed:
        """
        Creates an embed for a confidant.
        """
        title = "𝘾𝙊𝙉𝙁𝙄𝘿𝘼𝙉𝙏"  # noqa: RUF001, RUF003𝘿𝘼𝙉𝙏"F001𝘿𝘼𝙉𝙏"
        description = (
            "Though still worried about the track team, Rye said he has the Phantom Thieves now."
            if not level_up
            else "Congratulations! You've leveled up your bond with this confidant."
        )
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
        )

        embed.add_field(name=f"Rank {rank}", value=stars, inline=True)
        embed.set_thumbnail(url=avatar_url)

        return embed

    async def get_confidants_message(self, user):
        user_id = user.id  # Get the user ID directly as an integer

        # Fetch real user data
        user_data = await self.config.user(user).all()  # Use the 'all' method to get all data associated with the user

        if not user_data.get("scores"):  # Simplified check for scores
            return "No confidants found. Seek out allies to forge unbreakable bonds."

        message = "# <a:hearty2k:1208204286962565161> Confidants \n\n"
        for confidant_id, score in user_data["scores"].items():
            level = await self.level_manager.calculate_level(score)
            stars = await self.level_manager.generate_star_rating(level)
            emoji = await self.get_user_emoji(discord.Object(id=confidant_id))

            emoji_str = f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>" if emoji else ""

            message += f"### {emoji_str} <@{confidant_id}>: {stars} \n"
        message += f"\nYour rank: {user_data.get('aggregate_score', 0)} pts (not implemented yet)"

        return message
