"""Tests for role name generation functionality."""

from cogs.seasonalroles.role.role_namer import generate_role_name


def test_generate_role_name():
    """Test that role names are generated correctly."""
    test_cases = [
        ("TestHoliday", "05-05", "TestHoliday 05-05"),
        ("Kids Day", "05-05", "Kids Day 05-05"),
        ("New Year's Day", "01-01", "New Year's Day 01-01"),
    ]

    for holiday_name, date, expected in test_cases:
        assert generate_role_name(holiday_name, date) == expected


def test_generate_role_name_edge_cases():
    """Test edge cases for role name generation."""
    # Test with extra whitespace in holiday name
    assert generate_role_name("Test  Holiday  ", "05-05") == "Test  Holiday   05-05"

    # Test with special characters
    assert generate_role_name("New Year's Day!", "01-01") == "New Year's Day! 01-01"

    # Test with empty inputs
    assert generate_role_name("", "05-05") == " 05-05"
    assert generate_role_name("Holiday", "") == "Holiday "
