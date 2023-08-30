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

def last_weekday_of_month(year, month, weekday):
    """Find the last occurrence of a weekday in a given month."""
    _, last_day = calendar.monthrange(year, month)
    last_date = datetime.date(year, month, last_day)
    offset = (last_date.weekday() - weekday) % 7
    last_date = last_date - datetime.timedelta(days=offset)
    return last_date

def last_weekday(weekday):
    """Find the last occurrence of a weekday in the current month or the next month."""
    today = datetime.date.today()
    last_date = last_weekday_of_month(today.year, today.month, weekday)

    # If the last weekday is within the next 14 days, find the last weekday of the next month
    if (last_date - today).days < 14:
        next_month_date = today + relativedelta(months=1)
        last_date = last_weekday_of_month(next_month_date.year, next_month_date.month, weekday)

    return last_date

class DatePollButton(ui.Button):
    def __init__(self, label, date, config):
        super().__init__(style=ButtonStyle.primary, label=label)
        self.date = date
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        date = self.date.strftime("%a, %b %d")  # Get the date from the button label
        votes = await self.config.date_votes()  # Get the current votes
        votes[date] = votes.get(date, 0) + 1  # Increment the vote count for the date
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
        self.config.register_global(date_votes={}, is_date_poll_active=False)
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
    async def date(self, ctx, action: str):
        """Start or end date poll"""
        if action == "start":
            is_date_poll_active = await self.config.is_date_poll_active()
            if is_date_poll_active:
                await ctx.send('A date poll is already active.')
                return

            # Calculate the last Monday, Wednesday, Thursday, and Friday of the month
            last_monday = last_weekday(calendar.MONDAY)
            last_wednesday = last_weekday(calendar.WEDNESDAY)
            last_thursday = last_weekday(calendar.THURSDAY)
            last_friday = last_weekday(calendar.FRIDAY)
            last_saturday = last_weekday(calendar.SATURDAY)

            # Create an embed for the poll
            embed = Embed(title="<:movieclub:1066636399530479696> <:logomovieclub1:1089715872551141416><:logomovieclub2:1089715916385820772><:logomovieclub3:1089715950225469450> <:logomovieclub4:1089715994743812157><:logomovieclub5:1089716031095832636><:logomovieclub6:1089716070497124502>", description="Vote for the date of the next movie night!")

            # Create a view with buttons for each date
            view = DatePollView([last_monday, last_wednesday, last_thursday, last_friday, last_saturday], self.config)

            # Send the embed with the view
            await ctx.send(embed=embed, view=view)

            # Set the poll as active
            await self.config.is_date_poll_active.set(True)
        elif action == "end":
            # Get the votes
            votes = await self.config.date_votes()
            # Find the date with the most votes
            most_voted_date = max(votes, key=votes.get)
            # Announce the most voted date
            await ctx.send(f'The most voted date is {most_voted_date}')
            # Reset the votes
            await self.config.date_votes.set({})
            # Set the poll as inactive
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