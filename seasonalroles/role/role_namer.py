"""Pure functions for generating role names in a consistent format."""


def generate_role_name(holiday_name: str, date: str) -> str:
    """
    Generate a role name by combining the holiday name and date.

    Args:
        holiday_name (str): The name of the holiday (e.g., "Kids Day")
        date (str): The date in MM-DD format (e.g., "05-05")

    Returns:
        str: The formatted role name (e.g., "Kids Day 05-05")

    Examples:
        >>> generate_role_name("Kids Day", "05-05")
        'Kids Day 05-05'
        >>> generate_role_name("New Year's Celebration", "01-01")
        "New Year's Celebration 01-01"

    """
    return f"{holiday_name} {date}"
