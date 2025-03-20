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
) -> tuple[str | None, dict[str, Any] | None, float | None]:
    """
    Find a holiday by name using intelligent matching strategies.

    Args:
        holidays: Dictionary mapping holiday names to their details
        name: The search term to find matching holidays

    Returns:
        Tuple containing:
        - The original holiday name if found (preserving original case), or None if not found
        - The holiday details dictionary if found, or None if not found
        - Match confidence score (1.0 = exact match, lower values for partial matches), or None if not found

    Matching strategies (in order of priority):
    1. Exact match (case insensitive) with main name
    2. Exact match (case insensitive) with display_name
    3. Contains match with main name or display_name
    4. Word-by-word partial match with main name or display_name

    """
    if not name or not holidays:
        return None, None, None

    name = name.lower().strip()

    # Track best match
    best_match_name = None
    best_match_details = None
    best_score = 0.0

    for holiday_name, details in holidays.items():
        # Strategy 1: Exact match with holiday_name (highest priority)
        if holiday_name.lower() == name:
            return holiday_name, details, 1.0

        # Strategy 2: Exact match with display_name if available
        display_name = details.get("display_name", "").lower()
        if display_name and display_name == name:
            return holiday_name, details, 1.0

        # Strategy 3: Contains match with holiday_name
        if name in holiday_name.lower():
            # Score based on how much of the holiday name is matched
            score = len(name) / len(holiday_name.lower()) * 0.9  # 0.9 max for contains
            if score > best_score:
                best_score = score
                best_match_name = holiday_name
                best_match_details = details

        # Strategy 4: Contains match with display_name
        if display_name and name in display_name:
            score = len(name) / len(display_name) * 0.85  # 0.85 max for display_name contains
            if score > best_score:
                best_score = score
                best_match_name = holiday_name
                best_match_details = details

        # Strategy 5: Word-by-word match with holiday_name
        for word in holiday_name.lower().split():
            if name in word:
                score = len(name) / len(word) * 0.8  # 0.8 max for word match
                if score > best_score:
                    best_score = score
                    best_match_name = holiday_name
                    best_match_details = details

            # Also check if word is in name (allowing for partial word search)
            if word in name:
                score = len(word) / len(name) * 0.7  # 0.7 max for word in search
                if score > best_score:
                    best_score = score
                    best_match_name = holiday_name
                    best_match_details = details

        # Strategy 6: Word-by-word match with display_name
        for word in display_name.split() if display_name else []:
            if name in word:
                score = len(name) / len(word) * 0.75  # 0.75 max for display_name word match
                if score > best_score:
                    best_score = score
                    best_match_name = holiday_name
                    best_match_details = details

    if best_match_name:
        return best_match_name, best_match_details, best_score

    return None, None, None


def find_holiday_matches(
    holidays: dict[str, dict[str, Any]], name: str | None, threshold: float = 0.5
) -> list[tuple[str, dict[str, Any], float]]:
    """
    Find multiple holiday matches for a search term, ranked by confidence score.

    This function is useful for providing options when a partial match is ambiguous.

    Args:
        holidays: Dictionary mapping holiday names to their details
        name: The search term to find matching holidays
        threshold: Minimum confidence score to include in results (0.0 to 1.0)

    Returns:
        List of tuples containing:
        - The original holiday name
        - The holiday details dictionary
        - Match confidence score

    Results are sorted by confidence score in descending order (best matches first).

    """
    if not name or not holidays:
        return []

    name = name.lower().strip()
    matches = []

    for holiday_name, details in holidays.items():
        # Exact match with holiday_name
        if holiday_name.lower() == name:
            matches.append((holiday_name, details, 1.0))
            continue

        # Exact match with display_name if available
        display_name = details.get("display_name", "").lower()
        if display_name and display_name == name:
            matches.append((holiday_name, details, 1.0))
            continue

        score = 0.0

        # Contains match with holiday_name
        if name in holiday_name.lower():
            # Score based on how much of the holiday name is matched
            score = max(score, len(name) / len(holiday_name.lower()) * 0.9)

        # Contains match with display_name
        if display_name and name in display_name:
            score = max(score, len(name) / len(display_name) * 0.85)

        # Word-by-word match with holiday_name
        for word in holiday_name.lower().split():
            if name in word:
                score = max(score, len(name) / len(word) * 0.8)
            # Also check if word is in search term
            if word in name:
                score = max(score, len(word) / len(name) * 0.7)

        # Word-by-word match with display_name
        for word in display_name.split() if display_name else []:
            if name in word:
                score = max(score, len(name) / len(word) * 0.75)

        # Include the match if score is above threshold
        if score >= threshold:
            matches.append((holiday_name, details, score))

    # Sort by score in descending order
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches
