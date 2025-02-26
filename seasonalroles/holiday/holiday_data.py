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

    def __str__(self) -> str:
        """Return a human-readable string representation of the holiday"""
        return f"{self.name} ({self.month}/{self.day})"
