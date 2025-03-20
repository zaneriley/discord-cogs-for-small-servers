"""
Announce cog for making server announcements.

This cog provides a standalone announcement system with features for text/embed
announcements, scheduling, and templating capabilities.
"""

import json
from pathlib import Path

from redbot.core.bot import Red

from .announce_cog import Announce


async def setup(bot: Red) -> None:
    """Load Announce cog."""
    await bot.add_cog(Announce(bot))

# Load end user data statement for Red
with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]
