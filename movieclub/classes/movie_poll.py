import logging
from typing import Iterable
from collections import defaultdict
import random
import re

import discord
from discord import ui
from discord import ui, Embed, Button, ButtonStyle
from discord.ui import Button, View
from discord.errors import HTTPException
from holidays.countries.united_states import UnitedStates

# Application-specific imports
from .poll import Poll
from ..constants import MOVIE_CLUB_LOGO, DISCORD_EMBED_COLOR
from ..utilities.api_handlers.movie_data_fetcher import movie_data_to_discord_format

MAX_BUTTON_LABEL_SIZE = 16
MAX_BUTTONS_IN_ROW = 5

first_vote_endings = [
    "You know what's going on in the world. You know what culture looks like, you know the names of trends, and you certainly know what movie to vote for.",
    "The world doesn't want people to vote this way. But you did.",
    "Hell yeah! This is a real movie, the movie they played on the moon, the movie they played for the first aliens to make contact with us, the movie they'll play when the world ends.",
    "A profound choice. It speaks volumes about your taste, your ethos... or it was random ",
    "The movie (that you chose) said it feels appreciated. If movies could feel, that's how it would feel.",
    "It worked, the shadows no longer follow you",
    "This movie is a rare movie, one of those that see their interest increase over time, and will long be remembered for having a great influence on the state of motion pictures.",
    "It's about time you picked one.",
    "You aren't sure what decisions led you here, but it feels right.",
    "You have seen the face of Cinema, and she smiled at you.",
    "You are prone to picking... eccentric movies.",
    "Finally, an actual vote! We're thrilled to finally get to count this.",
    "This is the right action. This is the right choice.",
    "It was the only possible thing in that moment. The movie understood you.",
    "There is no shame in simplicity. Maybe you just want to watch a movie without too many thoughts and feelings. Your simple movie choice is appreciated.",
    "You say the name of the movie again, to yourself. _{self.label}_... It feels good to say it, to hear it. You stroke your cheek. This is smooth.",
    "People didn't rate this movie highly but you'll be damned if that stopped you from voting for it. That's the spirit."
]

next_vote_endings = [
    "Oh right, this movie is faster, you think. Maybe it has more power. Maybe it has more potential. Maybe the movie is keeping score. Of course it is. Every movie is keeping score.",
    "You feel a little more confident in your choice this time. You feel a little more confident in yourself.",
    "This one is more real. This is your real vote.",
    "You couldn't live with your mistake, and are now living with another one. Live with it.",
    "This movie makes you want to paint. Not that you are an artist. You've never done art, you can't do art. But you want to. Paint is cheap. It's very cheap. Just get the cheap one. That's all.",
    "Wow! You're really giving it to them! You're good at this! You've considered a great multiplicity of factors before coming to your choice. They all seemed to point in the same direction. You voted correctly.",
    ""
]

too_many_votes_endings = [
    "You can't vote for more than one movie. You know that. You know that.",
    "The number of times you've changed your vote is not up to you or anyone else, and nobody at Movie Club has the authority to bring up the matter with you.",
]

class MovieInteraction(View):
    "Buttons for Approve, Edit and Reject actions"
    def __init__(self):
        super().__init__(timeout=60)  
        approve_button = Button(label='Approve', custom_id='approve')
        approve_button.style = ButtonStyle.green
        self.add_item(approve_button)

        edit_button = Button(label='Edit', custom_id='edit')
        edit_button.style = ButtonStyle.secondary
        self.add_item(edit_button)

        reject_button = Button(label='Reject', custom_id='reject')
        reject_button.style = ButtonStyle.red
        self.add_item(reject_button)

    @ui.button(custom_id='approve')
    async def approve_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Movie approved.')

    @ui.button(custom_id='edit')
    async def edit_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Movie data edit feature not implemented yet.')

    @ui.button(custom_id='reject')
    async def reject_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Movie rejected.')

class MoviePoll(Poll): 
    def __init__(self, bot, config, guild):  
        super().__init__(bot, config, guild, "movie_poll")
        self.vote_change_counter = defaultdict(int)
        self.original_message_content = None  # Add this line 

    async def get_stored_movies(self):
        return await self.config.guild(self.guild).movies()

    async def start_poll(self, ctx, action, movies):
        if action == "start":
            
            target_role = await self.get_target_role()
            if target_role:
                mention_str = f"<@&{target_role}>" if target_role else ""
            else:
                mention_str = ""

            view = await self.build_view(movies.keys())

            msg_content = f"\u200B\n{MOVIE_CLUB_LOGO}\n\nWhich movie will we watch next? {mention_str}\n\u200B"
            embeds_list = []
            for movie_data in movies.values():
                embeds_list.append(movie_data_to_discord_format(movie_data))
            msg = await ctx.send(content=msg_content, embeds=embeds_list, view=view)
            logging.debug(f"Generated message id: {msg.id}")
            await self.set_message_id(msg.id)
            await self.set_poll_channel_id(msg.channel.id)
        else:
            await ctx.send('Invalid action. Use "start" or "end".')

    async def end_poll(self, ctx):
        try:
            target_role = await self.get_target_role()
            logging.debug("Clearing votes and user votes, setting Movie Poll as inactive.")
            votes = await self.get_votes()
            stored_movies = defaultdict(dict, await self.get_stored_movies())
            winner_movie = max(votes, key=votes.get) if any(votes.values()) else None
            winner_movie_data = stored_movies.get(winner_movie)
            logging.debug(f"Winner movie data: {winner_movie_data}")

            if winner_movie:
                trailer_url = winner_movie_data.get('trailer_url')
                # TODO: check to see if target_role is None
                trailer_message = f"\n[Watch the trailer]({trailer_url})\n\n\u200B See you <@&{target_role}> holders there! <:fingercrossed:1103626715663712286>\n\u200B" if trailer_url else ""
                await ctx.send(f"\u200B\n{MOVIE_CLUB_LOGO}\n\nThe most voted movie is:\n\n**{winner_movie}**! {trailer_message}")
            else:
                await ctx.send("No votes were cast in the movie poll.")

            await self.remove_poll_from_config()
            logging.debug("Movie Poll ended and set as inactive successfully.")
        except Exception as e:
            logging.error(f"Unable to end movie poll due to: {str(e)}")

    async def keep_poll_alive(self):
        logging.debug("Keeping Movie Poll alive...")
        poll_message = await self._fetch_poll_message()
        if poll_message:
            try:
                
                logging.debug("Editing message...")
                stored_movies = defaultdict(dict, await self.get_stored_movies())
                view = await self.build_view(stored_movies.keys())
                await poll_message.edit(view=view)
                logging.debug("Message edited.")
            except HTTPException as e:
                logging.debug(f"Unable to edit the message due to {e}. Setting the poll to inactive.")
                await self.remove_poll_from_config(self)

    async def restore_poll(self):
        poll_message = await self._fetch_poll_message()
        if poll_message is None:
            logging.debug("Poll message not found.")
            return
        
        stored_movies = defaultdict(dict, await self.get_stored_movies())
        
        view = await self.build_view(stored_movies.keys())
        await poll_message.edit(view=view)
    
    async def build_view(self, movie_names: Iterable[str]) -> discord.ui.View:
        view = discord.ui.View()
        total_length = 0
        logging.debug(f"movie_names: {movie_names}")
        for movie_name in movie_names:
            total_length += len(movie_name)
            movie_button = self.MovieButton(label=movie_name, movie_poll=self)
            view.add_item(movie_button)  # Add buttons to the view

        # if total_length >= 66:
        #     reduction_value = total_length - 66
        #     longest_label_length = max(len(movie_name) for movie_name in movie_names)
        #     for movie_button in view.children:
        #         if len(movie_button.label) > reduction_value:
        #             movie_button.label = movie_button.label[:-(reduction_value + 3)] + "..."
        #         reduction_value -= longest_label_length - len(movie_button.label)
        #         if reduction_value <= 0:
        #             break

        return view
    
    async def add_vote(self, user_id: str, movie_name: str):
        """Adds a vote for a movie."""
        try:
            logging.debug(f"Fetching current votes and user votes")
            user_votes = defaultdict(dict, await self.get_user_votes())
            votes = defaultdict(int, await self.get_votes())
            logging.debug(f"Fetched votes: {votes} and user votes: {user_votes}")
            if user_id in user_votes:
                old_movie = user_votes[user_id]
                if old_movie == movie_name:
                    logging.info(f"User {user_id} is attempting to vote for the same movie")
                    return
                votes[old_movie] -= 1
                user_votes[user_id] = movie_name
                votes[movie_name] += 1
                logging.info(f"Vote updated: User {user_id} changed the vote from {old_movie} to {movie_name}. Total votes: {votes}")
            else:
                user_votes[user_id] = movie_name
                votes[movie_name] += 1
                logging.info(f"Vote added: User {user_id} voted for {movie_name}. Total votes: {votes}")
            
            await self.set_user_votes(dict(user_votes))
            await self.set_votes(dict(votes))
        
        except Exception as e:
            logging.error(f"Error occurred while adding vote: {e}")

    async def remove_vote(self, user_id: str):
        """Removes a vote for a movie."""
        try:
            user_votes = defaultdict(dict, await self.get_user_votes())
            if movie_name := user_votes.get(user_id):
                votes = defaultdict(int, await self.get_votes())
                votes[movie_name] -= 1
                del user_votes[user_id]
                await self.set_votes(dict(votes))
                await self.set_user_votes(dict(user_votes))
                logging.info(f"Vote removed: User {user_id}'s vote for {movie_name} removed. Total votes: {votes}")
        except Exception as e:
            logging.error(f"Error occurred while removing vote: {e}")

    def send_initial_message(self):
        pass

    def send_update_message(self):
        pass

    def send_result_message(self):
        pass
    
    def get_poll_message_details(self):
        # Implement the method here
        pass

    def set_active_status(self, is_active):
        # Implement the method here
        pass

    class MovieButton(discord.ui.Button):
        def __init__(self, label: str, movie_poll: "MoviePoll"):
            super().__init__(style=discord.ButtonStyle.primary, label=label)
            self.movie_poll = movie_poll

        
        async def update_percentage_voted_text(self, interaction: discord.Interaction):
            # Your logic for updating the message goes here
            unique_voters = set()  
            user_votes = defaultdict(dict, await self.movie_poll.get_user_votes())
            logging.info(f"update percentage User votes: {user_votes.keys()}")
            for user in user_votes.keys():
                unique_voters.add(user)
            logging.debug(f"update percentage unique voters: {unique_voters}")

            target_role = await self.movie_poll.get_target_role()
            if target_role:
                target_role = discord.utils.get(interaction.guild.roles, id=target_role)
                target_role_member_ids = set(str(member.id) for member in target_role.members) if target_role else {interaction.guild.members}
            else:
                target_role_member_ids = set(member.id for member in interaction.guild.members)
            logging.info(f"update percentage target role member ids: {target_role_member_ids}")

            unique_role_voters = unique_voters.intersection(target_role_member_ids)
            
            percentage_voted = (len(unique_role_voters) / len(target_role_member_ids)) * 100

                      # Check if original_message_content is None, if so, store the current message content
            if self.movie_poll.original_message_content is None:
                self.movie_poll.original_message_content = interaction.message.content

            # TODO: store this in guild config and don't use regex
            original_message = interaction.message

            voter_count = len(unique_role_voters)
            more_to_go = len(target_role_member_ids) - len(unique_role_voters)
            passholder_text = "passholder" if voter_count == 1 else "passholders"
            if len(unique_role_voters) == 0:
                percentage_voted_text = ""
            else:
                percentage_voted_text = f"<:fingercrossed:1103626715663712286> {voter_count} movie club {passholder_text} voted, {more_to_go} more to go! ({percentage_voted:.2f}% participation)"
            logging.debug(f"Percentage voted text: {percentage_voted_text}")
            def update_string(message: str, voter_count: int, more_to_go: int, percentage_voted: float) -> str:
                pattern = r"(<:fingercrossed:1103626715663712286> \d+ movie club passholder(s)? voted, \d+ more to go! \(\d+(\.\d+)?% participation\)\n\u200B)"
                match = re.search(pattern, message)
                passholder_text = "passholder" if voter_count == 1 else "passholders"
                new_string = f"<:fingercrossed:1103626715663712286> {voter_count} movie club {passholder_text} voted, {more_to_go} more to go! ({percentage_voted:.2f}% participation)\n\u200B"
                if match:
                    old_string = match.group(1)
                    if voter_count == 0:
                        message = message.replace(old_string, "")
                    else:
                        message = message.replace(old_string, new_string)
                elif voter_count > 0:
                    message += "\n" + new_string
                return message
            updated_message = update_string(original_message.content, voter_count, more_to_go, percentage_voted)
            logging.debug(f"Updating message with percentage voted text: {percentage_voted_text}")
            await original_message.edit(content=updated_message)

        async def callback(self, interaction: discord.Interaction):
            """Updates the vote for a movie when a button is clicked."""
            user_id = str(interaction.user.id)  
            user_votes = defaultdict(dict, await self.movie_poll.get_user_votes())
            old_movie = user_votes.get(user_id)
            logging.info(f"User {user_id} old movie is {old_movie}")
            if not old_movie:
                await self.movie_poll.add_vote(user_id, self.label)
                message = f"You voted for `{self.label}`." + f"\n\n_{random.choice(first_vote_endings)}_"
            elif old_movie == self.label:
                await self.movie_poll.remove_vote(user_id)
                message = f"Your vote has been removed from `{old_movie}`. \n\nDon't forget to vote for another movie!"
            else:
                if self.movie_poll.vote_change_counter[user_id] >= 3:  # Check if user has changed vote more than 3 times
                    message = f"You voted for `{self.label}`.\n\nYour previous vote for `{old_movie}` has been removed." + f"\n\n_{random.choice(too_many_votes_endings)}_"
                else:
                    await self.movie_poll.remove_vote(user_id)
                    await self.movie_poll.add_vote(user_id, self.label)
                    self.movie_poll.vote_change_counter[user_id] += 1  # Increment the counter
                    message = f"You voted for `{self.label}`.\n\nYour previous vote for `{old_movie}` has been removed." + f"\n\n_{random.choice(next_vote_endings)}_"
            await self.update_percentage_voted_text(interaction)
            await interaction.response.send_message(message, ephemeral=True)

