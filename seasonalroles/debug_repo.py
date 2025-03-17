"""
Debug script for testing the holiday repository directly.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("holiday_debug")

class JsonHolidayRepositoryTester:
    """Test version of JsonHolidayRepository for debugging."""

    def __init__(self):
        """Initialize with direct file access."""
        self.data = self._load_data()

    def _load_data(self):
        """Load data directly from holidays.json."""
        try:
            # First try to load from the cog folder
            holidays_file = Path("cogs/seasonalroles/holidays.json")

            # Check if the file exists
            if not holidays_file.exists():
                logger.warning("holidays.json not found!")
                return {}

            with open(holidays_file, "r") as f:
                logger.info(f"Loading holidays data from {holidays_file}")
                data = json.load(f)
                return data
        except Exception:
            logger.exception("Error loading holidays.json")
            return {}

    async def get_holidays(self, _):
        """Get all holidays from the data."""
        # Get holidays from the data dictionary
        holidays = self.data.get("holidays", {})
        logger.info(f"Returning {len(holidays)} holidays")

        # If no holidays in expected format but data looks like direct holidays
        if not holidays and self.data and isinstance(self.data, dict):
            # Check if keys look like holiday names
            if any(key.endswith(("Day", "Festival", "Celebration")) for key in self.data.keys()):
                logger.warning("Data appears to be directly structured as holidays")
                return self.data

        return holidays

async def main():
    """Run tests on the repository."""
    # Initialize tester
    logger.info("Initializing JsonHolidayRepositoryTester")
    repo = JsonHolidayRepositoryTester()

    # Get raw data
    logger.info("Raw data loaded")
    raw_data = repo.data
    logger.info(f"Raw data keys: {list(raw_data.keys())}")

    # Check if 'holidays' key exists
    if "holidays" in raw_data:
        logger.info(f"'holidays' key exists with {len(raw_data['holidays'])} entries")
        logger.info(f"Holiday names: {list(raw_data['holidays'].keys())[:5]}")
    else:
        logger.error("'holidays' key not found in raw data!")

    # Test get_holidays method
    logger.info("Testing get_holidays method")
    holidays = await repo.get_holidays(None)
    logger.info(f"get_holidays returned {len(holidays)} holidays")

    if holidays:
        logger.info(f"First 5 holiday names: {list(holidays.keys())[:5]}")
        # Print first holiday details
        first_holiday = next(iter(holidays.keys()))
        logger.info(f"First holiday details: {json.dumps(holidays[first_holiday], indent=2)}")
    else:
        logger.error("No holidays returned from get_holidays!")

    logger.info("Debug complete")

if __name__ == "__main__":
    asyncio.run(main()) 