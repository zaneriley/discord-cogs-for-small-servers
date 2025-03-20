"""
Debug script for testing the holiday repository.

Run this script from the root directory:
python -m cogs.seasonalroles.debug
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("holiday_debug")

# Ensure we can import from parent directory
sys.path.append(os.getcwd())

from cogs.seasonalroles.holiday.holiday_repository import JsonHolidayRepository

async def main():
    # Initialize repository
    logger.info("Initializing JsonHolidayRepository")
    repo = JsonHolidayRepository()

    # Get raw data from _load_holidays_data
    logger.info("Loading raw data")
    raw_data = repo._load_holidays_data()
    logger.info(f"Raw data keys: {list(raw_data.keys())}")

    # Check if 'holidays' key exists
    if "holidays" in raw_data:
        logger.info(f"'holidays' key exists with {len(raw_data['holidays'])} entries")
        logger.info(f"Holiday names: {list(raw_data['holidays'].keys())}")
    else:
        logger.error("'holidays' key not found in raw data!")

    # Test get_holidays method
    logger.info("Testing get_holidays method")
    holidays = await repo.get_holidays(None)
    logger.info(f"get_holidays returned {len(holidays)} holidays")
    logger.info(f"Holiday names from get_holidays: {list(holidays.keys())}")

    # Print first holiday details
    if holidays:
        first_holiday = next(iter(holidays.keys()))
        logger.info(f"First holiday details: {json.dumps(holidays[first_holiday], indent=2)}")

    logger.info("Debug complete")

if __name__ == "__main__":
    asyncio.run(main()) 