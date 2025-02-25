from abc import ABC, abstractmethod


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


class ConfigHolidayRepository(HolidayRepository):
    def __init__(self, config):
        self.config = config

    async def get_holidays(self, guild) -> dict:
        return await self.config.guild(guild).holidays()

    async def set_holidays(self, guild, holidays: dict):
        await self.config.guild(guild).holidays.set(holidays)

    async def add_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        holidays = await self.get_holidays(guild)
        if name in holidays:
            return False
        holidays[name] = holiday_data
        await self.set_holidays(guild, holidays)
        return True

    async def update_holiday(self, guild, name: str, holiday_data: dict) -> bool:
        holidays = await self.get_holidays(guild)
        if name not in holidays:
            return False
        holidays[name].update(holiday_data)
        await self.set_holidays(guild, holidays)
        return True

    async def remove_holiday(self, guild, name: str) -> bool:
        holidays = await self.get_holidays(guild)
        if name not in holidays:
            return False
        del holidays[name]
        await self.set_holidays(guild, holidays)
        return True
