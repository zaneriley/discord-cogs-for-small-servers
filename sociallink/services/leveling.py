import logging
from datetime import UTC, datetime

import discord

from sociallink.services.events import (
    Events,
    event_bus,  # import singleton
)
from sociallink.services.observer import Observer

logger = logging.getLogger(__name__)


class LevelManager(Observer):
    def __init__(self, config, event_bus):
        self.config = config
        self.event_bus = event_bus
        logger.debug("Events possible: %s", self.event_bus._events)
        logger.debug("Subscribed to event %s", Events.ON_LEVEL_UP)

    async def calculate_level(self, score):
        base_s_link = await self.config.base_s_link()
        level_exponent = await self.config.level_exponent()
        max_levels = await self.config.max_levels()
        level = 0
        # logger.debug("Calculating level for score: %d", score)
        while score > base_s_link + (level**level_exponent) and level < max_levels:
            points_for_level = base_s_link + (level**level_exponent)
            # logger.debug("Level: %d, Points for level: %d, Remaining score: %d", level, points_for_level, score)
            score -= points_for_level
            level += 1
        logger.debug("Final level: %d for score: %d", level, score)
        return min(level, max_levels)

    async def generate_star_rating(self, level, *, is_level_up=False):
        max_levels = await self.config.max_levels()
        if is_level_up:
            stars = "★" * (level - 1) + "<a:ui_star_new:1239795055150104647>" + "☆" * (max_levels - level)
        else:
            stars = "★" * level + "☆" * (max_levels - level)
        return stars

    async def create_level_up_embed(
        self,
        journal_entry: str,
        rank: int,
        stars: str,
        avatar_url: str,
    ) -> discord.Embed:
        """
        Creates an embed for a confidant.
        """
        title = "𝘾𝙊𝙉𝙁𝙄𝘿𝘼𝙉𝙏"  # noqa: RUF001, RUF003𝘿𝘼𝙉𝙏"F001𝘿𝘼𝙉𝙏"
        description = journal_entry
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
        )

        embed.add_field(name=f"Rank {rank}", value=stars, inline=True)
        embed.set_thumbnail(url=avatar_url)

        return embed

    async def handle_link(self, ctx, user1, user2, score_increment, event_type):
        try:
            user1_id_str = str(user1.id)
            user2_id_str = str(user2.id)
            user1_data = await self.config.user(user1).all()
            user2_data = await self.config.user(user2).all()

            user1_data["scores"][user2_id_str] = user1_data["scores"].get(user2_id_str, 0) + score_increment
            user2_data["scores"][user1_id_str] = user2_data["scores"].get(user1_id_str, 0) + score_increment

            # Calculate new levels
            user1_new_level = await self.calculate_level(user1_data["scores"][user2_id_str])
            user2_new_level = await self.calculate_level(user2_data["scores"][user1_id_str])

            # Announce rank increase if applicable
            new_level_up = user1_new_level > await self.calculate_level(
                user1_data["scores"][user2_id_str] - score_increment
            )
            logger.debug("Level up calculation was %s", new_level_up)

            if new_level_up:
                timestamp = datetime.now(tz=UTC)
                stars = await self.generate_star_rating(user1_new_level, is_level_up=True)
                logger.info("Attempting to fire level up event for %s and %s", user1.display_name, user2.display_name)
                self.event_bus.fire(
                    Events.ON_LEVEL_UP,
                    user_1=user1,
                    user_2=user2,
                    level=user1_new_level,
                    stars=stars,
                    event_type=event_type,
                    timestamp=timestamp,
                )

            # TODO: Suppress for now while we prototype
            # if user2_new_level > await self.calculate_level(user2_data["scores"][user1_id_str] - score_increment):
            #     await self.announce_rank_increase(user2, user1, user2_new_level)

            # await self.journal_manager.create_journal_entry(event_type, user1, user2, timestamp, details)
            # await self.journal_manager.create_journal_entry(event_type, user2, user1, timestamp, details)

            await self.config.user(user1).set_raw("scores", value=user1_data["scores"])
            await self.config.user(user2).set_raw("scores", value=user2_data["scores"])

        except KeyError:
            logger.exception("Key error accessing user data")
            return (False, "Key error accessing user data")
        except TypeError:
            logger.exception("Type error in data manipulation")
            return (False, "Type error in data manipulation")
        except Exception:
            logger.exception("An unexpected error occurred while handling link")
            return (False, "An unexpected error occurred while handling link")
        else:
            return (
                True,
                f"Link handled successfully between {user1} and {user2} for {event_type} with increment {score_increment}",
            )

    @event_bus.subscribe(Events.ON_LEVEL_UP)
    async def handle_level_up(self, *args, **kwargs):
        logger.debug("Entered handle_level_up with args: %s, kwargs: %s", args, kwargs)

        try:
            logger.debug("Received event %s", kwargs)
            user_1 = kwargs.get("user_1")
            user_2 = kwargs.get("user_2")
            level = kwargs.get("level")
            stars = kwargs.get("stars")

            user_1_id_str = str(user_1.id)
            user_2_id_str = str(user_2.id)

            if not user_1_id_str or not user_2_id_str:
                logger.error("One or both users not found.")
                return

            # Fetch journal entries for both users
            user_1_data = await self.config.user(user_1).all()
            user_2_data = await self.config.user(user_2).all()

            # Get the latest journal entry for each user
            user_1_latest_journal = (
                sorted(user_1_data.get("journal", []), key=lambda x: x["timestamp"], reverse=True)[0]
                if user_1_data.get("journal")
                else ""
            )
            user_2_latest_journal = (
                sorted(user_2_data.get("journal", []), key=lambda x: x["timestamp"], reverse=True)[0]
                if user_2_data.get("journal")
                else ""
            )

            # The confidant the user ranked up with
            embed_for_user_2 = await self.create_level_up_embed(
                journal_entry=user_2_latest_journal,
                rank=level,
                stars=stars,
                avatar_url=user_2.display_avatar.url,
            )

            embed_for_user_1 = await self.create_level_up_embed(
                journal_entry=user_1_latest_journal,
                rank=level,
                stars=stars,
                avatar_url=user_1.display_avatar.url,
            )

            try:
                await user_1.send(content=f"## Rank up!!\n\n# <@{user_2.id}> \n", embed=embed_for_user_2)
                # TODO: TURNED OFF FOR PROTOTYPING DO NOT REMOVE
                # await user_2.send(content=f"## Rank up!!\n\n# <@{user_1.id}> \n", embed=embed_for_user_1)
                logger.info(
                    "Notified %s and %s of their increased social rank with stars.",
                    user_1.display_name,
                    user_2.display_name,
                )
            except Exception:
                logger.exception("Failed to send notification:")
        except Exception:
            logger.exception("Failed to process level up:")
