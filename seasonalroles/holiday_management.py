import discord
from utilities.date_utils import DateUtil

class HolidayService:
    def __init__(self, config):
        self.config = config

    async def add_holiday(self, guild, name, date, color, image=None, banner_url=None):
        holidays = await self.config.guild(guild).holidays()
        if holidays.get(name):
            return False, f"Holiday {name} already exists!"

        holidays[name] = {"date": date, "color": color}
        if image:
            holidays[name]["image"] = image
        if banner_url:
            holidays[name]["banner"] = banner_url

        await self.config.guild(guild).holidays.set(holidays)
        return True, f"Holiday {name} added successfully!"

    async def remove_holiday(self, guild, name):
        holidays = await self.config.guild(guild).holidays()
        if not holidays.get(name):
            return False, f"Holiday {name} does not exist!"

        del holidays[name]
        await self.config.guild(guild).holidays.set(holidays)
        return True, f"Holiday {name} has been removed successfully!"
    
    async def edit_holiday(self, guild, name, new_date, new_color, new_image=None, new_banner_url=None):
        holidays = await self.config.guild(guild).holidays()
        if not holidays.get(name):
            return False, f"Holiday {name} does not exist!"

        # Update the holiday details
        holidays[name]['date'] = new_date
        holidays[name]['color'] = new_color
        if new_image:
            holidays[name]['image'] = new_image
        if new_banner_url:
            holidays[name]['banner'] = new_banner_url

        await self.config.guild(guild).holidays.set(holidays)
        return True, f"Holiday {name} has been updated successfully!"
    
    async def get_sorted_holidays(self, guild):
        holidays = await self.config.guild(guild).holidays()
        if not holidays:
            return None, "No holidays have been configured."

        upcoming_holiday, days_until = self.find_upcoming_holiday(holidays)
        future_holidays = {name: days for name, days in days_until.items() if days > 0}
        past_holidays = {name: days for name, days in days_until.items() if days <= 0}

        sorted_future_holidays = sorted(future_holidays.items(), key=lambda x: x[1])
        sorted_past_holidays = sorted(past_holidays.items(), key=lambda x: x[1], reverse=True)

        sorted_holidays = sorted_future_holidays + sorted_past_holidays
        return sorted_holidays, upcoming_holiday, days_until

    def find_upcoming_holiday(self, holidays):
        # Logic to find the upcoming holiday
        current_date = DateUtil.now()
        upcoming_holiday = None
        min_days_diff = float('inf')
        days_until = {}

        for name, details in holidays.items():
            holiday_date_str = f"{current_date.year}-{details['date']}"
            holiday_date = DateUtil.str_to_date(holiday_date_str, "%Y-%m-%d")
            
            days_diff = (holiday_date - current_date).days
            days_until[name] = days_diff

            if days_diff > 0 and days_diff < min_days_diff:
                min_days_diff = days_diff
                upcoming_holiday = name

        return upcoming_holiday, days_until