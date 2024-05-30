import logging
from datetime import UTC, datetime

import discord
from redbot.core import commands

logger = logging.getLogger(__name__)

from sociallink.services.avatars import update_avatar_emojis


class AdminManager(commands.Cog):
    def __init__(self, bot, config, level_manager, confidants_manager, journal_manager):
        self.bot = bot
        self.config = config
        self.level_manager = level_manager
        self.confidants_manager = confidants_manager
        self.journal_manager = journal_manager


    async def show_settings(self, ctx):
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

        # event_points = "\n".join([f"- {event}: {details['points']} points" for event, details in events_config.items()])

        levels_points_str = "\n".join([f"- Level {level}: {points} points" for level, points in levels_points])

        settings_message = (
            f"# Social Link settings:\n"
            f"- Base Points for Social Link: {base_s_link}\n"
            f"- Level Exponent: {level_exponent}\n"
            f"- Maximum Levels: {max_levels}\n"
            f"- Decay Rate: {decay_rate} LP/day\n"
            f"- Decay Interval: {decay_interval}\n\n"
            # f"**Event Points:**\n{event_points}\n\n"
            f"**Levels and Points Required:**\n{levels_points_str}"
        )

        await ctx.send(settings_message)

    async def reset_user_data(self, ctx, user: discord.Member):
        """Actually resets the social link scores, journals, and other data for a user."""
        user_id = user.id

        try:
            # Clear the specific user's data
            await self.config.user(user).clear()
            logger.info("Cleared data for user %s (ID: %s)", user.display_name, user.id)
        except Exception as e:
            logger.exception("Failed to clear data for user %s (ID: %s): %s", user.display_name, user.id, e)
            await ctx.send(f"Failed to clear data for {user.display_name}. Please try again later.")
            return

        try:
            # Iterate through all users and remove any confidant scores related to the user being reset
            all_users = await self.config.all_users()
            logger.info("Fetched all users data")
            for other_user_id, other_user_data in all_users.items():
                if user_id in other_user_data.get("scores", {}):
                    try:
                        # Remove the confidant score
                        del other_user_data["scores"][user_id]
                        logger.info("Removed confidant score for user %s from other user %s", user_id, other_user_id)

                        # Recalculate the aggregate score
                        other_user_data["aggregate_score"] = sum(other_user_data["scores"].values())
                        logger.info("Recalculated aggregate score for user %s: %s", other_user_id, other_user_data["aggregate_score"])

                        # Save the updated data
                        await self.config.user_from_id(other_user_id).set_raw("scores", value=other_user_data["scores"])
                        await self.config.user_from_id(other_user_id).set_raw("aggregate_score", value=other_user_data["aggregate_score"])
                        logger.info(f"Updated scores and aggregate score for user {other_user_id}")
                    except Exception as e:
                        logger.exception("Failed to update data for user %s when removing confidant score for %s: %s", other_user_id, user_id, e)
        except Exception as e:
            logger.exception(f"Failed to iterate through all users to remove confidant scores for user {user_id}: {e}")
            await ctx.send(f"Failed to reset confidant scores for {user.display_name}. Please try again later.")
            return

        await ctx.send(f"All social link data for {user.display_name} has been reset.")
        logger.info(f"Reset social link data for user {user.display_name} (ID: {user.id})")

    async def simulate_event(self, ctx, event_type: str, user1: discord.Member, user2: discord.Member):
        valid_events = ["voice_channel", "message_mention", "reaction"]
        if event_type not in valid_events:
            await ctx.send(f"Invalid event type: {event_type}. Please use one of the following: {', '.join(valid_events)}")
            return

        logger.info("Simulating event between %s and %s for %s.", user1.display_name, user2.display_name, event_type)

        if not user1:
            await ctx.send("The first user mention is invalid. Please check and try again.")
            logger.error("Invalid user mention for user1: %s", ctx.message.content)
            return
        if not user2:
            await ctx.send("The second user mention is invalid. Please check and try again.")
            logger.error("Invalid user mention for user2: %s", {ctx.message.content})
            return

        events_config = await self.config.guild(ctx.guild).all()

        if event_type not in events_config:
            await ctx.send(f"No configuration found for event type: {event_type}")
            return

        event_points = events_config[event_type]["points"]

        score_increment = event_points
        if score_increment == 0:
            await ctx.send(f"No points configuration found for event type: {event_type}. Please check the configuration.")
            logger.error(f"No points configuration found for event type: {event_type}")
            return

        success, message = await self.level_manager.handle_link(
            ctx,
            user1,
            user2,
            score_increment,
            event_type,
        )
        if success:
            await ctx.send(f"Simulated {event_type} event between {user1.display_name} and {user2.display_name}. Each received {score_increment} points.")
            logger.info(message)
        else:
            await ctx.send("Failed to simulate the event due to an internal error.")
            logger.error(message)

    async def add_points(self, ctx, user: discord.Member, points: int):
        """Add arbitrary points to yourself and another user."""

        me = ctx.guild.get_member(ctx.message.author.id)

        if not me:
            await ctx.send("Could not find your user in the guild.")
            logger.error("Could not find user with ID  in the guild.")
            return

        if not user:
            await ctx.send("The user mention is invalid. Please check and try again.")
            logger.error("Invalid user mention: %s", ctx.message.content)
            return

        # Add points to both users
        success_me, message_me = await self.level_manager.handle_link(
            ctx,
            me,
            user,
            points,
            "manual_add",
        )

        if success_me:
            await ctx.send(f"Added {points} points to both {me.display_name} and {user.display_name}.")
            logger.info(f"Added {points} points to both {me.display_name} and {user.display_name}.")
        else:
            await ctx.send("Failed to add points due to an internal error.")
            logger.error(f"Failed to add points: {message_me}, {message_user}")

    async def update_avatar_emojis(self, ctx, bot, config):
        """
        Command to trigger avatar updating and save the emoji IDs in the configuration.
        """
        try:
            emoji_mapping = await update_avatar_emojis(bot, config)
            for user_id, emoji_id in emoji_mapping.items():
                try:
                    await self.config.user_from_id(user_id).set_raw("emoji_id", value=emoji_id)
                except Exception as e:
                    logger.exception("Failed to save emoji ID for user %s:", user_id)
                    await ctx.send(f"Failed to save emoji for user ID {user_id}. Error: {e}")
            await ctx.send("Avatars updated and emoji IDs saved successfully.")
        except Exception as e:
            logger.exception("Failed to update avatars:")
            await ctx.send(f"Failed to update avatars due to an internal error: {e}")

    async def test_journal_entry(self, ctx, user: discord.Member, *, event_details: str):
        """Test command for creating a journal entry."""
        # Create journal entry with timestamp:
        timestamp = datetime.now(tz=UTC)
        success, result = await self.journal_manager.create_journal_entry(
            "admin_test", user, user, timestamp, event_details
        )

        if success:
            await ctx.send(f"Journal entry successfully created: {result}")
        else:
            await ctx.send(f"Failed to create journal entry: {result}")
