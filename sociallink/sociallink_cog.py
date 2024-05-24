import logging
import os

import discord
from dotenv import load_dotenv
from redbot.core import Config, commands
from redbot.core.commands import has_permissions

from utilities.discord_utils import PaginatorView

from .commands.admin import AdminManager
from .commands.confidants import ConfidantsManager
from .commands.journal import JournalManager
from .commands.rank import RankManager
from .services.events import EventManager, event_bus
from .services.leveling import LevelManager
from .services.listeners import ListenerManager
from .services.metrics_tracker import MetricsTracker
from .services.slinks import SLinkManager

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: Update this to properly load from the .env file
IDENTIFIER = int(os.getenv("IDENTIFIER", "1234567890"))
GUILD_ID = int(os.getenv("GUILD_ID", "947277446678470696"))


# TODO:
# - Log basic metrics
# - Handle basic events to generate exp
# - Add emoji handling (refactor emojilocker)

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
        self.event_bus = event_bus
        self.event_bus.set_config(self.config)
        self.rank_manager       = RankManager(self.config)
        self.journal_manager    = JournalManager(self.config, self.event_bus)
        self.level_manager      = LevelManager(self.config, self.event_bus)
        self.slink_manager      = SLinkManager(self.bot, self.config, self.event_bus)
        self.confidants_manager = ConfidantsManager(self.bot, self.config, self.level_manager)
        self.event_manager      = EventManager(self.config, self.level_manager, self.confidants_manager)
        self.listener_manager   = ListenerManager(self.config, self.event_bus)
        self.metrics_tracker    = MetricsTracker(self.bot, self.config, self.event_bus)
        self.admin_manager      = AdminManager(self.bot, self.config, self.level_manager, self.confidants_manager, self.journal_manager)

        # Register event listeners to fire events
        self.listener_manager = ListenerManager(self.config, self.event_bus)

        default_global = {
            "guild_id": GUILD_ID,
            # Social Link Settings
            # Controls how difficult it is to get a social link
            "base_s_link": 10,
            "level_exponent": 2,
            "max_levels": 10,
            "decay_rate": 2,  # LP/day
            "decay_interval": "daily",
            # Metrics Tracking
            "metrics_enabled": False,
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

    ################################
    # Admin commands               #
    ################################
    @sociallink.group()
    @has_permissions(administrator=True)
    async def admin(self, ctx):
        """Admin-only commands for managing social links."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid admin command.")

    @admin.command(name="settings")
    async def show_settings(self, ctx):
        """Shows the user's confidants and the score for each."""
        await self.admin_manager.show_settings(ctx)

    @admin.command(name="simulate")
    async def simulate_event(self, ctx, event_type: str, user1: discord.Member, user2: discord.Member):
        """Simulates a social link event between two users."""
        await self.admin_manager.simulate_event(ctx, event_type, user1, user2)

    @admin.command(name="add")
    async def add_points(self, ctx, user: discord.Member, points: int):
        """Add arbitrary points to yourself and another user."""
        await self.admin_manager.add_points(ctx, user, points)

    @admin.command(name="reset")
    async def reset(self, ctx, user: discord.Member):
        """Resets the social link scores, journals, and other data for a user."""
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send(f"Are you sure you want to reset all social link data for {user.display_name}? Type `yes` to confirm or `no` to cancel.")

        try:
            confirmation = await self.bot.wait_for("message", check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("Reset operation timed out.")
            return

        if confirmation.content.lower() == "yes":
            await self.admin_manager.reset_user_data(ctx, user)
        else:
            await ctx.send("Reset operation cancelled.")

    @admin.command(name="update_avatar_emojis")
    async def update_avatar_emojis(self, ctx):
        """Updates all user avatars as emojis in the specified guild and returns a mapping of user IDs to emoji IDs."""
        await self.admin_manager.update_avatar_emojis(ctx)

    @admin.command(name="journal_entry")
    async def test_journal_entry(self, ctx, user: discord.Member, *, event_details: str):
        """Create a journal entry with timestamp, author, and event details."""
        await self.admin_manager.test_journal_entry(ctx, user, event_details=event_details)

    ################################
    # Metrics Tracking             #
    ################################
    @sociallink.group()
    @has_permissions(administrator=True)
    async def metrics(self, ctx):
        """Commands for managing game metrics."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid metrics command passed.")

    @metrics.command(name="enable")
    async def enable_metrics(self, ctx):
        """Enable metrics tracking."""
        self.metrics_tracker.enable_metrics()
        await ctx.send("Metrics tracking enabled.")

    @metrics.command(name="disable")
    async def disable_metrics(self, ctx):
        """Disable metrics tracking."""
        self.metrics_tracker.disable_metrics()
        await ctx.send("Metrics tracking disabled.")

        """Generate a report of the game metrics."""
        success, message = self.metrics_tracker.generate_report()
        if success:
            await ctx.send("Report generated and sent.")
        else:
            await ctx.send(message)

    ################################
    # User facing commands         #
    ################################
    @commands.hybrid_command(name="confidants", aliases=["sociallink_confidants"])
    async def confidants(self, ctx: commands.Context):
        """Check your bonds with friends and allies."""
        await self.confidants_manager.confidants(ctx)

    @sociallink.command()
    async def rank(self, ctx):
        """Show's a server-wide ranking of users based on their aggregate confidant score."""
        user_id = ctx.author.id
        rank_message = await self.rank_manager.get_rankings_leaderboard(user_id)
        await ctx.send(rank_message)

    @sociallink.command()
    async def journal(self, ctx, entries_per_page: int = 10):
        """Shows a list of events that increased links between users."""
        try:
            pages = await self.journal_manager.display_journal(ctx.author, entries_per_page)
            paginator = PaginatorView(pages)
            await ctx.send(pages[0], view=paginator)
        except Exception:
            logger.exception("Error processing journal for user %s", {ctx.author.id})
            await ctx.send("An error occurred while retrieving your journal. Please try again later.")

    ################################
    # Event listeners              #
    ################################
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # TODO: Move to avatars.py and use eventbus
        """
        Event listener to update emojis when a member's avatar changes.
        """
        if before.avatar != after.avatar:
            guild = after.guild
            try:
                avatar_data = await self.confidants_manager.fetch_user_avatar(after)
                if avatar_data:
                    emoji_id = await self.confidants_manager.upload_avatar_as_emoji(guild, after, avatar_data)
                    if emoji_id:
                        await self.config.user(after).set_raw("emoji_id", value=emoji_id)
                        logger.info(f"Updated emoji for {after.display_name}")
            except Exception:
                logger.exception("Failed to update avatar for %s", {after.display_name})

    @commands.Cog.listener()
    async def on_message(self, message):
        """Event listener to track message activity."""
        await self.listener_manager.on_message(message)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Event listener to track voice channel activity."""
        await self.listener_manager.on_voice_state_update(member,before,after)

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
