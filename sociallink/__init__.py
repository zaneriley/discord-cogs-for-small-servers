import json
from pathlib import Path

from redbot.core.bot import Red

from .sociallink_cog import SocialLink

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot: Red) -> None:
    social_link_cog = SocialLink(bot)
    await social_link_cog.setup()
    await bot.add_cog(social_link_cog)
    await bot.tree.sync()  # Sync the command tree with Discord
