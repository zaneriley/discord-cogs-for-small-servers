import asyncio
import logging
from datetime import UTC, datetime
from functools import partial

logger = logging.getLogger(__name__)


class Events:
    ON_LEVEL_UP = "on_level_up"
    ON_SOCIAL_LINK = "on_social_link"
    ON_JOURNAL_ENTRY = "on_journal_entry" 

    # # Messaging
    ON_MESSAGE_MENTION = "on_message_mention"
    # ON_MESSAGE_MENTION_RECIPROCATED = "on_message_mention_reciprocated"
    ON_MESSAGE_QUOTE = "on_message_quote"
    ON_MESSAGE_WITH_MEDIA_ATTACHENT = "on_message_with_media_attachment"

    # # Reactions
    # ON_REACTION_ADD = "on_reaction_add"
    # ON_REACTION_ADD_RECIPROCATED = "on_reaction_add_reciprocated"

    # # Voice Channels
    ON_VOICE_CHANNEL_JOIN = "on_voice_channel_join" 
    # ON_VOICE_CHANNEL_EXTENDED_STAY = "on_voice_channel_extended_stay"
    # ON_VOICE_CHANNEL_SCREEN_SHARE = "on_voice_channel_screen_share"

    # # Threads
    # ON_THREAD_CREATE = "on_thread_created"
    # ON_THREAD_PARTICIPATION = "on_thread_participation"

    # # Events (RSVPs)  # noqa: ERA001
    # ON_EVENT_RSVP = "on_event_rsvp"

    # Profile changes
    ON_AVATAR_CHANGE = "on_avatar_change"

    # # Gaming (If Applicable)
    # ON_ACHIEVEMENT_UNLOCKED = "on_achievement_unlocked"

class EventBus:

    """
    Event bus for managing events in a Discord bot.
    This works as a singleton, so there's only one instance of the EventBus class.
    The EventBus class is responsible for managing the event bus and dispatching events to subscribers.

    Attributes
    ----------
    events: dict
        A dictionary that maps event names to lists of subscribers.
        Each subscriber is a function that takes a single argument, which is the event data.

    Methods
    -------
    subscribe(event_name)
        Subscribes a function to a specific event.
        The function will be called whenever the event is dispatched.

    fire(event_name, *args, **kwargs)
        Dispatches an event to all subscribers.
        The event data will be passed as arguments to the subscribers.

    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.events = {}  # noqa: SLF001
            cls._instance.config = None
        return cls._instance

    def __init__(self):
        self.events = {Events.ON_LEVEL_UP: []}

    def set_config(self, config):
        self.config = config

    def subscribe(self, event_name):
        def decorator(func):
            if event_name not in self.events:
                self.events[event_name] = []
            # Check if the function is an instance method
            if hasattr(func, "__self__"):
                # Bind the instance method to its instance
                bound_func = partial(func, func.__self__)
                self.events[event_name].append(bound_func)
            else:
                self.events[event_name].append(func)
            logger.debug("Subscriber %s subscribed to event %s\n", func, event_name)
            logger.debug("Current events registered: %s\n\n", self.events)
            return func

        return decorator

    def fire(self, event_name, *args, **kwargs):
        logger.debug("Current events registered: %s", self.events)
        logger.debug("Firing event: %s", event_name)
        if event_name in self.events:
            for handler in self.events[event_name]:
                try:
                    logger.debug("Handling event %s with handler %s", event_name, handler)
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(self, config=self.config, *args, **kwargs))
                    else:
                        handler(config=self.config, *args, **kwargs)
                except Exception as e:
                    logger.exception("Error in handler %s for event %s:\n %s", handler, event_name, e)
        else:
            logger.warning("No handlers found for event: %s", event_name)

event_bus = EventBus()


class EventManager:
    def __init__(self, config, level_manager, confidants_manager):
        self.config = config
        self.level_manager = level_manager
        self.confidants_manager = confidants_manager
        self.voice_sessions = {}

    async def on_voice_state_update(self, member, before, after):
        try:
            if member.bot:
                logger.debug(f"Ignoring bot user: {member.display_name} ({member.id})")
                return

            now = datetime.now(tz=UTC)
            user_id = str(member.id)
            today = now.date()

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

        except Exception:
            logger.exception("Error handling voice state update for %s (%s)", {member.display_name}, ({member.id}))

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
                        await self.level_manager.announce_rank_increase(user_id, other_user_id, 1)
                    other_session["interactions"][user_id] = new_interaction_time
                    session["interactions"][other_user_id] = new_interaction_time

        session["start"] = None
        logger.debug(f"Updated interaction time for User {user_id} after leaving/switching channel {channel_id}")

    async def on_level_up(self, event_data):
        user_1 = event_data["user_1"]
        user_2 = event_data["user_2"]
        level = event_data["level"]
        stars = event_data["stars"]

        journal_entry = await self.journal_manager.get_latest_journal_entry(user_1.id, user_2.id)

        # Create the embed with the journal entry (using your confidants_manager)
        embed = await self.confidants_manager.create_level_up_embed(
            username=user_2.display_name,
            journal_entry=journal_entry["description"] if journal_entry else "",
            rank=level,
            stars=stars,
            avatar_url=user_2.display_avatar.url,
            level_up=True,
        )

        await user_1.send(content=f"## Rank up!!\n\n# <@{user_2.id}> \n", embed=embed)
