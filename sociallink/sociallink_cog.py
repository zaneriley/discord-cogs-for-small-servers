import logging
import os
from datetime import UTC, datetime

import discord
from dotenv import load_dotenv
from redbot.core import Config, commands

from .commands.confidants import ConfidantsManager
from .commands.journal import JournalManager
from .commands.rank import RankManager
from .leveling import LevelManager

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: Update this to properly load from the .env file
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))


# TODO:
# - Not accruing points when simulating events. Just storing the last points value.
# - Aggregate score not working
# - Journal does not populate
# - Refactor once it's working


class SocialLink(commands.Cog):

    """
    Tracks social links and aggregate scores between users.

    Commands:
    !sociallink confidants
        Shows the user's confidants and the score for each.

    !sociallink rank
        Show's a server-wide ranking of users based on their aggregate confidant score

    !sociallink journal
        Shows a list of events that increased links between users

    !sociallink admin reset <user_id> <score>
        Resets the social link scores for all users

    !sociallink admin simulate <event_type> <user_id1> <user_id2>
        Simulates a social link event between two users

    Current list of events:
    - Users @mention each other
    - Users react to each other
    - Users join Discord events with at least one other user
    - Users join voice channels with at least one other user for a certain amount of time
    - length of conversation threads initiated by one user and continued by another
    """

    def __init__(self, bot) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.journal_manager = JournalManager(self.config)
        self.confidants_manager = ConfidantsManager(self.config)
        self.rank_manager = RankManager()
        self.level_manager = LevelManager(self.config, self.journal_manager, self.confidants_manager)

        default_global = {
            # Social Link Settings
            # Controls how difficult it is to get a social link
            "base_s_link": 10,
            "level_exponent": 2,
            "max_levels": 10,
            "decay_rate": 2,  # LP/day
            "decay_interval": "daily",
        }
        default_events = {
            "voice_channel": {
                "duration_threshold": 1800,
                "points": 10,
            },
            "message_mention": {
                "points": 5,
            },
            "reaction": {
                "points": 2,
            },
        }
        default_user = {"scores": {}, "aggregate_score": 0, "journal": []}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_events)
        self.config.register_user(**default_user)
        self.voice_sessions = {}  # {user_id: {"start": datetime, "channel": channel_id}}

    @commands.Cog.listener()
    async def on_ready(self):
        guild_id = GUILD_ID  # Assuming GUILD_ID is the ID of your guild
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            logger.error(f"Guild with ID {guild_id} not found.")
            return

        members = guild.members  # This gets all members of the guild
        all_users = await self.config.all_users()  # Await the coroutine directly
        for member in members:
            if member.bot:  # Skip bot accounts to avoid unnecessary data storage
                continue
            user_scores = all_users.get(str(member.id), {}).get("scores", {})
            for other_member in members:
                if other_member.id == member.id or other_member.bot:  # Skip self and bots
                    continue
                # Initialize score if not exist
                if str(other_member.id) not in user_scores:
                    user_scores[str(other_member.id)] = 0
            all_users[str(member.id)] = {
                "scores": user_scores,
                "aggregate_score": 0,
                "journal": [],
            }

        logger.info("SocialLink cog ready and social link scores initialized")

    @commands.group(aliases=["slink", "sl"])
    async def sociallink(self, ctx):
        """Commands related to social link."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid social link command passed.")

    @sociallink.group()
    async def admin(self, ctx):
        """Admin-only commands for managing social links."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid admin command.")

    @admin.command(name="simulate")
    async def simulate_event(self, ctx, event_type: str, user1: discord.Member, user2: discord.Member):
        valid_events = ["voice_channel", "message_mention", "reaction"]
        if event_type not in valid_events:
            await ctx.send(
                f"Invalid event type: {event_type}. Please use one of the following: {', '.join(valid_events)}"
            )
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
            await ctx.send(
                f"No points configuration found for event type: {event_type}. Please check the configuration."
            )
            logger.error(f"No points configuration found for event type: {event_type}")
            return

        success, message = await self.level_manager.handle_link(
            ctx, user1, user2, score_increment, event_type, "Simulated event"
        )
        if success:
            await ctx.send(
                f"Simulated {event_type} event between {user1.display_name} and {user2.display_name}. Each received {score_increment} points."
            )
            logger.info(message)
        else:
            await ctx.send("Failed to simulate the event due to an internal error.")
            logger.error(message)

    @admin.command(name="settings")
    async def show_settings(self, ctx):
        settings = await self.level_manager.get_settings(ctx)

        base_s_link = settings["base_s_link"]
        level_exponent = settings["level_exponent"]
        max_levels = settings["max_levels"]
        decay_rate = settings["decay_rate"]
        decay_interval = settings["decay_interval"]
        events_config = settings["events_config"]
        levels_points = settings["levels_points"]

        event_points = "\n".join([f"- {event}: {details['points']} points" for event, details in events_config.items()])

        levels_points_str = "\n".join([f"- Level {level}: {points} points" for level, points in levels_points])

        settings_message = (
            f"# Social Link settings:**\n"
            f"- Base Points for Social Link: {base_s_link}\n"
            f"- Level Exponent: {level_exponent}\n"
            f"- Maximum Levels: {max_levels}\n"
            f"- Decay Rate: {decay_rate} LP/day\n"
            f"- Decay Interval: {decay_interval}\n\n"
            f"**Event Points:**\n{event_points}\n\n"
            f"**Event Points:**\n{event_points}\n\n"
            f"**Levels and Points Required:**\n{levels_points_str}"
        )

        await ctx.send(settings_message)

    @admin.command(name="journal_entry")
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

    @commands.hybrid_command(name="confidants", aliases=["sociallink_confidants"])
    async def confidants(self, ctx: commands.Context):
        """Check your bonds with friends and allies."""
        user_id = ctx.author.id  # Get the user ID directly as an integer

        # Fetch real user data
        user_data = await self.config.user(
            ctx.author
        ).all()  # Use the 'all' method to get all data associated with the user

        if not user_data.get("scores"):  # Simplified check for scores
            await ctx.send("No confidants found. Seek out allies to forge unbreakable bonds.")
            return

        message = "# <a:hearty2k:1208204286962565161> Confidants \n\n"
        for confidant_id, score in user_data["scores"].items():
            level = await self.level_manager.calculate_level(score)
            stars = await self.level_manager.generate_star_rating(level)
            message += f"<@{confidant_id}>: {stars} `{score} pts` \n"  # Use confidant_id directly
        message += f"\nYour rank: {user_data.get('aggregate_score', 0)} pts (not implemented yet)"

        if ctx.interaction:
            await ctx.interaction.response.send_message(message, ephemeral=True)
        else:
            await ctx.send(message)

    @sociallink.command()
    async def rank(self, ctx):
        """Show's a server-wide ranking of users based on their aggregate confidant score."""
        sorted_users = await self.rank_manager.get_rankings(self.config)
        rank_message = self.rank_manager.format_rankings(sorted_users, ctx.author.id)
        await ctx.send(rank_message)

    @sociallink.command()
    async def journal(self, ctx):
        """Shows a list of events that increased links between users."""
        try:
            message = await self.journal_manager.display_journal(ctx.author)

            await ctx.send(message)

        except Exception as e:
            logger.exception(f"An error occurred while processing the journal command for user {ctx.author.id}: {e}")
            await ctx.send("An error occurred while retrieving your journal. Please try again later.")

    # Listeners for sLink activity
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            if member.bot:
                logger.debug(f"Ignoring bot user: {member.display_name} ({member.id})")
                return

            now = datetime.now(tz=UTC)
            user_id = str(member.id)
            today = now.date()  # Not using the DateUtil here because it could cause issues with datetime.now(tz=UTC)

            if user_id not in self.voice_sessions or self.voice_sessions[user_id]["last_interaction_date"] < today:
                logger.info(f"Initializing or resetting voice session for user: {member.display_name} ({member.id})")
                self.voice_sessions[user_id] = {
                    "channel": None,
                    "start": None,
                    "interactions": {},
                    "last_interaction_date": today,
                }

            if before.channel is None and after.channel is not None:
                logger.info(f"User {member.display_name} ({member.id}) joined voice channel: {after.channel.id}")
                self.voice_sessions[user_id]["channel"] = after.channel.id
                self.voice_sessions[user_id]["start"] = now

            elif before.channel is not None and (after.channel is None or before.channel.id != after.channel.id):
                logger.info(
                    f"User {member.display_name} ({member.id}) left or switched from voice channel: {before.channel.id}"
                )
                await self._update_interaction_time(user_id, before.channel.id, now)

                if after.channel is None:
                    self.voice_sessions[user_id]["channel"] = None
                    self.voice_sessions[user_id]["start"] = None
                else:
                    self.voice_sessions[user_id]["channel"] = after.channel.id
                    self.voice_sessions[user_id]["start"] = now

        except Exception as e:
            logger.error(
                f"Error handling voice state update for {member.display_name} ({member.id}): {e}", exc_info=True
            )

    async def _update_interaction_time(self, user_id, channel_id, end_time):
        session = self.voice_sessions[user_id]
        start_time = session["start"]
        if start_time is None:
            logger.warning(f"No start time found for session: User {user_id} in channel {channel_id}")
            return

        duration = (end_time - start_time).total_seconds()
        if duration < 0:
            logger.warning(f"Negative duration calculated for User {user_id} in channel {channel_id}")
            return

        for other_user_id, other_session in self.voice_sessions.items():
            if other_user_id != user_id and other_session["channel"] == channel_id:
                if other_session["last_interaction_date"] == session["last_interaction_date"]:
                    interaction_time = other_session["interactions"].get(user_id, 0)
                    new_interaction_time = min(interaction_time + duration, 10)
                    if new_interaction_time == 10:
                        logger.info(f"Interaction time capped at 30 minutes for users {user_id} and {other_user_id}")
                        await self.announce_rank_increase(user_id, other_user_id, 1)
                    other_session["interactions"][user_id] = new_interaction_time
                    session["interactions"][other_user_id] = new_interaction_time

        session["start"] = None
        logger.debug(f"Updated interaction time for User {user_id} after leaving/switching channel {channel_id}")
