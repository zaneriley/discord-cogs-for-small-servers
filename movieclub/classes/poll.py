import logging
from abc import ABC, abstractmethod
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional

from discord.errors import NotFound, Forbidden, HTTPException

class Poll(ABC):

    def __init__(self, 
                 bot, 
                 config, 
                 guild: int, 
                 poll_type: str,
                 ):
        self.bot = bot
        self.config = config
        self.guild = guild
        self.poll_id = poll_type

        # Store the poll data under its unique id
        # self.config.register_guild(polls={self.poll_id: { "votes":{},"user_votes":{}, "buttons":[], "target_role":None, "poll_message_id":None, "poll_channel_id":None}})

        logging.debug(f"Poll initialized with poll id: {self.poll_id}")

    async def write_poll_to_config(self):
        guild_group = self.config.guild(self.guild)
        async with guild_group.polls() as polls:
          polls[self.poll_id] = {"votes":{},"user_votes":{}, "buttons":[], "poll_message_id":None, "poll_channel_id":None}

    async def remove_poll_from_config(self):
        guild_group = self.config.guild(self.guild)
        async with guild_group.polls() as polls:
          polls.pop(self.poll_id)
   
    async def get_votes(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "votes")
    
    async def set_votes(self, votes):
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "votes", value=votes)

    async def get_user_votes(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "user_votes")
    
    async def set_user_votes(self, user_votes):
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "user_votes", value=user_votes)

    async def get_target_role(self):
        return await self.config.guild(self.guild).target_role()
    
    async def get_message_id(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "poll_message_id")

    async def set_message_id(self, new_id):
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "poll_message_id", value=new_id)

    async def get_poll_channel_id(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "poll_channel_id")
    
    async def set_poll_channel_id(self, new_id):
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "poll_channel_id", value=new_id)

    async def get_buttons(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "buttons")

    async def add_buttons(self, buttons):
        existing_buttons = await self.get_buttons()
        for button in buttons:
            existing_buttons.append(button)
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "buttons", value=buttons)

    @abstractmethod
    def start_poll(self):
        pass

    @abstractmethod
    def end_poll(self):
        pass

    @abstractmethod
    async def restore_poll(self):
        pass

    @abstractmethod
    async def keep_poll_alive(self):
        pass

    async def is_active(self):
        return self.poll_id in self.bot.get_cog("MovieClub").active_polls

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
    
    async def _fetch_poll_message(self):
        channel_id = await self.get_poll_channel_id()
        message_id = await self.get_message_id()
        logging.debug(f"Fetching message with id {message_id} from channel {channel_id}")
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