from datetime import datetime, date
from typing import List, Union
from dateutil.relativedelta import relativedelta


class DateUtil:
    """
    Utility class for working with dates and timedeltas.
    These largely focus on ensuring consistent dates by removing or preventing datetime objects from being created.
    If you need to work with datetime objects, use the datetime module directly.
    """

    @staticmethod
    def normalize_date(input_date: Union[datetime, date]) -> date:
        """Ensures the input is a datetime.date object."""
        if isinstance(input_date, datetime):
            return input_date.date()
        elif isinstance(input_date, date):
            return input_date
        else:
            raise TypeError(
                "input_date must be a datetime.datetime or datetime.date instance"
            )

    @staticmethod
    def get_presentable_date(input_date: date) -> str:
        """Returns a date string in the format 'Mon, Sept 18, YYYY'"""
        return input_date.strftime("%a, %b %d, %Y")

    @staticmethod
    def add_days(date: date, days: int) -> date:
        """Returns the date after adding the specified number of days"""
        return date + delta(days=days)

    @staticmethod
    def subtract_days(date: date, days: int) -> date:
        """Returns the date after subtracting the specified number of days"""
        return date - delta(days=days)

    @staticmethod
    def str_to_date(date_string: str, format_str: str = "%a, %b %d, %Y") -> List[date]:
        """Converts a date string to a date object using the specified format string"""
        return date.strp(date_string, format_str)

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
