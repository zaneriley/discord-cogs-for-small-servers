import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..utilities.discord_utils import send_discord_message

logger = logging.getLogger(__name__)


class MessageScheduler:
    def __init__(self, scheduler: AsyncIOScheduler | None = None):
        """
        Initialize the MessageScheduler with an optional scheduler.
        """
        self.scheduler = scheduler or AsyncIOScheduler()
        self.scheduler.start()
        logger.info("MessageScheduler initialized.")

    async def _scheduled_message_job(self, channel_id: int, message_content: str, role_id: int | None = None):
        """
        Internal job to be scheduled for sending the message.
        """
        try:
            formatted_message = self._format_message(message_content, role_id)
            await send_discord_message(channel_id, formatted_message)
            logger.info(f"Sent scheduled message to channel {channel_id}.")
        except Exception as e:
            logger.error(f"Failed to send scheduled message to channel {channel_id}: {e}")

    def _format_message(self, message: str, role_id: int | None = None) -> str:
        """
        Format the message with role mention if provided.
        """
        if role_id:
            logger.debug(f"Adding role mention for role {role_id} to message.")
            return f"<@&{role_id}>\n{message}"
        return message

    def schedule_message(
        self,
        channel_id: int,
        trigger_time: datetime.datetime,
        message_content: str,
        role_id: int | None = None,
    ):
        """
        Schedule a message to be sent to the specified channel at the given time.
        """
        if trigger_time <= datetime.datetime.now():
            logger.error("Provided trigger_time is in the past. Cannot schedule message.")
            raise ValueError("Please provide a future time for scheduling the message.")

        try:
            self.scheduler.add_job(
                self._scheduled_message_job,
                "date",
                run_date=trigger_time,
                args=(channel_id, message_content, role_id),
            )
            logger.info(f"Scheduled message for channel {channel_id} at {trigger_time}.")
        except Exception as e:
            logger.error(f"Failed to schedule message for channel {channel_id} at {trigger_time}: {e}")
            raise
