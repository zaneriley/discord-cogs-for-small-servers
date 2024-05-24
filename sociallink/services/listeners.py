import logging

import discord
from redbot.core import commands

from sociallink.services.events import (
    Events,
    event_bus,  # import singleton
)
from sociallink.services.metrics_tracker import MetricsTracker  # Import your MetricsTracker class
from utilities.image_utils import get_image_handler

logger = logging.getLogger(__name__)


class ListenerManager(commands.Cog):
    def __init__(self, config, event_bus):
        self.config = config
        self.event_bus = event_bus

    async def on_message(self, message):
        """
        Listens for messages and fires the appropriate event.
        - On message with media attachment: ON_MESSAGE_WITH_MEDIA_ATTACHENT
        - On message quote/reply: ON_MESSAGE_QUOTE
        - On message mention: ON_MESSAGE_MENTION
        """
        if message.attachments:
            self.event_bus.fire(Events.ON_MESSAGE_WITH_MEDIA_ATTACHENT, message=message)
            logger.debug("Received event %s, message: %s", Events.ON_MESSAGE_WITH_MEDIA_ATTACHENT, message)
            await MetricsTracker.log_event("message_with_media_attachment", {"message_id": message.id})  # Log the event
        if message.reference is not None:
            # note that message.reference.resolved can be either a discord.Message or discord.DeletedReferencedMessage object.
            # If it's a discord.DeletedReferencedMessage object, the author attribute will not be available,
            # so we check the type of message.reference.resolved before accessing the author attribute.
            replied_to = (
                message.reference.resolved.author if isinstance(message.reference.resolved, discord.Message) else None
            )
            self.event_bus.fire(Events.ON_MESSAGE_QUOTE, message=message, replied_to=replied_to)
            logger.debug("Received event %s, message: %s, replied_to: %s", Events.ON_MESSAGE_QUOTE, message, replied_to)
            await MetricsTracker.log_event("message_quote", {"message_id": message.id, "replied_to_id": replied_to.id if replied_to else None})  # Log the event
        if message.mentions:
            for member in message.mentions:
                self.event_bus.fire(Events.ON_MESSAGE_MENTION, message=message, mentioned_member=member)
                logger.debug(
                    "Received event %s, message: %s, mentioned_member: %s", Events.ON_MESSAGE_MENTION, message, member
                )
                await MetricsTracker.log_event("message_mention", {"message_id": message.id, "mentioned_member_id": member.id})  # Log the event


    # Voice channel listeners
    async def on_voice_state_update(self, member, before, after):
        """Listens for voice state updates and fires the appropriate event."""
        if before.channel is None and after.channel is not None:
            self.event_bus.fire(Events.ON_VOICE_CHANNEL_JOIN, member=member, channel=after.channel)
            logger.debug(
                "Received event %s, member: %s, channel: %s", Events.ON_VOICE_CHANNEL_JOIN, member, after.channel
            )
            await MetricsTracker.log_event("voice_channel_join", {"user_id": member.id, "channel_id": after.channel.id})
        elif before.channel is not None and after.channel is None:
            self.event_bus.fire(Events.ON_VOICE_CHANNEL_LEAVE, member=member, channel=before.channel)
            logger.debug(
                "Received event %s, member: %s, channel: %s", Events.ON_VOICE_CHANNEL_LEAVE, member, before.channel
            )
            await MetricsTracker.log_event("voice_channel_leave", {"user_id": member.id, "channel_id": before.channel.id})

    # Member profile listeners
    async def on_member_update(self, before, after):
        """Event listener to update emojis when a member's avatar changes."""
        if before.avatar != after.avatar:
            self.event_bus.fire(Events.ON_AVATAR_CHANGE, member=after)
            logger.debug("Received event %s, member: %s", Events.ON_AVATAR_CHANGE, after)
            await MetricsTracker.log_event("avatar_change", {"member_id": after.id})  # Log the event

    # TODO:Move where appropriate
    @event_bus.subscribe(Events.ON_MESSAGE_WITH_MEDIA_ATTACHENT)
    async def handle_message_with_media_attachment(self, config, message):
        logger.debug("Received event %s", Events.ON_MESSAGE_WITH_MEDIA_ATTACHENT)
        for attachment in message.attachments:
            if attachment.content_type.startswith("image/") or attachment.content_type.startswith("video/"):
                image_handler = get_image_handler(attachment.url)
                image_data = await image_handler.fetch_image_data()
                # Process the image_data as needed
                logger.info("Processed media attachment for message %s", message.id)
