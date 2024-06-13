import asyncio
import logging
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
    ON_VOICE_CHANNEL_LEAVE = "on_voice_channel_leave"
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
            cls._instance.events = {}
            cls._instance.config = None
            cls._instance.bot = None
        return cls._instance

    def __init__(self):
        self.events = {
            Events.ON_LEVEL_UP: [],
            Events.ON_SOCIAL_LINK: [],
            Events.ON_JOURNAL_ENTRY: [],
            Events.ON_MESSAGE_MENTION: [],
            Events.ON_MESSAGE_QUOTE: [],
            Events.ON_MESSAGE_WITH_MEDIA_ATTACHENT: [],
            Events.ON_AVATAR_CHANGE: [],
        }

    def set_config(self, config):
        self.config = config

    def register_bot(self, bot):
        self.bot = bot

    def subscribe(self, event_name):
        def decorator(func):
            if event_name not in self.events:
                self.events[event_name] = []
            if hasattr(func, "__self__"):
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
                        asyncio.create_task(handler(self, bot=self.bot, config=self.config, *args, **kwargs))
                    else:
                        handler(config=self.config, *args, **kwargs)
                except Exception as e:
                    logger.exception("Error in handler %s for event %s:\n %s", handler, event_name, e)
        else:
            logger.warning("No handlers found for event: %s", event_name)


event_bus = EventBus()
