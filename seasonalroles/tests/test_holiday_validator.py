"""Tests for holiday validation functions."""

from cogs.seasonalroles.holiday.holiday_validator import (
    find_holiday,
    validate_color,
    validate_date_format,
    validate_holiday_name,
)


def test_validate_color():
    """Test hex color validation."""
    # Valid colors
    assert validate_color("#FF0000") is True  # Red
    assert validate_color("#00FF00") is True  # Green
    assert validate_color("#0000FF") is True  # Blue
    assert validate_color("#123456") is True  # Random valid color

    # Invalid colors
    assert validate_color("FF0000") is False  # Missing #
    assert validate_color("#FF00") is False  # Too short
    assert validate_color("#FF000000") is False  # Too long
    assert validate_color("#GGGGGG") is False  # Invalid characters
    assert validate_color("") is False  # Empty string
    assert validate_color("#12345") is False  # 6 chars including #
    assert validate_color(None) is False  # None value


def test_validate_date_format():
    """Test date string format validation."""
    # Valid dates
    assert validate_date_format("01-01") is True  # January 1st
    assert validate_date_format("12-31") is True  # December 31st
    assert validate_date_format("02-29") is True  # February 29th (leap year)

    # Invalid dates
    assert validate_date_format("1-1") is False  # Missing leading zeros
    assert validate_date_format("13-01") is False  # Invalid month
    assert validate_date_format("12-32") is False  # Invalid day
    assert validate_date_format("00-00") is False  # Invalid month and day
    assert validate_date_format("12/25") is False  # Wrong separator
    assert validate_date_format("2024-12-25") is False  # Full date not allowed
    assert validate_date_format("") is False  # Empty string
    assert validate_date_format(None) is False  # None value


def test_validate_holiday_name():
    """Test holiday name validation."""
    # Valid names
    assert validate_holiday_name("Christmas") is True
    assert validate_holiday_name("New Year's Day") is True
    assert validate_holiday_name("Kids' Day") is True
    assert validate_holiday_name("Spring Festival 2024") is True

    # Invalid names
    assert validate_holiday_name("") is False  # Empty string
    assert validate_holiday_name(" ") is False  # Just whitespace
    assert validate_holiday_name("\t") is False  # Tab character
    assert validate_holiday_name("\n") is False  # Newline
    assert validate_holiday_name(None) is False  # None value


def test_find_holiday():
    """Test case-insensitive holiday lookup."""
    holidays = {
        "Kids Day": {"date": "05-05", "color": "#FF0000"},
        "Christmas": {"date": "12-25", "color": "#00FF00"},
        "New Year's Day": {"date": "01-01", "color": "#0000FF"},
    }

    # Test exact matches
    assert find_holiday(holidays, "Kids Day") == ("Kids Day", holidays["Kids Day"])
    assert find_holiday(holidays, "Christmas") == ("Christmas", holidays["Christmas"])

    # Test case-insensitive matches
    assert find_holiday(holidays, "kids day") == ("Kids Day", holidays["Kids Day"])
    assert find_holiday(holidays, "CHRISTMAS") == ("Christmas", holidays["Christmas"])
    assert find_holiday(holidays, "new year's day") == (
        "New Year's Day",
        holidays["New Year's Day"],
    )

    # Test non-existent holidays
    assert find_holiday(holidays, "Easter") == (None, None)
    assert find_holiday(holidays, "") == (None, None)
    assert find_holiday(holidays, None) == (None, None)

    # Test with empty holiday dict
    assert find_holiday({}, "Christmas") == (None, None)
