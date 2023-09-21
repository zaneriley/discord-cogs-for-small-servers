import logging

import discord
from discord import ui
from discord import ui, Embed, Button,ButtonStyle
from discord.ui import Button, View
from holidays.countries.united_states import UnitedStates

# Application-specific imports
from .poll import Poll
from ..constants import MOVIE_CLUB_LOGO
from ..utilities.api_handlers.movie_data_fetcher import get_movie_discord_embed

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

    async def add_movie(self, ctx, movie_name: str):
        if not movie_name:
            ctx.send("Movie name cannot be empty.")
            return
        movie_data = get_movie_discord_embed(movie_name)
        if not movie_data:
            ctx.send("Could not fetch movie data. Please check the name again.")
            return
        
        logging.info(f"Movie data: {movie_data}")
        embed = movie_data
        
        view = MovieInteraction()
        await ctx.send(embed=embed)

    async def start_poll(self, ctx, action, month):
        if action == "start":
            pass
        else:
            await ctx.send('Invalid action. Use "start" or "end".')

    async def end_poll(self, ctx):
        try:
            pass
        except Exception as e:
            logging.error(f"Unable to end movie poll due to: {str(e)}")  

    async def keep_poll_alive(self):
        logging.debug("Keeping Date Poll alive...")
        poll_message = await self._fetch_poll_message()
        if poll_message:
            try:
                logging.debug("Editing message...")
                view = await self.build_view()
                await poll_message.edit(view=view)
                logging.debug("Message edited.")
            except HTTPException as e:
                logging.debug(f"Unable to edit the message due to {e}. Setting the poll to inactive.")
                await self.remove_poll_from_config(self)

    async def restore_poll(self):
        poll_message = await self._fetch_poll_message()
        if poll_message is None:
            return
        # date_votes_dict = await self.config.date_votes()
        # date_votes = {datetime.datetime.strptime(date_string, "%a, %b %d"): vote for date_string, vote in date_votes_dict.items()}
        date_strings = await self.get_buttons()
        dates = [datetime.datetime.strptime(date_string, "%a, %b %d, %Y") for date_string in date_strings]
        view = DatePollView(dates, self.config, self.guild, self.poll_id)
        await poll_message.edit(view=view)
    
    async def build_view(self):
        date_strings = await self.get_buttons()
        dates = [datetime.datetime.strptime(date_string, "%a, %b %d, %Y") for date_string in date_strings]
        return DatePollView(dates, self.config, self.guild, self.poll_id)

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