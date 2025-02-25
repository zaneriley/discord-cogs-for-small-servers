from __future__ import annotations

import logging
from datetime import date, datetime, timezone

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants for date-related values
FEBRUARY = 2
FEB_29 = 29
FEB_28 = 28


def is_leap_year(year: int) -> bool:
    """
    Check if the given year is a leap year.

    Args:
    ----
        year: The year to check

    Returns:
    -------
        bool: True if the year is a leap year, False otherwise

    """
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def compute_days_until_holiday(
    holiday_date_str: str, current_date: date | None = None
) -> int:
    """
    Calculate the number of days until the specified holiday.
    If the holiday has already occurred this year, it calculates for next year.

    Args:
    ----
        holiday_date_str: Date of the holiday in format MM-DD (e.g., 12-25 for Christmas)
        current_date: Current date to calculate from (defaults to today if not provided)

    Returns:
    -------
        int: Number of days until the holiday

    """
    if current_date is None:
        current_date = datetime.now(timezone.utc).date()

    try:
        # Parse the holiday date (month-day)
        holiday_month, holiday_day = map(int, holiday_date_str.split("-"))

        # Create date objects for this year's holiday
        this_year = current_date.year
        try:
            this_year_holiday = date(this_year, holiday_month, holiday_day)
        except ValueError:
            # Handle Feb 29 in non-leap years
            if holiday_month == FEBRUARY and holiday_day == FEB_29 and not is_leap_year(this_year):
                this_year_holiday = date(this_year, FEBRUARY, FEB_28)
            else:
                raise

        # Calculate days until the holiday
        days_until = (this_year_holiday - current_date).days

        # If the holiday has already passed this year, calculate for next year
        if days_until < 0:
            next_year = this_year + 1
            try:
                next_year_holiday = date(next_year, holiday_month, holiday_day)
            except ValueError:
                # Handle Feb 29 in non-leap years
                if (
                    holiday_month == FEBRUARY
                    and holiday_day == FEB_29
                    and not is_leap_year(next_year)
                ):
                    next_year_holiday = date(next_year, FEBRUARY, FEB_28)
                else:
                    raise
            days_until = (next_year_holiday - current_date).days

    except ValueError as e:
        msg = f"Invalid date format. Expected MM-DD, got {holiday_date_str}"
        logger.exception(f"{msg}")
        raise ValueError(msg) from e
    else:
        return days_until


def find_upcoming_holiday(
    holidays: dict, current_date: date | None = None
) -> tuple[str | None, dict[str, int]]:
    """
    Find the next upcoming holiday and compute days until each holiday.

    Args:
        holidays: Dictionary mapping holiday names to their details including date
        current_date: Optional date to compute from (defaults to DateUtil.now())

    Returns:
        Tuple containing:
        - Name of the next upcoming holiday (or None if no holidays)
        - Dictionary mapping each holiday name to days until that holiday

    """
    if not holidays:
        return None, {}

    days_until = {}
    upcoming_holiday = None
    min_days_diff = float("inf")

    for name, details in holidays.items():
        days_diff = compute_days_until_holiday(details["date"], current_date)
        days_until[name] = days_diff

        # Update upcoming holiday if this one is sooner (and in the future)
        if days_diff > 0 and days_diff < min_days_diff:
            min_days_diff = days_diff
            upcoming_holiday = name

    return upcoming_holiday, days_until


def get_sorted_holidays(
    holidays: dict, current_date: date | None = None
) -> list[tuple[str, int]]:
    """
    Get holidays sorted by their days until occurrence.
    Future holidays are sorted by closest first, followed by past holidays.

    Args:
        holidays: Dictionary mapping holiday names to their details including date
        current_date: Optional date to compute from (defaults to DateUtil.now())

    Returns:
        List of tuples (holiday_name, days_until) sorted by days until,
        with future holidays first (positive days) followed by past holidays.

    """
    if not holidays:
        return []

    # Get days until each holiday
    _, days_until = find_upcoming_holiday(holidays, current_date)

    # Split into future and past holidays
    future_holidays = [(name, days) for name, days in days_until.items() if days > 0]
    past_holidays = [(name, days) for name, days in days_until.items() if days <= 0]

    # Sort future holidays by closest first, past holidays by most recently passed
    future_holidays.sort(key=lambda x: x[1])  # Sort by days until
    past_holidays.sort(key=lambda x: x[1], reverse=True)  # Sort by days ago

    return future_holidays + past_holidays
