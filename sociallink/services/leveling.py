import logging
import random
from datetime import UTC, datetime

import discord

from sociallink.services.events import (
    Events,
    event_bus,  # import singleton
)
from sociallink.services.observer import Observer

logger = logging.getLogger(__name__)


class LevelManager(Observer):
    def __init__(self, bot, config, event_bus):
        self.bot = bot
        self.config = config
        self.event_bus = event_bus
        logger.debug("Events possible: %s", self.event_bus.events)
        logger.debug("Subscribed to event %s", Events.ON_LEVEL_UP)

        # Basic dumb events for prototypign
        # in the future we should use fancier logic to
        # determine a sociallink
        self.event_bus.events[Events.ON_MESSAGE_MENTION].append(self.handle_link)
        self.event_bus.events[Events.ON_MESSAGE_QUOTE].append(self.handle_link)

    @classmethod
    def get_level_up_message(cls, level, max_level, user):
        user = user.display_name
        level_1_messages = [
            "A new bond has been formed!",
            "A new path has opened up before you.",
            "Feels like a bond is forming...",
        ]

        other_level_messages = [
            "Your bond has grown stronger!",
            "Your relationship has reached a new level of trust!",
            "Your connection has deepened, unlocking new potential!",
            "Your bond has evolved, revealing new paths ahead!",
            "You feel a surge of power!",
        ]

        max_level_messages = [
            f"Your bond with {user}has reached its ultimate form!",
            f"Your relationship with {user} has achieved its highest potential!",
            f"Your connection with {user} has transcended all limits!",
            "Your bond has become unbreakable!",
            "You have reached the pinnacle of your relationship!",
        ]

        if level == 1:
            return random.choice(level_1_messages)  # noqa: S311
        if level == max_level:
            return random.choice(max_level_messages)  # noqa: S311
        return random.choice(other_level_messages)  # noqa: S311

    @classmethod
    def next_level_messages(cls, level, max_level, user):
        new_level_far = [f"I don't think my bond with {user} will deepen just yet..."]

        new_level_close = [f"I feel like my bond with {user} will grow stronger soon..."]

        max_level_read = [f"I have a strong bond with {user}"]

        if level == 1:
            return random.choice(new_level_far)  # noqa: S311
        if level == max_level:
            return random.choice(max_level_read)  # noqa: S311
        return random.choice(new_level_close)  # noqa: S311

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

    # We need to declare this as a class method so that it can be used as a callback in the EventBus
    @classmethod
    async def create_level_up_embed(
        cls,
        title: str,
        journal_entry: str,
        rank: int,
        stars: str,
        avatar_url: str,
    ) -> discord.Embed:
        """
        Creates an embed for a confidant.
        """
        description = journal_entry
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple(),
        )
        embed.set_author(name="𝘾𝙊𝙉𝙁𝙄𝘿𝘼𝙉𝙏")
        embed.add_field(name=f"Rank {rank}", value=stars, inline=True)
        embed.set_thumbnail(url=avatar_url)

        return embed

    async def handle_link(self, *args, **kwargs):
        try:
            ctx = kwargs.get("ctx")
            user1 = kwargs.get("author")
            user2 = kwargs.get("confidant")
            logger.debug("Handling link between %s and %s", user1, user2)
            score_increment = kwargs.get("score_increment")
            event_type = kwargs.get("event_type")
            channel_id = kwargs.get("channel_id")
            score_increment = kwargs.get("points")

            user1_id_str = str(user1.id)
            user2_id_str = str(user2.id)
            user1_data = await self.config.user(user1).all()
            user2_data = await self.config.user(user2).all()

            user1_data["scores"][user2_id_str] = user1_data["scores"].get(user2_id_str, 0) + score_increment
            user2_data["scores"][user1_id_str] = user2_data["scores"].get(user1_id_str, 0) + score_increment

            # Calculate and set aggregate_score for both users
            user1_data["aggregate_score"] = sum(user1_data["scores"].values())
            user2_data["aggregate_score"] = sum(user2_data["scores"].values())

            # Calculate new levels
            user1_new_level = await self.calculate_level(user1_data["scores"][user2_id_str])
            await self.calculate_level(user2_data["scores"][user1_id_str])

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
                    ctx=ctx,
                    user_1=user1,
                    user_2=user2,
                    level=user1_new_level,
                    stars=stars,
                    event_type=event_type,
                    timestamp=timestamp,
                    channel_id=channel_id,  # Add this line to include channel_id
                )

            # TODO: Suppress for now while we prototype
            # if user2_new_level > await self.calculate_level(user2_data["scores"][user1_id_str] - score_increment):
            #     await self.announce_rank_increase(user2, user1, user2_new_level)

            await self.config.user(user1).set_raw("scores", value=user1_data["scores"])
            await self.config.user(user1).set_raw("aggregate_score", value=user1_data["aggregate_score"])
            await self.config.user(user2).set_raw("scores", value=user2_data["scores"])
            await self.config.user(user2).set_raw("aggregate_score", value=user2_data["aggregate_score"])

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
    async def handle_level_up(cls, bot, config, *args, **kwargs):  # noqa: N805
        logger.debug("Entered handle_level_up with args: %s, kwargs: %s", args, kwargs)
        max_level = await config.max_levels()
        try:
            logger.debug("Received event %s", kwargs)
            user_1 = kwargs.get("user_1")
            user_2 = kwargs.get("user_2")
            level = kwargs.get("level")
            stars = kwargs.get("stars")
            channel_id = kwargs.get("channel_id")

            user_1_id_str = str(user_1.id)
            user_2_id_str = str(user_2.id)

            if not user_1_id_str or not user_2_id_str:
                logger.error("One or both users not found.")
                return

            # Fetch the channel object
            channel = bot.get_channel(channel_id)
            if not channel:
                logger.error("Channel with ID %s not found.", channel_id)
                return

            # Fetch journal entries for both users
            user_1_data = await config.user(user_1).all()
            user_2_data = await config.user(user_2).all()

            # Get the latest journal entry for each user
            (
                sorted(user_1_data.get("journal", []), key=lambda x: x["timestamp"], reverse=True)[0].get(
                    "description", ""
                )
                if user_1_data.get("journal")
                else ""
            )
            (
                sorted(user_2_data.get("journal", []), key=lambda x: x["timestamp"], reverse=True)[0].get(
                    "description", ""
                )
                if user_2_data.get("journal")
                else ""
            )

            # The confidant the user ranked up with
            embed_for_user_2 = await LevelManager.create_level_up_embed(
                journal_entry="",
                title=f"@{user_2.display_name}",
                rank=level,
                stars=stars,
                avatar_url=user_2.display_avatar.url,
            )

            embed_for_user_1 = await LevelManager.create_level_up_embed(
                journal_entry="",
                title=f"@{user_1.display_name}",
                rank=level,
                stars=stars,
                avatar_url=user_1.display_avatar.url,
            )

            level_up_message_user_1 = LevelManager.get_level_up_message(level, max_level, user_2)
            LevelManager.get_level_up_message(level, max_level, user_1)

            # Send the initial message with both embeds to the channel
            await channel.send(content="## 𝙍𝘼𝙉𝙆 𝙐𝙋\n\n", embeds=[embed_for_user_2, embed_for_user_1])

            # Send the follow-up message with the level-up message to the channel
            await channel.send(content=f"{level_up_message_user_1}")

            logger.info(
                "Notified %s and %s of their increased social rank with stars in channel %s.",
                user_1.display_name,
                user_2.display_name,
                channel_id,
            )
        except Exception:
            logger.exception("Failed to send notification:")
