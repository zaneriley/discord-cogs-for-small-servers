import logging
from abc import ABC, abstractmethod
import uuid

from discord.errors import NotFound, Forbidden, HTTPException

class Poll(ABC):

    def __init__(self, bot, config, guild, poll_type):
        self.bot = bot
        self.config = config
        self.guild = guild
        self.poll_id = poll_type
        self.message_id = None
        self.poll_channel_id = None
        self.buttons = []

        # Store the poll data under its unique id
        self.config.register_guild(polls={self.poll_id: { "votes": {}, "user_votes": {} }})
        logging.debug(f"Poll initialized with poll id: {self.poll_id}")

    def set_message_id(self, new_id):
        self.message_id = new_id

    def set_poll_channel_id(self, new_id):
        self.poll_channel_id = new_id

    def add_buttons(self, button):
        self.buttons.append(button)

    @abstractmethod
    def start_poll(self):
        pass

    @abstractmethod
    def end_poll(self):
        pass

    async def restore_poll(self):
        is_poll_active = await self.is_active()
        if is_poll_active:
            channel_id = await self.config.poll_channel_id()
            message_id = await self.config.poll_message_id()
            poll_message = await self._fetch_poll_message(channel_id, message_id)
            if poll_message is None:
                return
            view = await self.build_view()
            await poll_message.edit(view=view)

    @abstractmethod
    async def keep_poll_alive(self):
        pass

    async def is_active(self):
        return self.poll_id in self.bot.get_cog("MovieClub").active_polls

    @abstractmethod
    def get_votes(self):
        pass

    @abstractmethod
    def get_user_votes(self):
        pass

    async def refresh_buttons(self):
        # This exists because Discord will make the buttons inactive after a few minutes
        # Check if the poll is active.
        is_poll_active = await self.is_active()
        if is_poll_active:
            logging.debug("Refreshing buttons...")
            channel_id, message_id = await self.get_poll_message_details()
            poll_message = await self._fetch_poll_message(channel_id, message_id)
            if poll_message:
                try:
                    logging.debug("Editing message...")
                    view = await self.build_view()
                    await poll_message.edit(view=view)
                    logging.debug("Message edited.")
                except HTTPException as e:
                    logging.debug(f"Unable to edit the message due to {e}. Setting the poll to inactive.")
                    await self.set_active_status(False)
        else:
            logging.debug("The poll is inactive. Skipping the refresh operation.") 

    @abstractmethod
    async def get_poll_message_details(self): 
        pass
    
    async def _fetch_poll_message(self, channel_id: int, message_id: int):
        # Fetches and returns the message related to the poll.
        channel = self.bot.get_channel(channel_id)
        try:
            logging.debug("Fetch message...")
            return await channel.fetch_message(message_id)
        except NotFound:
            logging.debug("Poll message not found.")
            return None

    @abstractmethod
    async def build_view(self): 
        pass

    @abstractmethod
    async def send_initial_message(self):
        pass

    @abstractmethod
    async def send_update_message(self):
        pass

    @abstractmethod
    async def send_result_message(self):
        pass

    async def is_active(self): 
        return await self.config.is_date_poll_active()

    async def set_active_status(self, is_active: bool): 
        await self.config.is_date_poll_active.set(is_active)