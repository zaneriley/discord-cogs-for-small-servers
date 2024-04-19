from utilities.date_utils import DateUtil

from redbot.core import Config, commands


import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: Update this to properly load from the .env file
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))


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
            "decay_rate": 2,  # LP/day
            "decay_interval": "daily",
        }
        default_user = {"scores": {}, "aggregate_score": 0}
        self.config.register_global(**default_global)
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
        async with self.config.all_users() as all_users:
            for member in members:
                if (
                    member.bot
                ):  # Skip bot accounts to avoid unnecessary data storage
                    continue
                user_scores = all_users.get(str(member.id), {}).get("scores", {})
                for other_member in members:
                    if (
                        other_member.id == member.id or other_member.bot
                    ):  # Skip self and bots
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

    @sociallink.command(aliases=["friends", "confidents"])
    async def confidants(self, ctx):
        """Shows the user's confidants and the score for each."""
        user_id = str(ctx.author.id)

        mock_data = {
            "289198795625857026": {
                "scores": {
                    "393266291261308938": 120,
                    "863149927340572723": 200,
                },
                "aggregate_score": 320,
            },
            "393266291261308938": {
                "scores": {
                    "289198795625857026": 120,
                    "863149927340572723": 150,
                },
                "aggregate_score": 270,
            },
            "863149927340572723": {
                "scores": {
                    "289198795625857026": 200,
                    "393266291261308938": 150,
                },
                "aggregate_score": 350,
            },
        }

        user_data = mock_data.get(user_id, {})

        if not user_data or "scores" not in user_data or not user_data["scores"]:
            await ctx.send("You have no confidants yet!")
            return

        message = "🏆 Confidants 🏆\n\n"
        for confidant_id, score in user_data["scores"].items():
            level = await self.calculate_level(score)
            stars = "★" * level + "☆" * (10 - level)
            message += f"<@{confidant_id}>: {stars} `{score} pts` \n"
        message += f"\nAggregate Score: {user_data.get('aggregate_score', 0)} pts"

        await ctx.send(message)

    @sociallink.command()
    async def rank(self, ctx):
        """Show's a server-wide ranking of users based on their aggregate confidant score."""
        mock_data = {
            "289198795625857026": {
                "scores": {
                    "393266291261308938": 120,
                    "863149927340572723": 200,
                },
                "aggregate_score": 320,
            },
            "393266291261308938": {
                "scores": {
                    "289198795625857026": 120,
                    "863149927340572723": 150,
                },
                "aggregate_score": 270,
            },
            "863149927340572723": {
                "scores": {
                    "289198795625857026": 200,
                    "393266291261308938": 150,
                },
                "aggregate_score": 350,
            },
        }

        # Sorting users based on their aggregate score in descending order
        sorted_users = sorted(
            mock_data.items(), key=lambda x: x[1]["aggregate_score"], reverse=True
        )

        # Formatting the output
        rank_message = "👥 Social Link Rankings 👥\n\nForge unbreakable bonds and rise through the ranks!\n\n"
        for rank, (user_id, data) in enumerate(sorted_users, start=1):
            rank_message += f"{rank}. {user_id} ({data['aggregate_score']} pts)\n"

        await ctx.send(rank_message)

    @sociallink.command()
    async def journal(self, ctx):
        """Shows a list of events that increased links between users."""
        await ctx.send("Hello World from journal!")

    # Event Handlers
    async def handle_link(self, ctx, score: int):
        """Sets the social link score between the author and another user."""
        # ... (update links, recalculate aggregate scores)

    # Helpers
    async def update_links(self, user1_id, user2_id, score):
        """Updates links for both users and recalculates aggregate scores."""
        # If initial rank, require a large event (VC chat) to "connect" the users
        # Otherwise, just update the score
        # For Mid-rank and final rank, require a large event to "connect" the users

    async def update_aggregate_score(self, user_id):
        """Recalculates the aggregate score for a user."""
        # ... (fetch links, calculate sum, update aggregate_score)

    async def calculate_level(self, score):
        base_s_link = await self.config.base_s_link()
        level_exponent = await self.config.level_exponent()
        level = 0
        while score >= base_s_link + (level**level_exponent):
            level += 1
            score -= base_s_link + (level**level_exponent)
        return level  # TODO: Add TIME DECAY

    # Listeners for sLink activity
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            logging.info(f"Voice state update for {member.display_name} ({member.id})")

            if member.bot:
                logging.debug("Ignoring bot's own voice state update.")
                return

            user_id = member.id
            now = DateUtil.now()

            if before.channel is None and after.channel is not None:
                logging.info(f"{member.display_name} joined voice channel {after.channel.name} ({after.channel.id})")
                self.voice_sessions[user_id] = {"start": now, "channel": after.channel.id}

            elif before.channel is not None and (after.channel is None or before.channel.id != after.channel.id):
                session = self.voice_sessions.pop(user_id, None)
                if session:
                    duration = (now - session["start"]).total_seconds()
                    logging.info(f"{member.display_name} left voice channel {before.channel.name} ({before.channel.id}) after {duration} seconds")
                    if duration >= 1800:  # 30 minutes
                        logging.info(f"Updating social link points for {member.display_name} due to session duration.")
                        await self.update_social_link_points(member, session["channel"])
                    else:
                        logging.info(f"Session duration for {member.display_name} was less than 30 minutes; no points updated.")
                else:
                    logging.warning(f"No session found for {member.display_name} ({member.id}) on voice state update.")
        except Exception as e:
            logging.error(f"Error handling voice state update for {member.display_name} ({member.id}): {e}")
