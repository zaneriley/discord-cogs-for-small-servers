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
        self.config.register_guild(polls={}, target_role=None)
        self.active_polls = {}  
        self.polls = {}
        # self.config.register_poll(poll_id="", votes={}, user_votes={}) 
        self.keep_poll_alive.start()
    
    async def get_all_active_polls_from_config(self, guild):
        return await self.config.guild(guild).polls()
    
    @tasks.loop(minutes=3)
    async def keep_poll_alive(self):
        error_polls = []
        for poll in self.active_polls.values():
            try:
                await poll.keep_poll_alive() 
            except Exception as e:
                message_id = await poll.get_message_id()
                logging.error(f"Unable to keep poll {message_id} alive due to: {str(e)}") 
                error_polls.append(poll.poll_id)
        for error_poll in error_polls:
            del self.active_polls[error_poll]
    
    @keep_poll_alive.before_loop
    async def before_refresh_buttons(self):
        await self.bot.wait_until_ready()

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
    
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            restoring_polls = await self.get_all_active_polls_from_config(guild)
            for poll_id in restoring_polls.keys():
                if poll_id == "date_poll":
                    self.active_polls[poll_id] = DatePoll(self.bot, self.config, guild)
                elif poll_id == "movie_poll":
                    pass
        
        for poll in self.active_polls.values():
            try:
                await poll.restore_poll()
            except Exception as e:
                logging.error(f"Unhandled exception in on_ready during poll restoration: {e}")

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

    @commands.guild_only()  
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @poll.command()
    async def date(self, ctx, action: str, month: str = None):
        target_role = await self.config.guild(ctx.guild).target_role()

        if action.lower() == "start":
            try:
                if "date_poll" in self.active_polls.keys():    # proceed if poll is active
                    # is_date_poll_active = await self.active_polls[Poll.poll_id].is_active()
                    # if is_date_poll_active:
                    await ctx.send('A date poll is already active.')
                    return
                else:
                    poll = DatePoll(self.bot, self.config, ctx.guild)
                    await poll.write_poll_to_config()
                    await poll.start_poll(ctx, action, month)
                    self.active_polls["date_poll"] = poll  # add poll to active polls using new poll_id
                    await ctx.send('A date poll is activated.')

            except AttributeError:
                await ctx.send(f"Error: Unable to initialize date poll. For some reason, the Poll object could not be created.")
                logging.exception("Failed to initialize date poll.")

        elif action.lower() == "end":
            if "date_poll" in self.active_polls.keys():   # check if poll is in active polls using new poll_id
                await self.active_polls["date_poll"].end_poll(ctx)
                del self.active_polls["date_poll"]  # remove poll from active polls using new poll_id
            else:
                await ctx.send('No active date poll in this channel.')
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

    @commands.guild_only()  
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movieclub.command(name='setrole')
    async def set_target_role(self, ctx, role: discord.Role):
        """Sets the role for which to count the total members in polls. Default is @everyone."""
        await self.config.guild(ctx.guild).target_role.set(role.id)
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
