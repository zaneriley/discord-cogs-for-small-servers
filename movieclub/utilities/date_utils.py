from datetime import datetime, date, timedelta
from typing import List, Union
from dateutil.relativedelta import relativedelta
import logging


class DateUtil:
    @staticmethod
    def normalize_date(input_date: Union[datetime, date]) -> date:
        """Ensures the input is a datetime.date object."""
        if isinstance(input_date, datetime):
            return input_date.date()  # Convert datetime to date
        elif isinstance(input_date, date):
            return input_date  # Already a date, return as is
        else:
            raise TypeError(
                "input_date must be a datetime.datetime or datetime.date instance"
            )

    @staticmethod
    def get_presentable_date(input_date: date) -> str:
        """Returns a date string in the format 'Mon, Sept 18, YYYY'"""
        return input_date.strftime("%a, %b %d")

    @staticmethod
    def add_days(date: date, days: int) -> date:
        """Returns the date after adding the specified number of days"""
        return date + timedelta(days=days)

    @staticmethod
    def subtract_days(date: date, days: int) -> date:
        """Returns the date after subtracting the specified number of days"""
        return date - timedelta(days=days)

    @staticmethod
    def str_to_date(
        date_string: str, format_str: str = "%a, %b %d, %Y"
    ) -> Union[date, None]:
        """Converts a date string to a date object using the specified format string.
        Returns None if conversion fails."""
        try:
            return datetime.strptime(date_string, format_str).date()
        except ValueError as e:
            logging.error(
                f"Failed to convert '{date_string}' to date with format '{format_str}': {e}"
            )
            return None

    @staticmethod
    def sort_dates(dates: List[date]) -> List[date]:
        """Sorts and returns a list of date objects"""
        return sorted(dates)

    @staticmethod
    def now() -> date:
        """Returns current date"""
        return date.today()

    @staticmethod
    def get_year_month(month: str, year: int = None) -> date:
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
    def get_iso_weekdays_from_names(day_names: List[str]) -> List[int]:
        """
        Converts a list of day names to their corresponding ISO weekday numbers.
        Raises ValueError for invalid day names.
        """
        day_name_to_iso = {
            "Monday": 1,
            "Tuesday": 2,
            "Wednesday": 3,
            "Thursday": 4,
            "Friday": 5,
            "Saturday": 6,
            "Sunday": 7,
        }
        iso_numbers = []
        for day in day_names:
            if day in day_name_to_iso:
                iso_numbers.append(day_name_to_iso[day])
            else:
                raise ValueError(f"Invalid day name: {day}")
        return iso_numbers
