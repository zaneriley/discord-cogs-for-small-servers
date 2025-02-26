from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta


class DateUtil:

    """
    Utility class for working with dates and timedeltas.
    These largely focus on ensuring consistent dates by removing or preventing datetime objects from being created.
    If you need to work with datetime objects, use the datetime module directly.
    """

    @staticmethod
    def normalize_date(input_date: datetime | date) -> date:
        """Ensures the input is a datetime.date object."""
        if isinstance(input_date, datetime):
            return input_date.date()
        if isinstance(input_date, date):
            return input_date
        msg = "input_date must be a datetime.datetime or datetime.date instance"
        raise TypeError(msg)

    @staticmethod
    def get_presentable_date(input_date: date) -> str:
        """Returns a date string in the format 'Mon, Sept 18, YYYY'"""
        return input_date.strftime("%a, %b %d, %Y")

    @staticmethod
    def add_days(date: date, days: int) -> date:
        """Returns the date after adding the specified number of days"""
        return date + timedelta(days=days)

    @staticmethod
    def subtract_days(date: date, days: int) -> date:
        """Returns the date after subtracting the specified number of days"""
        return date - timedelta(days=days)

    @staticmethod
    def str_to_date(date_string: str, format_str: str = "%a, %b %d, %Y") -> date:
        """
        Converts a date string to a date object using the specified format string.

        Args:
        ----
            date_string: The date string to convert
            format_str: The format string to use (e.g., "%Y-%m-%d" for "2024-01-01")

        Returns:
        -------
            A date object representing the input string

        Raises:
        ------
            ValueError: If the date string doesn't match the format exactly or represents an invalid date

        """
        if not date_string:
            msg = "Date string cannot be empty"
            raise ValueError(msg)

        # For YYYY-MM-DD format, ensure proper formatting before parsing
        if format_str == "%Y-%m-%d":
            # Check that the format matches exactly (e.g., "2024-01-01" not "2024-1-1")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_string):
                msg = f"Date string '{date_string}' does not match format 'YYYY-MM-DD' (requires leading zeros)"
                raise ValueError(msg)

            # Extract year, month, day and validate them
            try:
                year_str, month_str, day_str = date_string.split("-")
                year = int(year_str)
                month = int(month_str)
                day = int(day_str)

                # Validate month range
                if month < 1 or month > 12:
                    msg = f"Month must be between 1 and 12, got {month}"
                    raise ValueError(msg)

                # Get the number of days in this month (accounting for leap years)
                is_leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                days_in_month = 29 if month == 2 and is_leap_year else [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month]

                # Validate day range
                if day < 1 or day > days_in_month:
                    if month == 2 and day == 29 and not is_leap_year:
                        msg = f"Invalid date: February 29 in non-leap year {year}"
                        raise ValueError(msg)
                    msg = f"Day must be between 1 and {days_in_month} for month {month}, got {day}"
                    raise ValueError(msg)
            except ValueError as e:
                if "invalid literal for int()" in str(e):
                    msg = f"Invalid date components in '{date_string}' - all parts must be numbers"
                    raise ValueError(msg) from e
                raise

        try:
            return datetime.strptime(date_string, format_str).date()
        except ValueError as e:
            msg = f"Invalid date string '{date_string}' for format '{format_str}'"
            raise ValueError(msg) from e

    @staticmethod
    def sort_dates(dates: list[date]) -> list[date]:
        """Sorts and returns a list of date objects"""
        return sorted(dates)

    @staticmethod
    def now() -> date:
        """Returns current date"""
        return date.today()

    @staticmethod
    def get_year_month(month: str, year: int | None = None) -> date:
        """Returns a date object for the first day of the specified '%B' or '%b' month"""
        year = year if year else DateUtil.now().year
        try:
            # Correctly use datetime.strptime and convert to date
            return datetime.strptime(f"{year} {month}", "%Y %B").date()
        except ValueError:
            # Handle abbreviated month names
            return datetime.strptime(f"{year} {month}", "%Y %b").date()

    @staticmethod
    def is_within_days(date1: date, date2: date, days: int) -> bool:
        """Returns true if the difference between date1 and date2 is within the given number of days"""
        return (date1.date() - date2.date()).days <= days

    @staticmethod
    def to_next_month(date: date) -> date:
        """Returns the same date in the next month"""
        return date + relativedelta(months=1)

    @staticmethod
    def get_holiday_date(month: int, day: int, year: int | None = None) -> date:
        """
        Returns a date object for the specified month and day in the provided or current year.

        Args:
            month: Month (1-12)
            day: Day of month
            year: Year (defaults to current year if not provided)

        Returns:
            date: A date object representing the holiday

        Raises:
            ValueError: If the month or day are invalid

        """
        if year is None:
            year = DateUtil.now().year

        # Validate month and day
        if month < 1 or month > 12:
            msg = f"Month must be between 1 and 12, got {month}"
            raise ValueError(msg)

        # Get the number of days in this month (accounting for leap years)
        is_leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        days_in_month = 29 if month == 2 and is_leap_year else [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month]

        if day < 1 or day > days_in_month:
            msg = f"Day must be between 1 and {days_in_month} for month {month}, got {day}"
            raise ValueError(msg)

        return date(year, month, day)

    @staticmethod
    def is_same_day(date1: date, date2: date) -> bool:
        """
        Checks if two dates represent the same day.

        Args:
            date1: First date to compare
            date2: Second date to compare

        Returns:
            bool: True if the dates represent the same day, False otherwise

        """
        # Normalize in case datetime objects are passed
        date1 = DateUtil.normalize_date(date1)
        date2 = DateUtil.normalize_date(date2)

        return date1.year == date2.year and date1.month == date2.month and date1.day == date2.day
