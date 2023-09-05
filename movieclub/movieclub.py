# Standard library imports
import calendar
import datetime
from datetime import date, timedelta
import logging
from typing import Literal, List
from collections import defaultdict

# Third-party library imports
from dateutil.relativedelta import relativedelta, SU  # Import SU (Sunday)
import discord
from discord import ui, Embed, Button, ButtonStyle, ActionRow
from discord.ext import tasks
from discord.errors import NotFound, Forbidden, HTTPException
import holidays
from holidays.countries.united_states import UnitedStates

# Application-specific imports
from redbot.core import commands, Config
from redbot.core.bot import Red

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

MOVIE_CLUB_LOGO = '<:movieclub:1066636399530479696>\u2007<:logomovieclub1:1089715872551141416><:logomovieclub2:1089715916385820772><:logomovieclub3:1089715950225469450> <:logomovieclub4:1089715994743812157><:logomovieclub5:1089716031095832636><:logomovieclub6:1089716070497124502>'

class DateUtil:

    @staticmethod
    def normalize_date(date: datetime.datetime) -> datetime.datetime:
        """Returns a date with the time set to 00:00:00 for consistent comparison"""
        return datetime.datetime.combine(date.date(), datetime.datetime.min.time())

    @staticmethod
    def get_presentable_date(date: datetime.datetime) -> str:
        """Returns a date string in the format 'Mon, Sept 18'"""
        return date.strftime('%a, %b %d')

    @staticmethod
    def add_days(date: datetime, days: int) -> datetime:
        """Returns the date after adding the specified number of days"""
        return date + datetime.timedelta(days=days)

    @staticmethod
    def subtract_days(date: datetime, days: int) -> datetime:
        """Returns the date after subtracting the specified number of days"""
        return date - datetime.timedelta(days=days)
    
    @staticmethod
    def sort_dates(dates: List[datetime.datetime]) -> List[datetime.datetime]:
        """Sorts and returns a list of datetime objects"""
        return sorted(dates)
    
    @staticmethod
    def now() -> datetime:
        """Returns current date with normalized time"""
        return DateUtil.normalize_date(datetime.datetime.now())
        
    @staticmethod
    def get_year_month(month: str, year: int = None) -> datetime:
        """Returns a datetime object in the format '%B' or '%b'"""
        year = year if year else DateUtil.now().year
        try:
            return datetime.datetime.strptime(month, "%B").replace(year=year)
        except ValueError:
            return datetime.datetime.strptime(month, "%b").replace(year=year)

    @staticmethod
    def is_within_days(date1: datetime, date2: datetime, days: int) -> bool:
        """Returns true if the difference between date1 and date2 is within the given number of days"""
        return (date1.date() - date2.date()).days <= days

    @staticmethod
    def to_next_month(date: datetime) -> datetime:
        """Returns the same date in the next month"""
        return date + relativedelta(months=1)
    
def first_weekday_after_days(weekday, date, days=14, holiday_list=None):
    """
    Returns the first weekday after a given number of days from the input date,
    skipping any holidays.
    """
    logging.debug(f"Input date in first_weekday_after_days: {date}")
    
    # Calculate the date 14 days from the input date
    future_date = date + timedelta(days=days)
    
    # Start iterating from the future_date to find the next available weekday
    while True:
        # Calculate the weekday of the future_date
        diff = weekday - future_date.weekday()
        offset = diff if diff >= 0 else diff + 7
        first_date = future_date + timedelta(days=offset)
        
        logging.debug(f"Calculated first_date in first_weekday_after_days: {first_date}")
        
        # Check if first_date is still within the same month as the input date
        if first_date.month != date.month:
            logging.debug(f"first_date {first_date} is not in the same month as input date {date}. Returning None.")
            return None
        
        # Check for holidays
        if holiday_list and (first_date in holiday_list or 
                             first_date - timedelta(days=1) in holiday_list or 
                             first_date + timedelta(days=1) in holiday_list):
            logging.debug(f"first_date {first_date} is a holiday or near a holiday. Skipping.")
            # Move to the next day and continue the loop
            future_date = first_date + timedelta(days=1)
            continue
        
        return first_date

def last_weekday_of_month(year, month, weekday):
    """Find the last occurrence of a weekday in a given month."""
    _, last_day = calendar.monthrange(year, month)
    last_date = datetime.date(year, month, last_day)
    offset = (last_date.weekday() - weekday) % 7
    last_date = last_date - datetime.timedelta(days=offset)
    return last_date

def last_weekday(weekday, date):
    """
    Returns the last weekday of the month.
    """
    logging.debug(f"Input date in last_weekday: {date}")
    next_month = date + relativedelta(months=1)
    last_day_of_month = next_month - datetime.timedelta(days=1)
    diff = last_day_of_month.weekday() - weekday
    offset = diff if diff >= 0 else diff + 7
    last_date = last_day_of_month - datetime.timedelta(days=offset)
    
    logging.debug(f"Calculated last_date in last_weekday: {last_date}")

    if (last_date - date).days <= 14:
        logging.debug(f"last_date {last_date} is within 14 days from input date {date}. Returning None.")
        return None      

    return last_date


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

class DatePollView(ui.View):
    def __init__(self, dates, config):
        super().__init__()
        for date in dates:
            self.add_item(DatePollButton(date, config))

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

class CustomHolidays(UnitedStates):
    def _populate(self, year):
        # Populate the holiday list with the default US holidays
        super()._populate(year)

        # Add Halloween
        self[date(year, 10, 31)] = "Halloween"
        
        # Add Christmas Eve
        self[date(year, 12, 24)] = "Christmas Eve"
        
        # Add New Year's Eve
        self[date(year, 12, 31)] = "New Year's Eve"
        
        # Add Valentine's Day
        self[date(year, 2, 14)] = "Valentine's Day"

        # Add Mother's Day (Second Sunday in May)
        may_first = date(year, 5, 1)
        mothers_day = may_first + relativedelta(weekday=SU(2))  # Advance to the second Sunday
        self[mothers_day] = "Mother's Day"

        # Add Father's Day (Third Sunday in June)
        june_first = date(year, 6, 1)
        fathers_day = june_first + relativedelta(weekday=SU(3))  # Advance to the third Sunday
        self[fathers_day] = "Father's Day"

        # TODO: add parameter that marks the day before and after a holiday as unavailable or not
        # Add insanely good day
        self[date(year, 9, 21)] = "September 21st"

        # Add Thanksgiving Eve (Day before Thanksgiving)
        thanksgiving = [k for k, v in self.items() if "Thanksgiving" in v][0]  # Find the date of Thanksgiving
        thanksgiving_eve = thanksgiving - relativedelta(days=1)  # Calculate Thanksgiving Eve
        self[thanksgiving_eve] = "Thanksgiving Eve"

class MovieClub(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=289198795625857026, force_registration=True)
        self.config.register_global(date_votes={}, is_date_poll_active=False, date_user_votes={}, date_buttons=[], target_role=None, poll_message_id=None, poll_channel_id=None)
        # Add a bot wait until ready guard if the bot hasn't fully connected

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Restores the poll if the bot restarts while the poll is active."""
        try:
            logging.debug("Starting on_ready listener...")
            self.refresh_poll_buttons.start()
            await self.restore_polls()
            logging.debug("Ending on_ready listener...")
        except Exception as e:
            logging.error(f"Unhandled exception in on_ready: {e}")

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
        if action == "start":
            is_date_poll_active = await self.config.is_date_poll_active()
            if is_date_poll_active:
                await ctx.send('A date poll is already active.')
                return


            if month:
                month = DateUtil.get_year_month(month)
            else:
                month = DateUtil.now()
                last_monday = last_weekday(calendar.MONDAY, month)
                if DateUtil.is_within_days(last_monday, DateUtil.now(), 14):
                    month = DateUtil.to_next_month(month)

            us_holidays = CustomHolidays(years=month.year)

            # Calculate the last Monday, Wednesday, Thursday, and Friday of the month
            # These dates are abritrary for our server, but can be changed to suit your needs
            # TODO: fix this bad redundancy
            last_monday = first_weekday_after_days(0, month, days=14, holiday_list=us_holidays)
            last_wednesday = first_weekday_after_days(2, month, days=14, holiday_list=us_holidays)
            last_thursday = first_weekday_after_days(3, month, days=14, holiday_list=us_holidays)
            last_friday = first_weekday_after_days(4, month, days=14, holiday_list=us_holidays)
            last_saturday = first_weekday_after_days(5, month, days=14, holiday_list=us_holidays)

            # Filter out dates that are public holidays.
            # Also avoid the days immediately before and after holidays.
            # This is to maximize the likelihood that people are available.
            
            dates = [date for date in [last_monday, last_wednesday, last_thursday, last_friday, last_saturday] if date is not None]
            # dates = [date for date in dates if date not in us_holidays and date - datetime.timedelta(days=1) not in us_holidays and date + datetime.timedelta(days=1) not in us_holidays]

            # Sort the dates so the buttons are in chronological order
            dates.sort()

            target_role_id = await self.config.target_role()  
            if target_role_id:
                target_role = target_role_id
                mention_str = f"<@&{target_role_id}>" if target_role else ""
            else:
                mention_str = ""

            embed = Embed(title=f"{MOVIE_CLUB_LOGO}\n\n")
            embed.add_field(name="Showtimes", value="6pm Pacific ∙ 7pm High Peak ∙ 8pm Heartland ∙ 9pm Eastern ∙ 10am 東京", inline=False)

            # Create a view with buttons for each date
            view = DatePollView(dates, self.config)

            # Send a regular message with the optional role mention followed by the voting prompt and the embed with the view
            msg = await ctx.send(content=f"\u200B\nVote for the date of the next movie night! {mention_str}\n\u200B", embed=embed, view=view)

            # Save the poll message id and channel id into the bot config
            await self.config.poll_message_id.set(msg.id)
            await self.config.poll_channel_id.set(msg.channel.id)

            # Set the poll as active
            await self.config.is_date_poll_active.set(True)
            
            # new lines for storing the date buttons
            date_strings = [date.strftime("%a, %b %d, %Y") for date in dates]
            await self.config.date_buttons.set(date_strings)


        elif action == "end":
            # Initialize the variable before the if-else block
            most_voted_dates = []

            # Get the votes
            votes = await self.config.date_votes()

            if len(votes) == 0:  # Check if no votes exist
                await ctx.send("The poll was manually closed. No one voted in this poll.")
            else:
                # Identify Max Votes
                max_votes = max(votes.values())
                
                # Find Ties
                most_voted_dates = [date for date, vote_count in votes.items() if vote_count == max_votes]
                
                # Generate Message
                if len(most_voted_dates) > 1:
                    tie_message = f"\u200B\n{MOVIE_CLUB_LOGO}\n\nThere is a tie! <:swirl:1103626545685336116> The most voted dates are:\n\n"
                else:
                    tie_message = f"\u200B\n{MOVIE_CLUB_LOGO}\n\n The most voted date is:\n\n"

                # Collect user availability information for each date
                date_user_votes = await self.config.date_user_votes()

                for most_voted_date in most_voted_dates:
                    # use the correct date object to retrieve the votes
                    date_to_check = datetime.datetime.strptime(most_voted_date, "%Y-%m-%d")
                    presentable_date = DateUtil.get_presentable_date(date_to_check)
                    
                    # need to convert the date back to string format to use as key for the dictionary
                    str_date_to_check = date_to_check.strftime("%Y-%m-%d")
                    user_votes = date_user_votes.get(str_date_to_check, {})
                    user_ids = ', '.join(f'<@{user_id}>' for user_id in user_votes.keys())
                    tie_message += f'**{presentable_date}**\nAvailable: {user_ids}\n\n'

                await ctx.send(tie_message)
                
            # Reset the votes
            await self.config.date_votes.set({})
            await self.config.date_user_votes.set({})
            await self.config.is_date_poll_active.set(False)
            
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
    async def refresh_poll_buttons(self):
        """Background task to refresh poll buttons."""
        logging.debug("Starting refresh buttons task...")
        is_date_poll_active = await self.config.is_date_poll_active()
        
        if is_date_poll_active:
            logging.debug("Refreshing buttons...")
            channel_id = await self.config.poll_channel_id()
            message_id = await self.config.poll_message_id()
            channel = self.bot.get_channel(channel_id)
            
            try:
                logging.debug("Fetch message...")
                message = await channel.fetch_message(message_id)
                logging.debug("Message fetched.")
                date_strings = await self.config.date_buttons()
                dates = [datetime.datetime.strptime(date_string, "%a, %b %d, %Y") for date_string in date_strings]
                view = DatePollView(dates, self.config)
                logging.debug("Editing message...")
                message = await channel.fetch_message(message_id)
                await message.edit(view=view)
                logging.debug("Message edited.")
            except discord.HTTPException:
                logging.debug("Unable to edit the message.")
                await self.config.is_date_poll_active.set(False)
                logging.debug("Date poll activity set to False.")
                
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
        is_date_poll_active = await self.config.is_date_poll_active()
        if is_date_poll_active:
            try:
                # Get the stored message and channel IDs
                message_id = await self.config.poll_message_id()
                channel_id = await self.config.poll_channel_id()

                # Get the poll channel and message
                poll_channel = self.bot.get_channel(channel_id)
                logging.debug(f"Restoring poll channel: {poll_channel}, ID: {channel_id}")
                if poll_channel is None:
                    logging.error(f"Couldn't fetch channel ID: {channel_id} during poll restoration.")
                    return

                poll_message = await poll_channel.fetch_message(message_id)

                # Get the stored votes
                date_votes_dict = await self.config.date_votes()
                date_votes = {datetime.datetime.strptime(date_string, "%a, %b %d"): vote for date_string, vote in date_votes_dict.items()}

                # Get the stored date buttons
                date_strings = await self.config.date_buttons()
                dates = [datetime.datetime.strptime(date_string, "%a, %b %d, %Y") for date_string in date_strings]
                view = DatePollView(dates, self.config)

                await poll_message.edit(view=view)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logging.error("Could not restore the poll")