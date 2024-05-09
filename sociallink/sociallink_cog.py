from datetime import datetime

from redbot.core import Config, commands
import discord
from discord.ext import tasks

import os
import logging
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: Update this to properly load from the .env file
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))

points_up_messages = [
    "You feel like you understand {pronoun} a lot better now.",
    "You feel your relationship with {user} has grown yet deeper…"
],

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
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )
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
        """Simulates a social link event between two users."""
        valid_events = ['voice_channel', 'message_mention', 'reaction']
        if event_type not in valid_events:
            await ctx.send(f"Invalid event type: {event_type}. Please use one of the following: {', '.join(valid_events)}")
            return

        logger.info(f"Simulating event between {user1.display_name} and {user2.display_name} for {event_type}.")

        # Detailed user validation
        if not user1:
            await ctx.send("The first user mention is invalid. Please check and try again.")
            logger.error(f"Invalid user mention for user1: {ctx.message.content}")
            return
        if not user2:
            await ctx.send("The second user mention is invalid. Please check and try again.")
            logger.error(f"Invalid user mention for user2: {ctx.message.content}")
            return
        
        # Retrieve the guild configuration for events
        events_config = await self.config.guild(ctx.guild).all()

        # Check if the event type exists in the configuration
        if event_type not in events_config:
            await ctx.send(f"No configuration found for event type: {event_type}")
            return

        # Access the points for the event type
        event_points = events_config[event_type]['points']

        score_increment = event_points
        if score_increment == 0:
            await ctx.send(f"No points configuration found for event type: {event_type}. Please check the configuration.")
            logger.error(f"No points configuration found for event type: {event_type}")
            return
        
        # Simulate the event
        try:
            await self.handle_link(ctx, user1.id, user2.id, score_increment, event_type, "Simulated event")
            await ctx.send(f"Simulated {event_type} event between {user1.display_name} and {user2.display_name}. Each received {score_increment} points.")
            logger.info(f"Simulated event successful between {user1.display_name} and {user2.display_name} for {event_type}.")
        except Exception as e:
            await ctx.send("Failed to simulate the event due to an internal error.")
            logger.error(f"Error simulating event between {user1.display_name} and {user2.display_name}: {str(e)}", exc_info=True)

    @sociallink.command(aliases=["friends", "confidents"])
    async def confidants(self, ctx):
        """Shows the user's confidants and the score for each."""
        user_id = ctx.author.id  # Get the user ID directly as an integer

        # Fetch real user data
        user_data = await self.config.user(ctx.author).all()  # Use the 'all' method to get all data associated with the user

        if not user_data.get("scores"):  # Simplified check for scores
            await ctx.send("You have no confidants yet!")
            return

        message = "🏆 Confidants 🏆\n\n"
        for confidant_id, score in user_data["scores"].items():
            level = await self._calculate_level(score)
            stars = await self._generate_star_rating(level)
            message += f"<@{confidant_id}>: {stars} `{score} pts` \n"  # Use confidant_id directly
        message += f"\nAggregate Score: {user_data.get('aggregate_score', 0)} pts"

        await ctx.send(message)

    @sociallink.command()
    async def rank(self, ctx):
        """Show's a server-wide ranking of users based on their aggregate confidant score."""
        mock_data = {
            "289198795625857026": {
                "scores": {
                    "393266291261308938": 0,
                    "863149927340572723": 0,
                },
                "aggregate_score": 0,
            },
            "393266291261308938": {
                "scores": {
                    "289198795625857026": 0,
                    "863149927340572723": 0,
                },
                "aggregate_score": 0,
            },
            "863149927340572723": {
                "scores": {
                    "289198795625857026": 0,
                    "393266291261308938": 0,
                },
                "aggregate_score": 0,
            },
        }

        # Sorting users based on their aggregate score in descending order
        sorted_users = sorted(
            mock_data.items(), key=lambda x: x[1]["aggregate_score"], reverse=True
        )

        # Formatting the output
        rank_message = "👥 Rankings 👥\n\nForge unbreakable bonds and rise through the ranks!\n\n"
        for rank, (user_id, data) in enumerate(sorted_users, start=1):
            rank_message += f"{rank}. {user_id} ({data['aggregate_score']} pts)\n"

        await ctx.send(rank_message)

    @sociallink.command()
    async def journal(self, ctx):
        """Shows a list of events that increased links between users."""
        user_id = str(ctx.author.id)
        user_journal = await self.config.user_from_id(int(user_id)).journal()

        if not user_journal:
            await ctx.send("Your journal is empty. Time to get out there!")
            return

        message = "📔 Journal 📔\n\n"
        for entry in user_journal:
            timestamp = entry["timestamp"]
            confidant_id = entry["confidant_id"]
            description = entry["description"]
            message += f"- {timestamp}: {description} with <@{confidant_id}>\n"

        await ctx.send(message)

    # Event Handlers
    async def handle_link(self, ctx, user_id1: int, user_id2: int, score_increment: int, event_type: str, details: str = ""):
        """Handles updating social links and scores, potentially triggering level increases and journal entries.

        """
        try:
            all_users = await self.config.all_users()

            # 1. Fetch Existing Scores:
            user1_data = all_users.get(str(user_id1), {"scores": {}, "aggregate_score": 0})
            user2_data = all_users.get(str(user_id2), {"scores": {}, "aggregate_score": 0})

            # 2. Update Scores (bidirectional):
            user1_data["scores"][str(user_id2)] = user1_data["scores"].get(str(user_id2), 0) + score_increment
            user2_data["scores"][str(user_id1)] = user2_data["scores"].get(str(user_id1), 0) + score_increment

            # 3. Update Aggregate Scores:
            await self.update_aggregate_score(user_id1)
            await self.update_aggregate_score(user_id2)

            # 4. Calculate Levels:
            old_user1_level = await self._calculate_level(user1_data["scores"].get(str(user_id2), 0) - score_increment)
            old_user2_level = await self._calculate_level(user2_data["scores"].get(str(user_id1), 0) - score_increment)
            new_user1_level = await self._calculate_level(user1_data["scores"][str(user_id2)])
            new_user2_level = await self._calculate_level(user2_data["scores"][str(user_id1)])

            # 5. Check for Level Up & Announce if needed (only once per pair):
            if new_user1_level > old_user1_level or new_user2_level > old_user2_level:
                await self.announce_rank_increase(user_id1, user_id2, max(new_user1_level, new_user2_level))

            # 6. Create Journal Entries:
            timestamp = datetime.now()
            await self._create_journal_entry(event_type, user_id1, user_id2, timestamp, details or "No details provided.")

            # 7. Store Updated Data:
            await self.config.user_from_id(user_id1).set(user1_data)
            await self.config.user_from_id(user_id2).set(user2_data)

        except KeyError as e:
            logger.error(f"Key error accessing user data: {e}", exc_info=True)
        except TypeError as e:
            logger.error(f"Type error in data manipulation: {e}", exc_info=True)
        except Exception as e:
            logger.exception(f"An unexpected error occurred while handling link: {e}")
        else:
            logger.info(f"Successfully handled link between {user_id1} and {user_id2} for {event_type} with increment {score_increment}")

    # Helpers
    async def update_links(self, user1_id, user2_id, score):
        """Updates links for both users and recalculates aggregate scores."""
        # If initial rank, require a large event (VC chat) to "connect" the users
        # Otherwise, just update the score
        # For Mid-rank and final rank, require a large event to "connect" the users

    async def update_aggregate_score(self, user_id):
        """Recalculates the aggregate score for a user."""
        # ... (fetch links, calculate sum, update aggregate_score)

    async def _calculate_level(self, score):
        base_s_link = await self.config.base_s_link()
        level_exponent = await self.config.level_exponent()
        max_levels = await self.config.max_levels()
        level = 0
        while score >= base_s_link + (level ** level_exponent) and level < max_levels:
            score -= base_s_link + (level ** level_exponent)
            level += 1
        return min(level, max_levels)  # TODO: Add TIME DECAY
    
    async def _generate_star_rating(self, level):
        """
        Generates a star rating string based on the level.
        
        Parameters:
        level (int): The current level of the user.
        
        Returns:
        str: A string representing the star rating.
        """
        max_levels = await self.config.max_levels()
        stars = "★" * level + "☆" * (max_levels - level)
        return stars
    
    async def announce_rank_increase(self, user_id_1, user_id_2, level):
        user_1 = self.bot.get_user(int(user_id_1))
        user_2 = self.bot.get_user(int(user_id_2))
        stars = await self._generate_star_rating(level)

        if not user_1 or not user_2:
            logger.error("One or both users not found.")
            return

        # Define a multi-line template
        message_template = """
# Rank up!!!

## Confidant: {confidant_name}!

Your bond with {confidant_name} has grown stronger!
    
{stars}
    """

        # Function to format the message
        def format_message(confidant_name, stars):
            return message_template.format(confidant_name=confidant_name, stars=stars)

        # Format messages for each user
        message_for_user_1 = format_message(user_2.display_name, stars)
        message_for_user_2 = format_message(user_1.display_name, stars)

        try:
            # Send the formatted messages
            await user_1.send(message_for_user_1)
            await user_2.send(message_for_user_2)
            logger.info(f"Notified {user_1.display_name} and {user_2.display_name} of their increased social rank with stars.")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def _create_journal_entry(self, event_type, initiator_id, confidant_id, timestamp, details=None):
        """
        Creates a social link journal entry based on a Discord interaction.

        Args:
            event_type (str): The type of interaction (e.g., "mention", "reaction", "voice_chat").
            initiator_id (int): The Discord ID of the user who initiated the interaction.
            confidant_id (int): The Discord ID of the confidant (the other user involved).
            timestamp (datetime): The time the interaction occurred.
            details (str, optional): Additional details about the interaction.

        Returns:
            dict: The created journal entry.
        """

        entry = {
            "event_type": event_type,
            "initiator_id": str(initiator_id),
            "confidant_id": str(confidant_id),
            "timestamp": timestamp.isoformat(),
            "description": details,
        }

        user_journal = await self.config.user_from_id(initiator_id).journal()
        user_journal.append(entry)
        await self.config.user_from_id(initiator_id).journal.set(user_journal)
    

    # Listeners for sLink activity
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            if member.bot:
                logger.debug(f"Ignoring bot user: {member.display_name} ({member.id})")
                return

            now = datetime.now()
            user_id = str(member.id)
            today = now.date() # Not using the DateUtil here because it could cause issues with datetime.now()

            if user_id not in self.voice_sessions or self.voice_sessions[user_id]["last_interaction_date"] < today:
                logger.info(f"Initializing or resetting voice session for user: {member.display_name} ({member.id})")
                self.voice_sessions[user_id] = {"channel": None, "start": None, "interactions": {}, "last_interaction_date": today}

            if before.channel is None and after.channel is not None:
                logger.info(f"User {member.display_name} ({member.id}) joined voice channel: {after.channel.id}")
                self.voice_sessions[user_id]["channel"] = after.channel.id
                self.voice_sessions[user_id]["start"] = now

            elif before.channel is not None and (after.channel is None or before.channel.id != after.channel.id):
                logger.info(f"User {member.display_name} ({member.id}) left or switched from voice channel: {before.channel.id}")
                await self._update_interaction_time(user_id, before.channel.id, now)

                if after.channel is None:
                    self.voice_sessions[user_id]["channel"] = None
                    self.voice_sessions[user_id]["start"] = None
                else:
                    self.voice_sessions[user_id]["channel"] = after.channel.id
                    self.voice_sessions[user_id]["start"] = now

        except Exception as e:
            logger.error(f"Error handling voice state update for {member.display_name} ({member.id}): {e}", exc_info=True)

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

