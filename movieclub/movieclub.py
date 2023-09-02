# Standard library imports
import calendar
import datetime
from datetime import date
import logging
from typing import Literal
from collections import defaultdict

# Third-party library imports
from dateutil.relativedelta import relativedelta, SU  # Import SU (Sunday)
import discord
from discord import ui, Embed, Button, ButtonStyle, ActionRow
import holidays
from holidays.countries.united_states import UnitedStates

# Application-specific imports
from redbot.core import commands, Config
from redbot.core.bot import Red

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

MOVIE_CLUB_LOGO = '<:movieclub:1066636399530479696>\u2007<:logomovieclub1:1089715872551141416><:logomovieclub2:1089715916385820772><:logomovieclub3:1089715950225469450> <:logomovieclub4:1089715994743812157><:logomovieclub5:1089716031095832636><:logomovieclub6:1089716070497124502>'

def last_weekday_of_month(year, month, weekday):
    """Find the last occurrence of a weekday in a given month."""
    _, last_day = calendar.monthrange(year, month)
    last_date = datetime.date(year, month, last_day)
    offset = (last_date.weekday() - weekday) % 7
    last_date = last_date - datetime.timedelta(days=offset)
    return last_date

def last_weekday(weekday, month):
    """
    Returns the last weekday of the month.
    """
    logging.debug(f"Month in last_weekday: {month}")  # Debug print

    # Get the last day of the specified month
    next_month = month + relativedelta(months=1)

    last_day_of_month = next_month - datetime.timedelta(days=1)
    diff = last_day_of_month.weekday() - weekday
    offset = diff if diff >= 0 else diff + 7
    return last_day_of_month - datetime.timedelta(days=offset)

class DatePollButton(ui.Button):
    def __init__(self, label, date, config):
        super().__init__(style=ButtonStyle.primary, label=label)
        self.date = date
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        # let Discord know we received the interaction so it doesn't time us out
        # in case it takes a while to respond for some reason
        await interaction.response.defer()

        date = self.date.strftime("%a, %b %d")  # Get the date from the button label
        # Convert the user ID to a string
        # Otherwise, the user ID will be converted to an int, which will cause issues when we try to use it as a key in a dict
        # Users won't be able to undo their votes if this happens
        user_id = str(interaction.user.id)  

        # Debug log: Initial user_id type
        logging.debug(f"user_id initial type: {type(user_id)}")  

        # Initialize defaultdicts
        votes = defaultdict(int, await self.config.date_votes())  
        date_user_votes = defaultdict(dict, await self.config.date_user_votes())
        date_votes = defaultdict(bool, date_user_votes[date])  
        
        # Debug logs: Before updating votes and date_user_votes
        logging.debug(f"BEFORE update: votes={votes} typeofkeys={type(list(votes.keys())[0]) if votes else None}, dateVotes={date_votes} typeofkeys={type(list(date_votes.keys())[0]) if date_votes else None}")

        if user_id in date_votes:
            # Toggle off vote
            votes[date] -= 1
            if votes[date] == 0:  # if no votes are left for this date
                votes.pop(date)  # remove this date from votes
            del date_votes[user_id]
        else:
            # Toggle on vote
            votes[date] += 1
            date_votes[user_id] = True

        # Update config
        date_user_votes[date] = dict(date_votes)  
        await self.config.date_user_votes.set(dict(date_user_votes))  
        await self.config.date_votes.set(dict(votes))  

        # Debug logs: After updating votes and date_user_votes 
        logging.debug(f"AFTER update: votes={votes} typeofkeys={type(list(votes.keys())[0]) if votes else None}, dateVotes={date_votes} typeofkeys={type(list(date_votes.keys())[0]) if date_votes else None}")

        logging.debug(f"Votes: {votes}")
        logging.debug(f"Users that voted for above date: {date_votes}")

        # Updating the discord UI so users know what's happening
        # Update the button label with the vote count
        self.label = f"{date} ({votes[date]})"

        # Update the original message with the total unique vote count out of total members of role or server
        vote_owners = set()
        for owners in date_user_votes.values():
            vote_owners.update(owners.keys())

        # Initialize the set of unique voters
        unique_voters = set()

        # Look through each user vote list to find unique vote owners
        for user_vote_list in date_user_votes.values():
            unique_voters.update(user_vote_list.keys())

        logging.debug(f"Unique voters: {unique_voters}")

        # Check if voters are members of target_role by comparing voter's ids with role members' ids
        target_role_id = await self.config.target_role()  
        if target_role_id:
            target_role = discord.utils.get(interaction.guild.roles, id=target_role_id)
            target_role_member_ids = {str(member.id) for member in target_role.members} if target_role else {str(member.id) for member in interaction.guild.members}
        else:
            target_role_member_ids = {str(member.id) for member in interaction.guild.members}

        logging.debug(f"Target role member IDs: {target_role_member_ids}")

        unique_role_voters = unique_voters.intersection(target_role_member_ids)

        logging.debug(f"Unique role voters: {unique_role_voters}")

        # Calculate the percentage of unique voters who are also members of the target_role
        percentage_voted = (len(unique_role_voters) / len(target_role_member_ids)) * 100  

        # Change total_votes == 0 to len(unique_role_voters) == 0
        if len(unique_role_voters) == 0:
            await interaction.message.edit(content=f"")
        else:
            await interaction.message.edit(content=f"Update: {len(unique_role_voters)} out of {len(target_role_member_ids)} have voted ({percentage_voted:.2f}%)")

        # Send an ephemeral message to the user
        voted_dates = [date for date in votes.keys() if user_id in date_user_votes.get(date, {})]

        if user_id in date_votes:
            # User voted, list of new dates.
            sorted_dates = sorted(voted_dates)
            joined_dates = '\n- '.join(sorted_dates)
            vote_message = f"\u200B\n<:check:1103626473266479154> Voted for `{date}`. \n\nAvailability:\n- {joined_dates}"
        else:
        # User vote's removed, current list of dates.
            if voted_dates:
                sorted_dates = sorted(voted_dates)
                joined_dates = '\n- '.join(sorted_dates)
            else:
                joined_dates = 'None (SAD!)'
            vote_message = f"\u200B\n<:X_:1103627142425747567> Vote removed for `{date}`.\n\nAvailability:\n- {joined_dates}"

        await interaction.followup.send(vote_message, ephemeral=True)

class DatePollView(ui.View):
    def __init__(self, dates, config):
        super().__init__()
        for date in dates:
            self.add_item(DatePollButton(date.strftime("%a, %b %d"), date, config))

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

        # Add Thanksgiving Eve (Day before Thanksgiving)
        thanksgiving = [k for k, v in self.items() if "Thanksgiving" in v][0]  # Find the date of Thanksgiving
        thanksgiving_eve = thanksgiving - relativedelta(days=1)  # Calculate Thanksgiving Eve
        self[thanksgiving_eve] = "Thanksgiving Eve"

class MovieClub(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=289198795625857026, force_registration=True)
        self.config.register_global(date_votes={}, is_date_poll_active=False, date_user_votes={}, target_role=None)
        self.is_date_poll_active = False

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.group()
    async def movieclub(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid Movie Club command passed...')

    @movieclub.group()
    async def poll(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid poll command passed TEST!!!..')

    @poll.command()
    async def date(self, ctx, action: str, month: str = None):
        """Start or end date poll"""
        if action == "start":
            is_date_poll_active = await self.config.is_date_poll_active()
            if is_date_poll_active:
                await ctx.send('A date poll is already active.')
                return

            # Parse month if provided, else use the current month.
            if month:
                try:
                    month = datetime.datetime.strptime(month, "%B")
                except ValueError:
                    try:
                        month = datetime.datetime.strptime(month, "%b")
                    except ValueError:
                        await ctx.send('Invalid month. Please provide a full month name (e.g., "October") or a three-letter abbreviation (e.g., "Oct").')
                        return
                logging.debug(f"Parsed month: {month}")  # Debug print
            else:
                # If no month is provided, use the current month
                month = datetime.datetime.now()

                # Calculate the last Monday of the month
                last_monday = last_weekday(calendar.MONDAY, month)

                # Check if the last Monday is within 14 days or less.
                # This is done to ensure that there's enough time for people to vote and prepare for the event.
                # If not enough time is left, we consider the next month for scheduling.
                if (last_monday.date() - datetime.date.today()).days <= 14:
                    month = month + relativedelta(months=1)

            # Calculate the last Monday, Wednesday, Thursday, and Friday of the month
            # These dates are abritrary for our server, but can be changed to suit your needs
            last_monday = last_weekday(0, month)        # For Monday
            last_wednesday = last_weekday(2, month)     # For Wednesday
            last_thursday = last_weekday(3, month)      # For Thursday
            last_friday = last_weekday(4, month)        # For Friday
            last_saturday = last_weekday(5, month)      # For Saturday

            # Filter out dates that are public holidays.
            # Also avoid the days immediately before and after holidays.
            # This is to maximize the likelihood that people are available.
            us_holidays = CustomHolidays(years=month.year)
            dates = [last_monday, last_wednesday, last_thursday, last_friday, last_saturday]
            dates = [date for date in dates if date not in us_holidays and date - datetime.timedelta(days=1) not in us_holidays and date + datetime.timedelta(days=1) not in us_holidays]

            # Sort the dates so the buttons are in chronological order
            dates.sort()

            # Code for creating and sending the poll 
            # Create an embed for the poll
            embed = Embed(title=f"{MOVIE_CLUB_LOGO}\n\n", description="Vote for the date of the next movie night!")

            # Create a view with buttons for each date
            view = DatePollView(dates, self.config)

            # Send the embed with the view
            await ctx.send(embed=embed, view=view)

            # Set the poll as active
            await self.config.is_date_poll_active.set(True)

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
                    user_votes = date_user_votes.get(most_voted_date, {})
                    user_ids = ', '.join(f'<@{user_id}>' for user_id in user_votes.keys())
                    tie_message += f'**{most_voted_date}**\nPeople available: {user_ids}\n\n'

                await ctx.send(tie_message)

            # Reset the votes
            await self.config.date_votes.set({})
            await self.config.date_user_votes.set({})
            await self.config.is_date_poll_active.set(False)

        else:
            await ctx.send('Invalid action. Use "start" or "end".')

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
    
    @movieclub.command(name='setrole')
    async def set_target_role(self, ctx, role: discord.Role):
        """Sets the role for which to count the total members in polls. Default is @everyone."""
        await self.config.target_role.set(role.id)
        await ctx.send(f"The role for total member count in polls has been set to {role.name}.")