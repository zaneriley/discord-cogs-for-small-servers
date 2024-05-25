import json
from pathlib import Path

from redbot.core.bot import Red

from .emojilocker_cog import EmojiLocker

with Path.open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]

async def setup(bot: Red) -> None:
    emoji_locker_cog = EmojiLocker(bot)
    await bot.add_cog(emoji_locker_cog)
    await bot.tree.sync()
