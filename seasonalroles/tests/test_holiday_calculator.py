# pylint: disable=no-assert

from datetime import date

import pytest
from cogs.seasonalroles.holiday.holiday_calculator import (
    compute_days_until_holiday,
    find_upcoming_holiday,
    get_sorted_holidays,
)


def test_compute_days_until_holiday():
    # Test with a fixed current date
    current_date = date(2024, 1, 1)  # January 1st, 2024

    # Test upcoming holiday
    assert (
        compute_days_until_holiday("01-05", current_date) == 4
    )  # Jan 5th is 4 days away

    # Test holiday that just passed
    assert (
        compute_days_until_holiday("12-25", current_date) == 359
    )  # Dec 25th is 359 days away (next year)

    # Test same day
    assert compute_days_until_holiday("01-01", current_date) == 0

    # Test invalid date format
    with pytest.raises(ValueError):
        compute_days_until_holiday("invalid-date", current_date)


def test_find_upcoming_holiday():
    current_date = date(2024, 1, 1)  # January 1st, 2024

    # Test with multiple holidays
    holidays = {
        "New Year": {"date": "01-01"},  # Today
        "Kids Day": {"date": "05-05"},  # Future
        "Christmas": {"date": "12-25"},  # Past (next year)
    }

    upcoming, days_until = find_upcoming_holiday(holidays, current_date)

    # Kids Day should be next upcoming
    assert upcoming == "Kids Day"

    # Verify days until each holiday
    assert days_until == {
        "New Year": 0,
        "Kids Day": 125,  # Days until May 5th
        "Christmas": 359,  # Days until next Christmas
    }

    # Test with empty holidays
    upcoming, days_until = find_upcoming_holiday({}, current_date)
    assert upcoming is None
    assert days_until == {}


def test_get_sorted_holidays():
    current_date = date(2024, 1, 1)  # January 1st, 2024

    # Test with multiple holidays
    holidays = {
        "New Year": {"date": "01-01"},  # Today
        "Valentine's": {"date": "02-14"},  # Future (soon)
        "Kids Day": {"date": "05-05"},  # Future (later)
        "Christmas": {"date": "12-25"},  # Past (next year)
    }

    sorted_holidays = get_sorted_holidays(holidays, current_date)

    # Verify order: future holidays first (by closest), then past/today
    assert sorted_holidays == [
        ("Valentine's", 44),  # Closest future
        ("Kids Day", 125),  # Next future
        ("Christmas", 359),  # Last future
        ("New Year", 0),  # Today (counts as past)
    ]

    # Test with empty holidays
    assert get_sorted_holidays({}, current_date) == []
