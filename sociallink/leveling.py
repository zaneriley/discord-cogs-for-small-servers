import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class LevelManager:
    def __init__(self, config, journal_manager, confidants_manager):
        self.config = config
        self.journal_manager = journal_manager
        self.confidants_manager = confidants_manager

    async def get_settings(self, ctx):
        base_s_link = await self.config.base_s_link()
        level_exponent = await self.config.level_exponent()
        max_levels = await self.config.max_levels()
        decay_rate = await self.config.decay_rate()
        decay_interval = await self.config.decay_interval()
        events_config = await self.config.guild(ctx.guild).all()

        levels_points = []
        total_points = 0
        for level in range(1, max_levels + 1):
            points_for_level = base_s_link + (level**level_exponent)
            total_points += points_for_level
            levels_points.append((level, total_points))

        return {
            "base_s_link": base_s_link,
            "level_exponent": level_exponent,
            "max_levels": max_levels,
            "decay_rate": decay_rate,
            "decay_interval": decay_interval,
            "events_config": events_config,
            "levels_points": levels_points,
        }

    async def handle_link(self, ctx, user1, user2, score_increment, event_type, details=""):
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
            if user1_new_level > await self.calculate_level(user1_data["scores"][user2_id_str] - score_increment):
                await self.announce_rank_increase(user1, user2, user1_new_level)
            # TODO: Suppress for now while we prototype
            # if user2_new_level > await self.calculate_level(user2_data["scores"][user1_id_str] - score_increment):
            #     await self.announce_rank_increase(user2, user1, user2_new_level)

            timestamp = datetime.now(tz=UTC)
            await self.journal_manager.create_journal_entry(event_type, user1, user2, timestamp, details)
            await self.journal_manager.create_journal_entry(event_type, user2, user1, timestamp, details)

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

    async def _calculate_level(self, score):
        base_s_link = await self.config.base_s_link()
        level_exponent = await self.config.level_exponent()
        max_levels = await self.config.max_levels()
        level = 0
        logger.debug("Calculating level for score: %d", score)
        while score > base_s_link + (level**level_exponent) and level < max_levels:
            points_for_level = base_s_link + (level**level_exponent)
            logger.debug("Level: %d, Points for level: %d, Remaining score: %d", level, points_for_level, score)
            score -= points_for_level
            level += 1
        logger.debug("Final level: %d for score: %d", level, score)
        return min(level, max_levels)

    async def generate_star_rating(self, level):
        max_levels = await self.config.max_levels()
        stars = "★" * level + "☆" * (max_levels - level)
        return stars

    async def announce_rank_increase(self, user_1, user_2, level):
        user_1_id_str = str(user_1.id)
        user_2_id_str = str(user_2.id)

        stars = await self.generate_star_rating(level)

        if not user_1_id_str or not user_2_id_str:
            logger.error("One or both users not found.")
            return

        embed_for_user_1 = await self.confidants_manager.create_confidant_embed(
            username=user_1.display_name,
            journal_entry="",
            rank=level,
            stars=stars,
            avatar_url=user_1.display_avatar.url,
        )

        try:
            await user_1.send(content=f"## Rank up!!\n\n# <@{user_1.id}> \n", embed=embed_for_user_1)
            logger.info(
                "Notified %s and %s of their increased social rank with stars.",
                user_1.display_name,
                user_2.display_name,
            )
        except Exception:
            logger.exception("Failed to send notification:")
