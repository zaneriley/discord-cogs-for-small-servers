# Standard imports
from __future__ import annotations

import calendar
import datetime
import logging
from collections import defaultdict
from datetime import date, timedelta

import discord

# Third-party library imports
from dateutil.relativedelta import SU, relativedelta  # Import SU (Sunday)
from discord import ButtonStyle, Embed, ui
from discord.errors import HTTPException
from discord.ext import commands, tasks
from holidays.countries.united_states import UnitedStates

# Application-specific imports
from movieclub.classes.poll import Poll
from movieclub.constants import MOVIE_CLUB_LOGO
from utilities.date_utils import DateUtil


def last_days_of_month(input_date: date, final_days: int = 14) -> list[date]:
    """Find the last days in a given month and return as a list."""
    _, last_day = calendar.monthrange(input_date.year, input_date.month)
    last_date = date(input_date.year, input_date.month, last_day)  # Corrected
    first_date = last_date - timedelta(days=final_days)
    return [first_date + timedelta(days=i) for i in range(final_days + 1)]


def get_filtered_candidate_dates(candidate_dates: list[date], us_holidays: set[date]) -> list[date]:
    filtered_dates = []
    removed_dates = []
    removal_reasons = defaultdict(int)

    for candidate_date in candidate_dates:
        # Assume weekends are 6 (Saturday) and 7 (Sunday), and Monday is 1
        if candidate_date.isoweekday() in [6, 7, 1]:
            removal_reasons["weekend_or_monday"] += 1
            removed_dates.append(candidate_date)
            continue
        if any((candidate_date + timedelta(days=offset)) in us_holidays for offset in (-1, 0, 1)):
            removal_reasons["holiday_or_adjacent"] += 1
            removed_dates.append(candidate_date)
            continue
        filtered_dates.append(candidate_date)

    if removed_dates:
        logging.debug(f"Removed dates: {', '.join(map(str, removed_dates))}")
    if filtered_dates:
        logging.debug(f"Remaining dates: {', '.join(map(str, filtered_dates))}")

    # Log a summary of the removal reasons and total dates
    logging.debug(f"Date removal summary: {dict(removal_reasons)}")
    logging.debug(f"Total dates checked: {len(candidate_dates)}, filtered: {len(filtered_dates)}")

    return filtered_dates


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
        thanksgiving = next(k for k, v in self.items() if "Thanksgiving" in v)  # Find the date of Thanksgiving
        thanksgiving_eve = thanksgiving - relativedelta(days=1)  # Calculate Thanksgiving Eve
        self[thanksgiving_eve] = "Thanksgiving Eve"


class DatePollView(ui.View):
    def __init__(self, dates: list[date], config, guild, poll_id):
        super().__init__()
        for date in dates:
            self.add_item(DatePollButton(date, config, guild, poll_id))


class DatePollButton(ui.Button):
    def __init__(self, date: date, config, guild, poll_id):
        super().__init__(style=ButtonStyle.primary, label=DateUtil.get_presentable_date(date))
        self.date = DateUtil.normalize_date(date)
        logging.debug(f"Creating DatePollButton for date: {self.date}")

        self.config = config
        self.guild = guild
        self.poll_id = poll_id

    async def get_votes(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "votes")

    async def set_votes(self, votes):
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "votes", value=votes)

    async def get_user_votes(self):
        return await self.config.guild(self.guild).polls.get_raw(self.poll_id, "user_votes")

    async def set_user_votes(self, user_votes):
        await self.config.guild(self.guild).polls.set_raw(self.poll_id, "user_votes", value=user_votes)

    async def get_target_role(self):
        return await self.config.guild(self.guild).target_role()

    async def callback(self, interaction: discord.Interaction):
        # let Discord know we received the interaction so it doesn't time us out
        # in case it takes a while to respond for some reason
        await interaction.response.defer()
        date_str = DateUtil.get_presentable_date(self.date)  # Convert datetime to string for display
        user_id = str(interaction.user.id)

        logging.debug("Fetching current votes and user votes")
        votes = defaultdict(int, await self.get_votes())
        date_user_votes = defaultdict(dict, await self.get_user_votes())
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
        logging.debug("Updating votes and user votes")
        await self.set_user_votes(dict(date_user_votes))
        await self.set_votes(dict(votes))
        logging.debug(f"Updated votes: {votes} and user votes: {date_user_votes}")
        logging.debug(f"AFTER update: votes={votes}, dateVotes={date_votes}")

        logging.debug(f"Votes: {votes}")
        logging.debug(f"Users that voted for above date: {date_votes}")
        self.label = f"{date_str} ({votes[date_key]})"  # Show the votes for the updated date

        unique_voters = set()
        for user_vote_list in date_user_votes.values():
            unique_voters.update(user_vote_list.keys())
        logging.debug(f"Unique voters: {unique_voters}")

        target_role = await self.get_target_role()
        if target_role:
            target_role = discord.utils.get(interaction.guild.roles, id=target_role)
            target_role_member_ids = (
                {str(member.id) for member in target_role.members} if target_role else {interaction.guild.members}
            )
        else:
            target_role_member_ids = {member.id for member in interaction.guild.members}
        logging.debug(f"Target role member IDs: {target_role_member_ids}")

        unique_role_voters = unique_voters.intersection(
            target_role_member_ids
        )  # Calculate the voters in the target role
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
        original_embed.set_footer(
            text=footer_text,
            icon_url="https://cdn3.emoji.gg/emojis/1075-pinkhearts.gif",
        )

        # Now editing the embed with the original_embed
        await interaction.message.edit(embed=original_embed)

        # Send an ephemeral message to the user
        voted_dates = [date for date in votes if user_id in date_user_votes.get(date, {})]

        def get_sorted_presentable_dates(dates):
            datetime_dates = [
                datetime.datetime.strptime(date, "%Y-%m-%d") for date in dates
            ]  # Convert stringified dates back to datetime
            sorted_dates = DateUtil.sort_dates(datetime_dates)  # Adjust this function to accept datetime formats
            return "\n- ".join(DateUtil.get_presentable_date(date) for date in sorted_dates)

        # The part of the code where you check and format the dates
        if voted_dates:
            joined_dates = get_sorted_presentable_dates(voted_dates)
        else:
            joined_dates = "None (SAD!)"

        if user_id in date_votes:
            vote_icon = "<:check:1103626473266479154>"
            action_message = f"Voted for `{date_str}`"
        else:
            vote_icon = "<:X_:1103627142425747567>"
            action_message = f"Vote removed for `{date_str}`"

        vote_message = f"\u200B\n{vote_icon} {action_message}. \n\nAvailability:\n- {joined_dates}"

        # Update the message with the new embed
        await interaction.followup.send(vote_message, ephemeral=True)


class DatePoll(Poll):
    def __init__(self, bot, config, guild):
        super().__init__(bot, config, guild, "date_poll")

    async def start_poll(self, ctx: commands.Context, action: str, month: str | None = None) -> None:
        try:
            logging.debug(f"Starting poll with action: {action}, month: {month}")
            candidate_dates = []
            us_holidays = []
            if action == "start":
                if month:
                    try:
                        logging.debug(f"Month provided: {month}")
                        month_date = DateUtil.get_year_month(month)
                        candidate_dates = last_days_of_month(month_date)
                        logging.debug(f"Candidate dates generated for {month}: {', '.join(map(str, candidate_dates))}")

                        us_holidays = CustomHolidays(years=month_date.year)
                        filtered_candidate_dates = get_filtered_candidate_dates(candidate_dates, us_holidays)
                        if len(filtered_candidate_dates) < 3:
                            await ctx.send("There are not enough dates available to start a poll.")
                            return
                    except Exception as e:
                        logging.exception(f"Error processing specific month '{month}': {e}")
                        await ctx.send("An error occurred while processing the specified month. Please try again.")
                        return
                else:
                    current_date = DateUtil.now()
                    logging.debug(f"No month provided, using today's date... {current_date}")
                    delta_days_from_current_date = current_date + timedelta(days=14)
                    if delta_days_from_current_date.month != current_date.month:
                        current_date = datetime.date(
                            delta_days_from_current_date.year,
                            delta_days_from_current_date.month,
                            1,
                        )
                        candidate_dates = last_days_of_month(current_date)
                        us_holidays = CustomHolidays(years=delta_days_from_current_date.year)
                    else:
                        candidate_dates = last_days_of_month(current_date)
                        us_holidays = CustomHolidays(years=current_date.year)
                        # remove days that are less than 14 days from today
                        for date in candidate_dates:
                            if delta_days_from_current_date > date:
                                candidate_dates.remove(date)

                    filtered_candidate_dates = get_filtered_candidate_dates(candidate_dates, us_holidays)
                    logging.debug(f"Filtered dates: {', '.join(map(str, filtered_candidate_dates))}")
                    if len(filtered_candidate_dates) < 3:
                        while True:
                            logging.debug(
                                f"Trying next month: {current_date.month}-{current_date.year}, found {len(filtered_candidate_dates)} suitable dates"
                            )
                            current_date = DateUtil.to_next_month(
                                datetime.date(current_date.year, current_date.month, 1)
                            )
                            candidate_dates = last_days_of_month(current_date)
                            us_holidays = CustomHolidays(years=current_date.year)
                            filtered_candidate_dates = get_filtered_candidate_dates(candidate_dates, us_holidays)

                            if len(filtered_candidate_dates) >= 3:
                                break
            logging.debug(f"Filtered dates before DatePollView: {', '.join(map(str, filtered_candidate_dates))}")
            dates = filtered_candidate_dates[:5]
            logging.debug(f"Passing dates to DatePollView: {', '.join(map(str, dates))}")

            target_role = await self.get_target_role()
            if target_role:
                mention_str = f"<@&{target_role}>" if target_role else ""
            else:
                mention_str = ""

            logging.debug(f"Sending poll message for dates: {', '.join(map(str, dates))}")

            # TODO: Move to discord.py functions?
            try:
                embed = Embed(title=f"{MOVIE_CLUB_LOGO}\n\n")
                embed.add_field(
                    name="Showtimes",
                    value="6pm Pacific ∙ 7pm High Peak ∙ 8pm Heartland ∙ 9pm Eastern ∙ 10am 東京",
                    inline=False,
                )

                view = DatePollView(dates, self.config, self.guild, self.poll_id)
                msg = await ctx.send(
                    content=f"\u200B\nVote for the date of the next movie night! {mention_str}\n\u200B",
                    embed=embed,
                    view=view,
                )
                logging.debug(f"Generated message id: {msg.id}")
                await self.set_message_id(msg.id)
                await self.set_poll_channel_id(msg.channel.id)
            except Exception as e:
                logging.exception(f"Failed to send poll message: {e}")
                await ctx.send("An error occurred while trying to send the poll message. Please try again later.")
                return

            date_strings = [date.strftime("%a, %b %d, %Y") for date in dates]
            await self.add_buttons(date_strings)

            close_weeks_before = 1  # For example, make this configurable
            # Suppose we pick the most-voted date as 'show_date' after the poll ends
            # We'll store an approximate "poll_end_date" for auto-close
            # If you're fetching an actual show date, this is where you'd do that logic
            # For demonstration, let's guess the show date is the last candidate
            show_date = max(dates) if dates else None
            if show_date:
                poll_end_date = show_date - timedelta(weeks=close_weeks_before)
                # Save it in config for a background task to check
                await self.config.guild(ctx.guild).polls.set_raw(
                    self.poll_id, "scheduled_close_date", value=poll_end_date.isoformat()
                )
        except Exception as e:
            logging.exception(f"Failed to send poll message: {e}")
            await ctx.send("An error occurred while trying to send the poll message. Please try again later.")
            return

        # This is the corrected placement for handling invalid actions
        if action not in ["start", "end"]:
            await ctx.send('Invalid action. Use "start" or "end".')

    async def end_poll(self, ctx):
        try:
            votes = await self.get_votes()
            if len(votes) == 0:
                await ctx.send("The poll was manually closed. No one voted in this poll.")
                return

            max_votes = max(votes.values())
            most_voted_dates = [date for date, vote_count in votes.items() if vote_count == max_votes]
            if len(most_voted_dates) > 1:
                tied_message = f"\u200B\n{MOVIE_CLUB_LOGO}\n\nThere is a tie! <:swirl:1103626545685336116> The most voted dates are:\n\n"
            else:
                tied_message = f"\u200B\n{MOVIE_CLUB_LOGO}\n\n The most voted date is:\n\n"
            date_user_votes = await self.get_user_votes()
            for most_voted_date in most_voted_dates:
                date_to_check = datetime.datetime.strptime(most_voted_date, "%Y-%m-%d")
                presentable_date = DateUtil.get_presentable_date(date_to_check)
                str_date_to_check = date_to_check.strftime("%Y-%m-%d")
                user_votes = date_user_votes.get(str_date_to_check, {})
                user_ids = ", ".join(f"<@{user_id}>" for user_id in user_votes)
                tied_message += f"**{presentable_date}**\nAvailable: {user_ids}\n\n"

            # gather user IDs from date_user_votes
            all_voters = set()
            for user_dict in date_user_votes.values():
                # user_dict is { user_id: <stuff> }
                all_voters.update(user_dict.keys())

            # Build a mention for each:
            mention_list = " ".join(f"<@{uid}>" for uid in all_voters)

            # your existing tied_message ...
            tied_message += f"\nThanks for participating! Shoutout to: {mention_list}"

            await ctx.send(tied_message)
            # then remove poll from config...
            await self.remove_poll_from_config()
        except Exception as e:
            logging.exception(f"Unable to end Date Poll due to: {e!s}")

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

        date_strings = await self.get_buttons()
        dates = [DateUtil.str_to_date(date_string) for date_string in date_strings]  # Converted line to use DateUtil
        view = DatePollView(dates, self.config, self.guild, self.poll_id)
        await poll_message.edit(view=view)

    async def build_view(self):
        date_strings = await self.get_buttons()
        logging.debug(f"Date strings: {date_strings}")
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

    @tasks.loop(minutes=30)
    async def auto_close_if_due(self):
        """
        Periodically check if the poll is past the scheduled close date.
        If so, end it automatically.
        """
        try:
            scheduled_close_date_str = await self.config.guild(self.guild).polls.get_raw(
                self.poll_id, "scheduled_close_date", default=None
            )
            if not scheduled_close_date_str:
                return
            scheduled_close_date = datetime.datetime.fromisoformat(scheduled_close_date_str).date()
            if datetime.date.today() >= scheduled_close_date:
                # Time to close the poll
                ctx_channel_id = await self.get_poll_channel_id()
                channel = self.bot.get_channel(ctx_channel_id)
                if channel:
                    dummy_ctx = await self.bot.get_context(await channel.fetch_message(await self.get_message_id()))
                    await self.end_poll(dummy_ctx)
                self.auto_close_if_due.cancel()
        except Exception as e:
            logging.exception(f"Error in auto_close_if_due for {self.poll_id}: {e}")
