# Standard library imports
import logging
from collections import defaultdict
from typing import Literal

# Third-party library imports
import discord
from discord.errors import HTTPException
from discord.ext import tasks

# Application-specific imports
from redbot.core import Config, commands
from redbot.core.bot import Red

from movieclub.api_handlers.movie_data_fetcher import get_movie_discord_embed

# Local imports
from movieclub.classes.date_poll import DatePoll
from movieclub.classes.movie_poll import MoviePoll
from utilities.discord_utils import create_discord_thread

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class MovieClub(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=289198795625857026, force_registration=True)
        self.config.register_guild(polls={}, target_role=None, movies={})
        self.active_polls = {}
        self.polls = {}
        self.movies = {}
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
            except HTTPException as http_e:
                message_id = await poll.get_message_id()
                logging.exception(f"HTTPException while keeping poll {message_id} alive: {http_e}")
                error_polls.append(poll.poll_id)
            except Exception as e:
                message_id = await poll.get_message_id()
                logging.exception(f"Unable to keep poll {message_id} alive due to: {e!s}")
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
                    self.active_polls[poll_id] = MoviePoll(self.bot, self.config, guild)

        for poll in self.active_polls.values():
            try:
                await poll.restore_poll()
            except Exception as e:
                logging.exception(f"Unhandled exception in on_ready during poll restoration: {e}")

    def create_poll(self, poll_type):
        if poll_type == "date":
            return DatePoll(self.config)
        elif poll_type == "movie":
            return MoviePoll(self.config)
        else:
            raise ValueError(f"Invalid poll_type: {poll_type}")

    @commands.group()
    @commands.bot_has_permissions(send_messages=True)
    async def movieclub(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid Movie Club command passed...")

    @movieclub.group()
    async def poll(self, ctx):
        if ctx.invoked_subcommand is None:
            # Check for required permissions
            permissions = ctx.channel.permissions_for(ctx.guild.me)
            if not permissions.send_messages:
                await ctx.author.send("I do not have permissions to send messages in the channel.")
            else:
                await ctx.send("Invalid poll command passed TEST!!!..")

    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @poll.group()
    async def date(self, ctx, action: str, month: str = None):
        """Date poll commands. Use subcommands or 'start'/'end' actions."""
        if ctx.invoked_subcommand is None:
            target_role = await self.config.guild(ctx.guild).target_role()

            if action.lower() == "start":
                try:
                    if "date_poll" in self.active_polls.keys():
                        await ctx.send("A date poll is already active.")
                        return
                    else:
                        poll = DatePoll(self.bot, self.config, ctx.guild)
                        await poll.write_poll_to_config()
                        await poll.start_poll(ctx, action, month)
                        self.active_polls["date_poll"] = poll  # add poll to active polls using new poll_id
                        await ctx.send("A date poll is activated.")

                except AttributeError:
                    await ctx.send(
                        "Error: Unable to initialize date poll. For some reason, the Poll object could not be created."
                    )
                    logging.exception("Failed to initialize date poll.")

            elif action.lower() == "end":
                if "date_poll" in self.active_polls.keys():  # check if poll is in active polls using new poll_id
                    await self.active_polls["date_poll"].end_poll(ctx)
                    del self.active_polls["date_poll"]
                else:
                    await ctx.send("No active date poll in this channel.")
            else:
                await ctx.send('Invalid action. Use "start" or "end".')

    @date.command(name="votes")
    async def date_poll_votes(self, ctx):
        """List the date poll voters for each date."""
        # Access the poll if active
        date_poll = self.active_polls.get("date_poll")
        if not date_poll:
            await ctx.send("No active date poll.")
            return
        date_user_votes = await date_poll.get_user_votes()
        if not date_user_votes:
            await ctx.send("No votes have been cast yet.")
            return
        
        lines = []
        for date_str, user_dict in date_user_votes.items():
            user_ids = ", ".join(f"<@{u}>" for u in user_dict.keys())
            lines.append(f"**{date_str}**: {user_ids}")
        
        if lines:
            await ctx.send("\n".join(lines))
        else:
            await ctx.send("No votes found.")

    # !movieclub poll movie start
    # !movieclub poll movie end
    @commands.guild_only()  # type:ignore
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @poll.command(name="movie")
    async def movie_poll(self, ctx, action: str):
        if action.lower() == "start":
            logging.debug(f"movie command received with action={action}")
            try:
                stored_movies = await self.config.guild(ctx.guild).movies()
                if stored_movies:
                    poll = MoviePoll(self.bot, self.config, ctx.guild)
                    await poll.write_poll_to_config()
                    await poll.start_poll(ctx, action, stored_movies)
                    self.active_polls["movie_poll"] = poll
                else:
                    await ctx.send(
                        "No movies found in the movie poll. Please add movies using the `movie add` command."
                    )

            except AttributeError:
                await ctx.send(
                    "Error: Unable to initialize movie poll. For some reason, the Poll object could not be created."
                )
                logging.exception("Failed to initialize movie poll.")

        elif action.lower() == "end":
            logging.debug(f"movie command received with action={action}")
            if "movie_poll" in self.active_polls.keys():  # check if poll is in active polls using new poll_id
                await self.active_polls["movie_poll"].end_poll(ctx)
                # TODO: REMOVE THIS WHEN CODE COMPLETE
                # Clear the movies in the Guild Config after starting the poll:
                await self.config.guild(ctx.guild).movies.clear()
                del self.active_polls["movie_poll"]  # remove poll from active polls using new poll_id
            else:
                await ctx.send("No active movie poll in this channel.")
        elif action.lower() == "votes":
            if "movie_poll" in self.active_polls.keys():
                await self.active_polls["movie_poll"].get_vote_progress(ctx)
            else:
                await ctx.send("No active movie poll in this channel.")
        else:
            await ctx.send('Invalid action. Use "start" or "end".')

    @movie_poll.command(name="votes")
    async def movie_poll_votes(self, ctx):
        """List the voters for each movie in the active movie poll."""
        mpoll = self.active_polls.get("movie_poll")
        if not mpoll:
            await ctx.send("No active movie poll.")
            return
        user_votes = await mpoll.get_user_votes()
        if not user_votes:
            await ctx.send("No votes have been cast yet.")
            return
        
        # Build reverse map: {movie: [voters...]}
        from collections import defaultdict
        movie_to_voters = defaultdict(list)
        for uid, movie_name in user_votes.items():
            movie_to_voters[movie_name].append(uid)
        
        results = []
        for mv, voters in movie_to_voters.items():
            mention_str = ", ".join(f"<@{u}>" for u in voters)
            results.append(f"**{mv}**: {mention_str}")
        
        if not results:
            await ctx.send("No votes found.")
        else:
            await ctx.send("\n".join(results))

    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movieclub.group()
    async def movie(self, ctx):
        if ctx.invoked_subcommand is None:
            # Check for required permissions
            permissions = ctx.channel.permissions_for(ctx.guild.me)
            if not permissions.send_messages:
                await ctx.author.send("I do not have permissions to send messages in the channel.")
            else:
                await ctx.send("Invalid movie command passed TEST!!!..")

    # !movieclub movie add <movie_name>
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movie.command(name="add")
    async def add_movie(self, ctx, *movie_name: str):
        movie_name = " ".join(movie_name)
        logging.debug(f"movie command received with movie_name={movie_name}")
        if movie_name:
            logging.debug(f"Adding movie {movie_name} to the poll")
            stored_movies = defaultdict(dict, await self.config.guild(ctx.guild).movies())
            movie_data, discord_format = get_movie_discord_embed(movie_name)
            movie_title = movie_data.get("title", movie_name)
            if movie_title not in stored_movies:
                stored_movies[movie_title] = movie_data
                await self.config.guild(ctx.guild).movies.set(stored_movies)
                await ctx.send(embed=discord_format)
                await ctx.send(f"'{movie_title}' has been added to the movie poll.")
            else:
                await ctx.send(f"There was an error adding '{movie_name}' to the movie poll.")
        else:
            await ctx.send("Please provide a movie name.")

    # !movieclub movie thread <movie_name>
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movie.command(name="thread")
    async def add_thread(self, ctx, *movie_name: str):
        movie_name = " ".join(movie_name)
        logging.debug(f"movie thread command received with movie_name={movie_name}")
        if movie_name:
            logging.debug(f"Creating thread for movie {movie_name}")
            movie_data, discord_format = get_movie_discord_embed(movie_name)
            logging.debug(f"movie_data: {movie_data}")
            movie_name = movie_data.get("title", movie_name)
            logging.debug(f"movie_name: {movie_name}")
            # TODO: make configurable
            channel_id = 1064523211905183784

            # Extract and format the details
            tagline = f"`{movie_data.get('tagline').upper() if movie_data.get('tagline') else 'No tagline available'}`"
            description = movie_data.get("description", "")
            details = f"{', '.join(movie_data['genre'][:2])} · {movie_data['runtime']} mins"
            rating = f"★ {movie_data['rating']} · {movie_data['number_of_reviewers']} fans"
            more_links = f"[Trailer]({movie_data['trailer_url']})"

            # Compile the details into a message
            message = f"{tagline}\n\n{description}\n\n**Details:** {details}\n**Rating:** {rating}\n**More:** {more_links}\n\n\u200B"
            thread_name = f"{movie_name} (Movie Club)"
            thread_content = message
            await create_discord_thread(
                ctx,
                channel_id=channel_id,
                thread_name=thread_name,
                thread_content=thread_content,
            )
            await ctx.send(f"'{movie_name}' thread has been created.")
            return message

        else:
            await ctx.send("Please provide a movie name.")

    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    @commands.mod_or_permissions(manage_messages=True)
    @movieclub.command(name="setrole")
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

    @movie.command(name="list")
    async def list_movies(self, ctx):
        """List the movies currently in the poll."""
        stored_movies = await self.config.guild(ctx.guild).movies()
        if not stored_movies:
            await ctx.send("No movies are currently added.")
        else:
            movie_titles = list(stored_movies.keys())
            movie_list_str = "\n".join(f"- {title}" for title in movie_titles)
            await ctx.send(f"Current movies in the poll:\n{movie_list_str}")

    @movie.command(name="remove")
    async def remove_movie(self, ctx, *, movie_name: str):
        """Removes a movie from the poll options."""
        stored_movies = await self.config.guild(ctx.guild).movies()
        if not stored_movies:
            await ctx.send("No movies are currently in the poll.")
            return
        # Attempt a case-insensitive match
        matched_key = None
        for key in stored_movies.keys():
            if key.lower() == movie_name.lower():
                matched_key = key
                break

        if matched_key:
            del stored_movies[matched_key]
            await self.config.guild(ctx.guild).movies.set(stored_movies)
            await ctx.send(f"Removed '{matched_key}' from the poll.")
        else:
            await ctx.send(f"'{movie_name}' was not found in the poll.")
