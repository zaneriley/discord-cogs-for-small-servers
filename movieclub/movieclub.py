# Standard library imports
import logging
from typing import Literal, List

# Third-party library imports
import discord
from discord import ui, Embed, Button, ButtonStyle, ActionRow
from discord.ext import tasks, commands
from discord.errors import NotFound, Forbidden, HTTPException

# Application-specific imports
from redbot.core import commands, Config
from redbot.core.bot import Red

# Local imports
from .classes.date_poll import DatePoll

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

class MovieClub(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=289198795625857026, force_registration=True)
        self.config.register_global(date_votes={}, is_date_poll_active=False, date_user_votes={}, date_buttons=[], target_role=None, poll_message_id=None, poll_channel_id=None)
        self.date_poll = DatePoll(self.bot, self.config)   # Pass both bot and config
        
    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Restores the poll if the bot restarts while the poll is active."""
        await self.date_poll.restore_poll()
        try:
            logging.debug("Starting on_ready listener...")
            self.refresh_poll_buttons.start()
            logging.debug("Ending on_ready listener...")
        except Exception as e:
            logging.error(f"Unhandled exception in on_ready: {e}")

    def create_poll(self, poll_type):
        if poll_type == "date":
            return DatePoll(self.config)
        else:
            raise ValueError(f"Invalid poll_type: {poll_type}")
        
    @commands.group()
    @commands.bot_has_permissions(send_messages=True)
    async def movieclub(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid Movie Club command passed...')

    @movieclub.group()
    async def poll(self, ctx):
        if ctx.invoked_subcommand is None:
            # Check for required permissions
            permissions = ctx.channel.permissions_for(ctx.guild.me)
            if not permissions.send_messages:
                await ctx.author.send('I do not have permissions to send messages in the channel.')
            else:
                await ctx.send('Invalid poll command passed TEST!!!..')

    @commands.guild_only()  # type:ignore
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @poll.command()
    async def date(self, ctx, action: str, month: str = None):
        """Start or end a date poll to choose the next movie night date."""
        if action.lower() == "start":
            await self.date_poll.start_poll(ctx, action, month)
        elif action.lower() == "end":
            await self.date_poll.end_poll(ctx)
        else:
            await ctx.send('Invalid action. Use "start" or "end".')

    @commands.guild_only()  # type:ignore
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movieclub.command()
    async def movie(self, ctx, action: str, movie_info: str = None):
        if action == "add":
            # Add movie
            pass
        elif action == "remove":
            # Remove movie
            pass
        else:
            await ctx.send('Invalid action. Use "add" or "remove".')

    @commands.guild_only()  # type:ignore
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @poll.command()
    async def movie(self, ctx, action: str):
        if action == "start":
            # Start movie poll
            pass
        elif action == "end":
            # End movie poll
            pass
        else:
            await ctx.send('Invalid action. Use "start" or "end".')

    @tasks.loop(minutes=3)
    async def refresh_poll_buttons(self, poll_type):
        """Background task to refresh poll buttons."""
        logging.debug("Starting refresh buttons task...")
        try:
            poll_object = self.create_poll(poll_type)
            if poll_object is None:
                logging.error("Poll object not created.")
                return
            is_poll_active = await poll_object.is_active()
            if not is_poll_active:
                logging.info(f"No active {poll_type} poll found.")
                return
            await poll_object.refresh_buttons()
            logging.debug("Ending refresh buttons task...")
        except ValueError as e:
            logging.error(str(e))
        except Exception as e:
            logging.error(f"Unhandled exception in refresh_poll_buttons: {e}")
        finally:
            logging.debug("Ending refresh buttons task...")
            
    @refresh_poll_buttons.before_loop
    async def before_refresh_buttons(self):
        await self.bot.wait_until_ready()

    @commands.guild_only()  # type:ignore
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movieclub.command(name='setrole')
    async def set_target_role(self, ctx, role: discord.Role):
        """Sets the role for which to count the total members in polls. Default is @everyone."""
        await self.config.target_role.set(role.id)
        await ctx.send(f"The role for total member count in polls has been set to {role.name}.")

    @commands.guild_only()  # type:ignore
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    async def restore_polls(self):
        """Restores the poll if the bot restarts while the poll is active."""
        await self.date_poll.restore_poll()

    @movieclub.command(name='hellothread')
    async def hellothread(self, ctx, channel_id: int):
        """Tries to create a forum post in the specified channel."""
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            await ctx.send("Invalid channel ID.")
            return
        thread = await channel.create_thread(name="Hello World Thread", content="This is the first message in the thread.")
        await thread.send("Hello, World!")
