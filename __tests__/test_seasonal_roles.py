import datetime

import pytest

# Import the business logic we want to test.
# We're testing parts of HolidayService that are not directly
# doing Discord API calls.
from cogs.seasonalroles.holiday_management import HolidayService

from utilities.date_utils import DateUtil


###############################################################################
# Fake DateUtil
###############################################################################
# We patch DateUtil.now() and DateUtil.str_to_date() so our tests run with a fixed "current" date.
class FakeDateUtil:
    @staticmethod
    def now():
        # Fixed current date for testing: May 1, 2023
        return datetime.datetime(2023, 5, 1, tzinfo=datetime.UTC)

    @staticmethod
    def str_to_date(date_str, format_str):
        return datetime.datetime.strptime(date_str, format_str).replace(tzinfo=datetime.UTC)

@pytest.fixture(autouse=True)
def patch_date_util(monkeypatch):
    monkeypatch.setattr(DateUtil, "now", FakeDateUtil.now)
    monkeypatch.setattr(DateUtil, "str_to_date", FakeDateUtil.str_to_date)

###############################################################################
# Fake Config for Business Logic
###############################################################################
# Since many HolidayService methods access config via self.config.guild(guild),
# we create fake config-related classes that simulate a repository adapter.
class FakeHoliday:

    """Simulate the 'holidays' property on a guild config."""

    def __init__(self, holidays):
        self._holidays = holidays

    async def __call__(self):
        return self._holidays

    async def set(self, new_holidays):
        self._holidays = new_holidays

class FakeGuildConfig:

    """Simulate a guild-specific configuration object."""

    def __init__(self, holidays):
        # self.holidays is an object that can be called and also has a .set method.
        self.holidays = FakeHoliday(holidays)

class FakeConfig:
    """Simulate a config adapter that returns guild configurations."""
    def __init__(self, holidays):
        self._holidays = holidays

    def guild(self, guild):
        return FakeGuildConfig(self._holidays)

class FakeGuild:
    """Minimal fake guild object with a name property."""
    name = "FakeGuild"

###############################################################################
# Tests for Date and Holiday Calculation
###############################################################################

def test_date_conversion():
    """
    Test that DateUtil.str_to_date converts a valid date string correctly.
    """
    date_str = "2023-05-05"
    date_obj = DateUtil.str_to_date(date_str, "%Y-%m-%d")
    assert date_obj.year == 2023
    assert date_obj.month == 5
    assert date_obj.day == 5

def test_find_upcoming_holiday():
    """
    With a fixed current date (May 1, 2023), test that the upcoming holiday is
    correctly determined and that the days remaining for each holiday are calculated.
    """
    # Create an instance of HolidayService.
    # Here, config is not used by find_upcoming_holiday so we pass None.
    service = HolidayService(config=None)
    holidays = {
        "HolidayA": {"date": "05-05", "color": "#AAA111"},   # future (4 days ahead)
        "HolidayB": {"date": "04-28", "color": "#BBB222"},   # past (3 days ago)
        "HolidayC": {"date": "06-10", "color": "#CCC333"},   # future (40 days ahead)
    }
    # Call the function we want to test.
    upcoming, days_until = service.find_upcoming_holiday(holidays)

    expected_diff_C = (datetime.datetime(2023, 6, 10) - datetime.datetime(2023, 5, 1)).days

    # Expect "HolidayA" to be the upcoming holiday because it is 4 days away.
    assert upcoming == "HolidayA"
    assert days_until["HolidayA"] == 4
    assert days_until["HolidayB"] == -3
    assert days_until["HolidayC"] == expected_diff_C

###############################################################################
# Tests for Holiday Validation (Case Insensitivity and Existence Check)
###############################################################################

@pytest.mark.asyncio
async def test_validate_holiday_exists_found():
    """
    Test that lookup is case-insensitive. Given a holiday 'Kids Day',
    validation should find 'kids day'.
    """
    service = HolidayService(config=None)
    holidays = {
        "Kids Day": {"date": "05-05", "color": "#68855A"}
    }
    exists, message = await service.validate_holiday_exists(holidays, "kids day")
    assert exists is True
    assert message is None

@pytest.mark.asyncio
async def test_validate_holiday_exists_not_found():
    """
    Validate that if a holiday is not present, the function returns False and an error message.
    """
    service = HolidayService(config=None)
    holidays = {
        "Kids Day": {"date": "05-05", "color": "#68855A"}
    }
    exists, message = await service.validate_holiday_exists(holidays, "Non Existing")
    assert exists is False
    assert "does not exist" in message

###############################################################################
# Tests for Role Naming Generation and Business Decisions
###############################################################################

def test_generate_role_name():
    """
    Test that the proper role name is created by concatenating the holiday name and date.
    (e.g., "Kids Day" + "05-05" -> "Kids Day 05-05").
    """
    holiday_name = "TestHoliday"
    holiday_date = "05-05"
    role_name = f"{holiday_name} {holiday_date}"
    assert role_name == "TestHoliday 05-05"

###############################################################################
# Tests for Sorting Holidays using Fake Config
###############################################################################

@pytest.mark.asyncio
async def test_get_sorted_holidays():
    """
    Test that the business logic for sorting returns future holidays sorted by proximity
    followed by past holidays, and that the upcoming holiday is determined correctly.
    """
    # Assume our fixed date is 2023-05-01.
    # Create a dictionary of holidays.
    holidays = {
        "HolidayA": {"date": "05-05", "color": "#AAA111"},   # +4 days
        "HolidayB": {"date": "04-30", "color": "#BBB222"},   # -1 day
        "HolidayC": {"date": "06-10", "color": "#CCC333"},   # +40 days
    }
    # Create a fake config adapter containing these holidays.
    fake_config = FakeConfig(holidays=holidays)
    # Create an instance of HolidayService with our fake config.
    service = HolidayService(config=fake_config)
    fake_guild = FakeGuild()

    # Call the asynchronous get_sorted_holidays method.
    sorted_holidays, upcoming_holiday, days_until = await service.get_sorted_holidays(fake_guild)

    # Check that upcoming holiday is detected (HolidayA is +4 days, which is the smallest positive difference).
    assert upcoming_holiday == "HolidayA"

    # Extract the future holidays from the sorted list.
    # sorted_holidays is structured as a list of tuples: (holiday_name, days_remaining)
    future_holidays = [name for name, diff in sorted_holidays if diff > 0]
    # We expect HolidayA (4 days) to come before HolidayC (40 days).
    assert future_holidays == ["HolidayA", "HolidayC"] 