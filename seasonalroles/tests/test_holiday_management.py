"""Tests for HolidayService business logic."""

import datetime
from datetime import timezone

import pytest
from cogs.seasonalroles.holiday_management import HolidayService

###############################################################################
# Test Fixtures and Helpers
###############################################################################


class FakeDateUtil:
    @staticmethod
    def now():
        # Fixed current date for testing: May 1, 2023
        return datetime.datetime(2023, 5, 1, tzinfo=timezone.utc)


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


@pytest.fixture(autouse=True)
def patch_date_util(monkeypatch):
    monkeypatch.setattr("utilities.date_utils.DateUtil.now", FakeDateUtil.now)


###############################################################################
# Tests for Holiday Validation and Existence Check
###############################################################################


@pytest.mark.asyncio
async def test_validate_holiday_exists_found():
    """Test that lookup is case-insensitive."""
    service = HolidayService(config=None)
    holidays = {"Kids Day": {"date": "05-05", "color": "#68855A"}}
    exists, message = await service.validate_holiday_exists(holidays, "kids day")
    assert exists is True
    assert message is None


@pytest.mark.asyncio
async def test_validate_holiday_exists_edge_cases():
    """Test edge cases for holiday validation."""
    service = HolidayService(config=None)
    holidays = {
        "Kids Day ": {"date": "05-05", "color": "#68855A"},  # Extra space in name
        " Spring Festival": {"date": "03-20", "color": "#68855A"},  # Leading space
        "Summer\tFestival": {"date": "06-21", "color": "#68855A"},  # Tab in name
    }

    # Test with extra whitespace in search
    exists, message = await service.validate_holiday_exists(holidays, "Kids Day  ")
    assert exists is True
    assert message is None

    # Test with leading whitespace in search
    exists, message = await service.validate_holiday_exists(
        holidays, "  Spring Festival"
    )
    assert exists is True
    assert message is None

    # Test with normalized whitespace
    exists, message = await service.validate_holiday_exists(holidays, "Summer Festival")
    assert exists is True
    assert message is None


@pytest.mark.asyncio
async def test_validate_holiday_exists_not_found():
    """Test that non-existent holidays return appropriate response."""
    service = HolidayService(config=None)
    holidays = {"Kids Day": {"date": "05-05", "color": "#68855A"}}
    exists, message = await service.validate_holiday_exists(holidays, "Non Existing")
    assert exists is False
    assert "does not exist" in message


###############################################################################
# Tests for Holiday Sorting
###############################################################################


@pytest.mark.asyncio
async def test_get_sorted_holidays():
    """Test holiday sorting business logic."""
    # Assume our fixed date is 2023-05-01
    holidays = {
        "HolidayA": {"date": "05-05", "color": "#AAA111"},  # +4 days
        "HolidayB": {"date": "04-30", "color": "#BBB222"},  # -1 day
        "HolidayC": {"date": "06-10", "color": "#CCC333"},  # +40 days
    }
    fake_config = FakeConfig(holidays=holidays)
    service = HolidayService(config=fake_config)
    fake_guild = FakeGuild()

    sorted_holidays, upcoming_holiday, days_until = await service.get_sorted_holidays(
        fake_guild
    )

    assert upcoming_holiday == "HolidayA"
    future_holidays = [name for name, diff in sorted_holidays if diff > 0]
    assert future_holidays == ["HolidayA", "HolidayC"]


@pytest.mark.asyncio
async def test_get_sorted_holidays_edge_cases():
    """Test edge cases for holiday sorting."""
    # Test with holidays on the same day
    holidays_same_day = {
        "HolidayA": {"date": "05-05", "color": "#AAA111"},
        "HolidayB": {"date": "05-05", "color": "#BBB222"},
    }
    fake_config = FakeConfig(holidays=holidays_same_day)
    service = HolidayService(config=fake_config)
    fake_guild = FakeGuild()

    sorted_holidays, upcoming_holiday, days_until = await service.get_sorted_holidays(
        fake_guild
    )

    # Both holidays should have the same days_until value
    assert len(set(days_until.values())) == 1
    # Either holiday could be the upcoming one
    assert upcoming_holiday in ["HolidayA", "HolidayB"]

    # Test with malformed holiday data
    holidays_malformed = {
        "HolidayA": {"date": "05-05", "color": "#AAA111"},
        "HolidayB": {},  # Missing required fields
        "HolidayC": {"color": "#CCC333"},  # Missing date
    }
    fake_config = FakeConfig(holidays=holidays_malformed)
    service = HolidayService(config=fake_config)

    # Should raise an error due to missing required fields
    with pytest.raises((KeyError, ValueError)):
        await service.get_sorted_holidays(fake_guild)
