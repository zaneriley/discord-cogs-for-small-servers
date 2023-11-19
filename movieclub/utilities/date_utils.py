from datetime import datetime, timedelta
from typing import List

# Third-party library imports
from dateutil.relativedelta import relativedelta


class DateUtil:
    @staticmethod
    def normalize_date(date: datetime) -> datetime:
        """Returns a date with the time set to 00:00:00 for consistent comparison"""
        return datetime.combine(date.date(), datetime.min.time())

    @staticmethod
    def normalize_date(date: datetime.date) -> datetime:
        """Returns a date with the time set to 00:00:00 for consistent comparison"""
        return datetime.combine(date, datetime.min.time())

    @staticmethod
    def get_presentable_date(date: datetime) -> str:
        """Returns a date string in the format 'Mon, Sept 18'"""
        return date.strftime("%a, %b %d")

    @staticmethod
    def add_days(date: datetime, days: int) -> datetime:
        """Returns the date after adding the specified number of days"""
        return date + timedelta(days=days)

    @staticmethod
    def subtract_days(date: datetime, days: int) -> datetime:
        """Returns the date after subtracting the specified number of days"""
        return date - timedelta(days=days)

    @staticmethod
    def str_to_date(
        date_string: str, format_str: str = "%a, %b %d, %Y"
    ) -> List[datetime]:
        """Converts a date string to a datetime object using the specified format string"""
        return datetime.strptime(date_string, format_str)

    @staticmethod
    def sort_dates(dates: List[datetime]) -> List[datetime]:
        """Sorts and returns a list of datetime objects"""
        return sorted(dates)

    @staticmethod
    def now() -> datetime:
        """Returns current date with normalized time"""
        return DateUtil.normalize_date(datetime.now())

    @staticmethod
    def get_year_month(month: str, year: int = None) -> datetime:
        """Returns a datetime object in the format '%B' or '%b'"""
        year = year if year else DateUtil.now().year
        try:
            return datetime.strptime(month, "%B").replace(year=year)
        except ValueError:
            return datetime.strptime(month, "%b").replace(year=year)

    @staticmethod
    def is_within_days(date1: datetime, date2: datetime, days: int) -> bool:
        """Returns true if the difference between date1 and date2 is within the given number of days"""
        return (date1.date() - date2.date()).days <= days

    @staticmethod
    def to_next_month(date: datetime) -> datetime:
        """Returns the same date in the next month"""
        return date + relativedelta(months=1)
