import datetime
from datetime import date, timedelta
from typing import Literal, List
from collections import defaultdict

# Third-party library imports
from dateutil.relativedelta import relativedelta, SU  # Import SU (Sunday)
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
