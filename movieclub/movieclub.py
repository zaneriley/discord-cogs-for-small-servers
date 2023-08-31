from typing import Literal
import discord
from discord import ui, Embed, Button, ButtonStyle, ActionRow
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core import Config
from redbot.core.config import Config
import datetime
import calendar
from dateutil.relativedelta import relativedelta
import holidays
import logging

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
    if month.month == 12:
        next_month = month.replace(year=month.year + 1, month=1, day=1)
    else:
        next_month = month.replace(month=month.month + 1, day=1)
    last_day_of_month = next_month - datetime.timedelta(days=1)

    # Find the last occurrence of the weekday in the month
    offset = (last_day_of_month.weekday() - weekday) % 7
    last_weekday = last_day_of_month - datetime.timedelta(days=offset)

    # Type checking to ensure we can do date comparisons
    if not isinstance(last_weekday, datetime.date):
        raise TypeError(f"Expected datetime.date, got {type(last_weekday).__name__}")

    return last_weekday

class DatePollButton(ui.Button):
    def __init__(self, label, date, config):
        super().__init__(style=ButtonStyle.primary, label=label)
        self.date = date
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        date = self.date.strftime("%a, %b %d")  # Get the date from the button label
        user_id = interaction.user.id  # Get the user ID

        # Update the vote count for the date
        votes = await self.config.date_votes()  # Get the current votes

        # Update the users who voted for the date
        date_user_votes = await self.config.date_user_votes()  # Get the current date-user votes
        date_votes = date_user_votes.get(date, {})  # Get the users who voted for the date
        
        if user_id in date_votes:
            # Toggle off the vote
            votes[date] = votes.get(date, 0) - 1  # Decrement the vote count for the date
            del date_votes[user_id]
        else:
            # Toggle on the vote
            votes[date] = votes.get(date, 0) + 1  # Increment the vote count for the date
            date_votes[user_id] = True

        date_user_votes[date] = date_votes  # Update the users who voted for the date
        await self.config.date_user_votes.set(date_user_votes)  # Save the updated date-user votes

        await self.config.date_votes.set(votes)  # Save the updated votes


class DatePollView(ui.View):
    def __init__(self, dates, config):
        super().__init__()
        for date in dates:
            self.add_item(DatePollButton(date.strftime("%a, %b %d"), date, config))

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

class MovieClub(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=289198795625857026, force_registration=True)
        self.config.register_global(date_votes={}, is_date_poll_active=False, date_user_votes={})
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

                # If there are 14 days or less until the last Monday of the month, use the next month
                if (last_monday - month).days <= 14:
                    month = month + relativedelta(months=1)


            # Calculate the last Monday, Wednesday, Thursday, and Friday of the month
            last_monday = last_weekday(calendar.MONDAY, month)
            last_wednesday = last_weekday(calendar.WEDNESDAY, month)
            last_thursday = last_weekday(calendar.THURSDAY, month)
            last_friday = last_weekday(calendar.FRIDAY, month)
            last_saturday = last_weekday(calendar.SATURDAY, month)

            # Filter out the holidays and "avoided" days
            us_holidays = holidays.US(years=month.year)
            dates = [last_monday, last_wednesday, last_thursday, last_friday, last_saturday]
            dates = [date for date in dates if date not in us_holidays and date - datetime.timedelta(days=1) not in us_holidays and date + datetime.timedelta(days=1) not in us_holidays]

            # Sort the dates so the buttons are in chronological order
            dates.sort()

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