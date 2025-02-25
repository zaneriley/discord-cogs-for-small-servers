"""Holiday validation functions."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Constants for magic numbers
MAX_MONTH = 12


def validate_color(color: str | None) -> bool:
    """
    Validate a hex color string.

    Args:
        color: The color string to validate (e.g., "#FF0000")

    Returns:
        True if the color is a valid hex color (starts with # and has exactly 6 hex digits),
        False otherwise.

    """
    if not color:
        return False

    # Check format: # followed by exactly 6 hex digits
    hex_pattern = r"^#[0-9A-Fa-f]{6}$"
    return bool(re.match(hex_pattern, color))


def validate_date_format(date_str: str | None) -> bool:
    """
    Validate that date_str is in MM-DD format.

    Args:
    ----
        date_str: The date string to validate.

    Returns:
    -------
        bool: True if the date is valid, False otherwise.

    """
    if not date_str:
        return False

    # Check basic format with regex
    if not re.match(r"^\d{2}-\d{2}$", date_str):
        return False

    try:
        # Try to parse as a date (using a leap year to allow Feb 29)
        datetime.strptime(f"2024-{date_str}", "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Extract month and day and verify they're in valid ranges
        month, day = map(int, date_str.split("-"))
        if month < 1 or month > MAX_MONTH:
            return False

        # Check days per month (including leap year February)
        days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return 1 <= day <= days_in_month[month]

    except ValueError:
        return False


def validate_holiday_name(name: str | None) -> bool:
    """
    Validate a holiday name.

    Args:
        name: The holiday name to validate

    Returns:
        True if the name is non-empty and contains non-whitespace characters,
        False otherwise.

    """
    if not name:
        return False

    # Check if string contains any non-whitespace characters
    return bool(name.strip())


def find_holiday(
    holidays: dict[str, dict[str, Any]], name: str | None
) -> tuple[str | None, dict[str, Any] | None]:
    """
    Find a holiday by name using case-insensitive matching.

    Args:
        holidays: Dictionary mapping holiday names to their details
        name: The name of the holiday to find

    Returns:
        Tuple containing:
        - The original holiday name if found (preserving original case), or None if not found
        - The holiday details dictionary if found, or None if not found

    """
    if not name or not holidays:
        return None, None

    # Create case-insensitive lookup dictionary
    lookup = {k.lower(): (k, v) for k, v in holidays.items()}

    # Try to find the holiday
    found = lookup.get(name.lower())
    if found:
        return found  # Returns (original_name, details)

    return None, None
