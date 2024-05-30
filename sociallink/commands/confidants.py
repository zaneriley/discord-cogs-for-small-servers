import asyncio
import logging
from io import BytesIO

import aiohttp
import discord
import wcwidth
from PIL import Image
from redbot.core import commands

from sociallink.services.avatars import get_user_emoji

logger = logging.getLogger(__name__)


class ConfidantsManager:
    def __init__(self, bot, config, level_manager):
        self.bot = bot
        self.config = config
        self.level_manager = level_manager

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

    # async def get_confidants_message(self, user):
    #     user_data = await self.config.user(user).all()
    #     if not user_data.get("scores"):
    #         return "_No confidants found. Seek out allies to forge unbreakable bonds._"

    #     message = "# <a:hearty2k:1208204286962565161> Confidants \n\n"
    #     for confidant_id, score in user_data["scores"].items():
    #         level = await self.level_manager.calculate_level(score)
    #         stars = await self.level_manager.generate_star_rating(level)
    #         emoji = await self.get_user_emoji(discord.Object(id=confidant_id))
    #         emoji_str = f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>" if emoji else ""
    #         message += f"### {emoji_str} <@{confidant_id}>: {stars} \n"
    #     message += f"\nYour rank: {user_data.get('aggregate_score', 0)} pts"
    #     return message

    async def confidants(self, ctx: commands.Context):
        """Check your bonds with friends and allies."""

        def get_max_width(emoji_str, name):
            max_width = 0
            for char in emoji_str + name:
                max_width = max(max_width, wcwidth.wcwidth(char))
            return max_width

        user_data = await self.config.user(
            ctx.author
        ).all()

        if not user_data.get("scores"):
            message = await ctx.send("_No confidants found. Seek out allies to forge unbreakable bonds._")
            return

        max_name_length = max(
            len(ctx.guild.get_member(int(confidant_id)).display_name) for confidant_id in user_data["scores"]
        )
        max_level = await self.config.max_levels()  # Get max level from config

        message = "# <a:hearty2k:1208204286962565161> Confidants \n\n"
        for confidant_id, score in user_data["scores"].items():
            # Should we be putting levels in the config too?
            level = await self.level_manager.calculate_level(score)
            level_display = "<a:ui_sparkle:1241181537190547547> 𝙈𝘼𝙓" if level == max_level else f" ★ {level}"
            emoji = await get_user_emoji(discord.Object(id=confidant_id), self.config, ctx)
            member = ctx.guild.get_member(int(confidant_id))
            name = member.display_name if member else "Unknown"

            # Pad the name to align the ranks
            emoji_str = f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>" if emoji else ""
            max_width = get_max_width(emoji_str, name)
            padding = "⠀" * (max_name_length - len(name) + max_width + 5)
            mention = f"<@{confidant_id}>"
            padded_mention = f"{mention}{padding}"

            message += f"### {emoji_str}⠀{padded_mention}{level_display}\n"

        message += f"\nRank: {user_data.get('aggregate_score', 0)} pts\nType `/rank` for more"
        return message
        
