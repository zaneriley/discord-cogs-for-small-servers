import json
from pathlib import Path

try:
    from redbot.core.bot import Red
except ModuleNotFoundError:
    Red = None

from .seasonalroles_cog import SeasonalRoles

info_path = Path(__file__).parent / "info.json"
with info_path.open() as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot: Red) -> None:
    await bot.add_cog(SeasonalRoles(bot))
