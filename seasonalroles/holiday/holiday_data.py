"""
Holiday data model for the SeasonalRoles cog.

This module defines the Holiday class used for representing holidays
within the SeasonalRoles cog, particularly for the announcement system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Holiday:

    """
    Represents a holiday with all necessary attributes for the SeasonalRoles cog.

    This class is used throughout the holiday announcement system to represent
    holiday data in a consistent way.

    Attributes:
        name: The name of the holiday
        month: The month of the holiday (1-12)
        day: The day of the month for the holiday
        color: The color associated with the holiday (hex string)
        image: Optional URL to an image representing the holiday
        banner_url: Optional URL to a banner image for the holiday

    """

    name: str
    month: int
    day: int
    color: str
    image: str | None = None
    banner_url: str | None = None

    def __post_init__(self):
        """Validate the holiday data after initialization."""
        # Check that month is valid (1-12)
        if not isinstance(self.month, int) or self.month < 1 or self.month > 12:
            msg = f"Month must be an integer between 1 and 12, got {self.month} ({type(self.month).__name__})"
            raise ValueError(msg)

        # Check that day is valid for the given month
        max_days = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # Including leap year Feb
        if not isinstance(self.day, int) or self.day < 1 or self.day > max_days[self.month]:
            msg = f"Day must be an integer between 1 and {max_days[self.month]} for month {self.month}, got {self.day}"
            raise ValueError(msg)

        # Check that color is a valid hex color
        if not isinstance(self.color, str) or not self.color.startswith("#") or len(self.color) != 7:
            msg = f"Color must be a valid hex color string (e.g., '#FF0000'), got {self.color}"
            raise ValueError(msg)

    def __str__(self) -> str:
        """Return a human-readable string representation of the holiday"""
        return f"{self.name} ({self.month}/{self.day})"
