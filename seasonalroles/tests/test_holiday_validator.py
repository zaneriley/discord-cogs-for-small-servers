"""Tests for holiday validation functions."""

from cogs.seasonalroles.holiday.holiday_validator import (
    find_holiday,
    validate_color,
    validate_date_format,
    validate_holiday_name,
)


def test_validate_color():
    """Test color validation."""
    assert validate_color("#FF0000") is True
    assert validate_color("#00FF00") is True
    assert validate_color("#0000FF") is True
    assert validate_color("#FF000") is False  # Missing digit
    assert validate_color("FF0000") is False  # Missing #
    assert validate_color("#FF000G") is False  # Invalid hex digit
    assert validate_color(None) is False
    assert validate_color("") is False


def test_validate_date_format():
    """Test date format validation."""
    assert validate_date_format("01-01") is True
    assert validate_date_format("12-31") is True
    assert validate_date_format("02-29") is True  # Leap year
    assert validate_date_format("13-01") is False  # Invalid month
    assert validate_date_format("01-32") is False  # Invalid day
    assert validate_date_format("02-30") is False  # Invalid day for February
    assert validate_date_format("01-1") is False  # Missing leading zero
    assert validate_date_format("1-01") is False  # Missing leading zero
    assert validate_date_format("1-1") is False  # Missing leading zeros
    assert validate_date_format(None) is False
    assert validate_date_format("") is False


def test_validate_holiday_name():
    """Test holiday name validation."""
    assert validate_holiday_name("Christmas") is True
    assert validate_holiday_name("New Year's Day") is True
    assert validate_holiday_name(" ") is False  # Only whitespace
    assert validate_holiday_name("") is False  # Empty string
    assert validate_holiday_name(None) is False
    assert validate_holiday_name("  Christmas  ") is True  # Leading/trailing whitespace is allowed


def test_find_holiday():
    """Test holiday lookup with confidence scoring."""
    holidays = {
        "Christmas": {"date": "12-25", "color": "#FF0000"},
        "New Year's Day": {"date": "01-01", "color": "#00FF00"},
        "Halloween": {"date": "10-31", "color": "#0000FF"}
    }

    # Test exact match
    name, details, score = find_holiday(holidays, "Christmas")
    assert name == "Christmas"
    assert details == holidays["Christmas"]
    assert score == 1.0

    # Test case-insensitive match
    name, details, score = find_holiday(holidays, "christmas")
    assert name == "Christmas"
    assert details == holidays["Christmas"]
    assert score == 1.0

    # Test partial match
    name, details, score = find_holiday(holidays, "New")
    assert name == "New Year's Day"
    assert details == holidays["New Year's Day"]
    assert score < 1.0  # Partial match should have lower confidence

    # Test no match
    name, details, score = find_holiday(holidays, "Non Existent")
    assert name is None
    assert details is None
    assert score is None

    # Test with display names
    holidays_with_display = {
        "Christmas": {"date": "12-25", "color": "#FF0000", "display_name": "Christmas Day"},
        "New Year's Day": {"date": "01-01", "color": "#00FF00", "display_name": "New Year"},
        "Halloween": {"date": "10-31", "color": "#0000FF", "display_name": "Halloween Night"}
    }

    # Test exact match with display name
    name, details, score = find_holiday(holidays_with_display, "Christmas Day")
    assert name == "Christmas"
    assert details == holidays_with_display["Christmas"]
    assert score == 1.0

    # Test partial match with display name
    name, details, score = find_holiday(holidays_with_display, "New")
    assert name == "New Year's Day"
    assert details == holidays_with_display["New Year's Day"]
    assert score < 1.0  # Partial match should have lower confidence
