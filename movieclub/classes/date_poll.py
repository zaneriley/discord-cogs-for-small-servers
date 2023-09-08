import datetime
from collections import defaultdict
import discord
from discord import ui
from discord import ui, ButtonStyle
import logging

from ..utilities import DateUtil

class DatePollView(ui.View):
    def __init__(self, dates, config):
        super().__init__()
        for date in dates:
            self.add_item(DatePollButton(date, config))

class DatePollButton(ui.Button):
    def __init__(self, date: datetime, config):
        super().__init__(style=ButtonStyle.primary, label=DateUtil.get_presentable_date(date))
        self.date = DateUtil.normalize_date(date)
        self.config = config
        
    async def callback(self, interaction: discord.Interaction):
        # let Discord know we received the interaction so it doesn't time us out
        # in case it takes a while to respond for some reason
        await interaction.response.defer()
        date_str = DateUtil.get_presentable_date(self.date)  # Convert datetime to string for display
        user_id = str(interaction.user.id)  

        logging.debug(f"Fetching current votes and user votes")
        votes = defaultdict(int, await self.config.date_votes())
        date_user_votes = defaultdict(dict, await self.config.date_user_votes())
        logging.debug(f"Fetched votes: {votes} and user votes: {date_user_votes}")
        date_key = self.date.strftime("%Y-%m-%d")  # Convert datetime to string for a dictionary key
        date_votes = defaultdict(bool, date_user_votes[date_key])

        logging.debug(f"user_id initial type: {type(user_id)}")  
        logging.debug(f"BEFORE update: votes={votes}, dateVotes={date_votes}")

        if user_id in date_votes:
            logging.debug(f"User {user_id} already voted for {date_str}. Toggle vote off.")
            votes[date_key] -= 1
            if votes[date_key] == 0:  
                votes.pop(date_key)  
            del date_votes[user_id]
        else:
            logging.debug(f"User {user_id} not found in votes for {date_str}. Toggle vote on.")
            votes[date_key] += 1
            date_votes[user_id] = True
        date_user_votes[date_key] = dict(date_votes)  

        # Update config
        logging.debug(f"Updating votes and user votes")
        await self.config.date_user_votes.set(dict(date_user_votes))  
        await self.config.date_votes.set(dict(votes))
        logging.debug(f"Updated votes: {votes} and user votes: {date_user_votes}")
        logging.debug(f"AFTER update: votes={votes}, dateVotes={date_votes}")

        logging.debug(f"Votes: {votes}")
        logging.debug(f"Users that voted for above date: {date_votes}")
        self.label = f"{date_str} ({votes[date_key]})"  # Show the votes for the updated date

        unique_voters = set()  
        for user_vote_list in date_user_votes.values():
            unique_voters.update(user_vote_list.keys())
        logging.debug(f"Unique voters: {unique_voters}")

        target_role_id = await self.config.target_role()  
        if target_role_id:
            target_role = discord.utils.get(interaction.guild.roles, id=target_role_id)
            target_role_member_ids = set(str(member.id) for member in target_role.members) if target_role else {interaction.guild.members}
        else:
            target_role_member_ids = set(member.id for member in interaction.guild.members)
        logging.debug(f"Target role member IDs: {target_role_member_ids}")

        unique_role_voters = unique_voters.intersection(target_role_member_ids)  # Calculate the voters in the target role
        logging.debug(f"Unique role voters: {unique_role_voters}")

        percentage_voted = (len(unique_role_voters) / len(target_role_member_ids)) * 100  
        original_message = await interaction.message.channel.fetch_message(interaction.message.id)
        original_embed = original_message.embeds[0]
        
        if len(unique_role_voters) == 0:
            footer_text = ""
        else:
            voter_count = len(unique_role_voters)
            more_to_go = len(target_role_member_ids) - len(unique_role_voters)
            passholder_text = "passholder" if voter_count == 1 else "passholders"
            footer_text = f"{voter_count} movie club {passholder_text} voted, {more_to_go} more to go! ({percentage_voted:.2f}% participation)"

        # Setting the footer in the original_embed
        original_embed.set_footer(text=footer_text, icon_url="https://cdn3.emoji.gg/emojis/1075-pinkhearts.gif")

        # Now editing the embed with the original_embed
        await interaction.message.edit(embed=original_embed)

        # Send an ephemeral message to the user
        voted_dates = [date for date in votes.keys() if user_id in date_user_votes.get(date, {})]

        def get_sorted_presentable_dates(dates):
            datetime_dates = [datetime.datetime.strptime(date, '%Y-%m-%d') for date in dates] # Convert stringified dates back to datetime
            sorted_dates = DateUtil.sort_dates(datetime_dates) # Adjust this function to accept datetime formats
            return '\n- '.join(DateUtil.get_presentable_date(date) for date in sorted_dates)

        # The part of the code where you check and format the dates
        if voted_dates:
            joined_dates = get_sorted_presentable_dates(voted_dates)
        else:
            joined_dates = 'None (SAD!)'

        if user_id in date_votes:
            vote_icon = "<:check:1103626473266479154>"
            action_message = f"Voted for `{date_str}`"
        else:
            vote_icon = "<:X_:1103627142425747567>"
            action_message = f"Vote removed for `{date_str}`"

        vote_message = f"\u200B\n{vote_icon} {action_message}. \n\nAvailability:\n- {joined_dates}"

        # Update the message with the new embed
        await interaction.followup.send(vote_message, ephemeral=True)
