import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class HolidayRepository(ABC):
    @abstractmethod
    async def get_holidays(self, guild) -> dict:
        pass

    @abstractmethod
    async def add_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        pass

    @abstractmethod
    async def update_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        pass

    @abstractmethod
    async def remove_holiday(self, guild, name: str) -> bool:
        pass


class JsonHolidayRepository(HolidayRepository):

    """Repository implementation that reads from and writes to holidays.json"""

    def __init__(self):
        self.data = self._load_holidays_data()

    def _load_holidays_data(self) -> dict:
        """
        Load holiday data from holidays.json.

        Returns:
            Dictionary containing holiday data

        """
        # First try to load from the root of the cog folder
        cog_dir = Path(__file__).parent.parent
        holidays_file = cog_dir / "holidays.json"

        logger.info(f"Looking for holidays.json at: {holidays_file} (exists: {holidays_file.exists()})")

        # Check if the file exists
        if not holidays_file.exists():
            logger.warning("holidays.json not found in cog directory, checking data directory...")
            # Fall back to data directory
            data_dir = cog_dir / "data"
            data_dir.mkdir(exist_ok=True)
            holidays_file = data_dir / "holidays.json"
            logger.info(f"Looking in data directory: {holidays_file} (exists: {holidays_file.exists()})")

            if not holidays_file.exists():
                logger.warning("holidays.json not found in data directory, creating empty file")
                # Create an empty holidays json file
                with holidays_file.open("w") as f:
                    json.dump({"holidays": {}}, f, indent=4)
                logger.info(f"Created new empty holidays.json at {holidays_file}")

        try:
            with holidays_file.open("r") as f:
                logger.info(f"Loading holidays data from {holidays_file}")
                data = json.load(f)

                # Log file stats and content summary
                file_size = holidays_file.stat().st_size
                logger.info(f"File size: {file_size} bytes")
                logger.info(f"Data keys: {list(data.keys())}")

                # Check if data is in the expected format with a "holidays" top-level key
                if "holidays" not in data:
                    logger.warning(f"'holidays' key not found in data. Available keys: {list(data.keys())}")
                    # If the data appears to be a direct dictionary of holidays, 
                    # wrap it in the expected structure
                    if data and isinstance(data, dict) and any(key.endswith(("Day", "Festival", "Celebration")) for key in data.keys()):
                        logger.warning("holidays.json is not in the expected format. Wrapping data with 'holidays' key.")
                        # Create the proper structure
                        wrapped_data = {"holidays": data}

                        # Save the updated structure back to the file
                        with holidays_file.open("w") as write_f:
                            json.dump(wrapped_data, write_f, indent=4)
                            logger.info("Updated holidays.json to use the expected structure")

                        return wrapped_data
                else:
                    holidays = data.get("holidays", {})
                    logger.info(f"Found {len(holidays)} holidays under 'holidays' key")

                return data
        except json.JSONDecodeError:
            logger.exception("Error parsing holidays.json")
            try:
                # Read raw content to help diagnose JSON issues
                with holidays_file.open("r") as f:
                    content = f.read(200)  # First 200 chars
                    logger.error(f"First 200 chars of file: {content}")
            except Exception:
                logger.exception("Could not read raw file content")
            return {"holidays": {}}
        except OSError:
            logger.exception("Error loading holidays.json")
            return {"holidays": {}}

    def _save_holidays_data(self) -> bool:
        """
        Save holiday data to holidays.json.

        Returns:
            True if successful, False otherwise

        """
        cog_dir = Path(__file__).parent.parent
        holidays_file = cog_dir / "holidays.json"

        try:
            with holidays_file.open("w") as f:
                json.dump(self.data, f, indent=4)
                return True
        except OSError:
            logger.exception(f"Error saving to {holidays_file}")
            return False

    async def get_holidays(self, _guild) -> dict:
        """Get all holidays from holidays.json"""
        # Log the current state of the repository
        logger.info(f"JsonHolidayRepository.get_holidays called, current state: data={bool(self.data)}")

        # Reload data to make sure we have the latest
        prev_data = self.data
        self.data = self._load_holidays_data()

        # Check if data has changed
        if id(prev_data) != id(self.data):
            logger.info("Data was reloaded from file")
        else:
            logger.info("Using existing data (not reloaded)")

        # Log the loaded data structure    
        logger.info(f"Data keys: {list(self.data.keys() if self.data else [])}")

        holidays = self.data.get("holidays", {})
        logger.info(f"JsonHolidayRepository returning holidays: {holidays}")

        # If no holidays are in the expected structure, try using the file content directly
        if not holidays:
            logger.warning("No holidays found in expected format. Raw data structure: %s", self.data)
            # Check if the data might be directly structured as holidays
            if self.data and isinstance(self.data, dict) and any(key.endswith(("Day", "Festival", "Celebration")) for key in self.data.keys()):
                logger.info("Data appears to be directly structured as holidays, using as-is")
                return self.data
            logger.error("No holidays found in any format")
        return holidays

    async def add_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        """Add a holiday to holidays.json"""
        holidays = await self.get_holidays(guild)

        if name in holidays:
            return False

        holidays[name] = holiday_data
        self.data["holidays"] = holidays
        return self._save_holidays_data()

    async def update_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        """Update a holiday in holidays.json"""
        holidays = await self.get_holidays(guild)

        if name not in holidays:
            return False

        holidays[name].update(holiday_data)
        self.data["holidays"] = holidays
        return self._save_holidays_data()

    async def remove_holiday(self, guild, name: str) -> bool:
        """Remove a holiday from holidays.json"""
        holidays = await self.get_holidays(guild)

        if name not in holidays:
            return False

        del holidays[name]
        self.data["holidays"] = holidays
        return self._save_holidays_data()

    async def save_holidays(self) -> bool:
        """Public method to save holiday data"""
        return self._save_holidays_data()


class ConfigHolidayRepository(HolidayRepository):

    """
    Legacy repository that bridges between Config and the new JsonHolidayRepository.

    This maintains backward compatibility while delegating operations to holidays.json.
    """

    def __init__(self, config):
        self.config = config
        self.json_repo = JsonHolidayRepository()

    async def get_holidays(self, guild) -> dict:
        """Get holidays from holidays.json"""
        logger.info(f"ConfigHolidayRepository.get_holidays called for guild: {guild.id} - {guild.name}")
        holidays = await self.json_repo.get_holidays(guild)
        logger.info(f"ConfigHolidayRepository received holidays from JsonHolidayRepository: {holidays}")
        return holidays

    async def set_holidays(self, _guild, holidays: dict):
        """Set holidays in holidays.json"""
        # This is a custom method used in migration
        self.json_repo.data["holidays"] = holidays
        # Use the public method for saving data
        await self.json_repo.save_holidays()

    async def add_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        """Add holiday to holidays.json"""
        return await self.json_repo.add_holiday(guild, name, holiday_data)

    async def update_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        """Update holiday in holidays.json"""
        return await self.json_repo.update_holiday(guild, name, holiday_data)

    async def remove_holiday(self, guild, name: str) -> bool:
        """Remove holiday from holidays.json"""
        return await self.json_repo.remove_holiday(guild, name)
