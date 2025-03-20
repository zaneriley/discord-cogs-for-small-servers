"""Tests for HolidayService business logic."""

import datetime
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cogs.seasonalroles.holiday_management import HolidayData, HolidayService

###############################################################################
# Test Fixtures and Helpers
###############################################################################


class FakeDateUtil:
    @staticmethod
    def now():
        # Fixed current date for testing: May 1, 2023
        return datetime.datetime(2023, 5, 1, tzinfo=timezone.utc)


class FakeHoliday:

    """Simulate the 'holidays' property on a guild config."""

    def __init__(self, holidays):
        self._holidays = holidays

    async def __call__(self):
        return self._holidays

    async def set(self, new_holidays):
        self._holidays = new_holidays


class FakeGuildConfig:

    """Simulate a guild-specific configuration object."""

    def __init__(self, holidays):
        self.holidays = FakeHoliday(holidays)


class FakeConfig:

    """Simulate a config adapter that returns guild configurations."""

    def __init__(self, holidays):
        self._holidays = holidays

    def guild(self, guild):
        return FakeGuildConfig(self._holidays)


class FakeGuild:

    """Minimal fake guild object with a name property."""

    name = "FakeGuild"


@pytest.fixture(autouse=True)
def patch_date_util(monkeypatch):
    monkeypatch.setattr("utilities.date_utils.DateUtil.now", FakeDateUtil.now)


###############################################################################
# Tests for Holiday Validation and Existence Check
###############################################################################


@pytest.fixture
def mock_holidays():
    """Create mock holiday data."""
    return {
        "HolidayA": {"date": "05-05", "color": "#AAA111"},
        "HolidayB": {"date": "04-30", "color": "#BBB222"},
        "HolidayC": {"date": "06-10", "color": "#CCC333"}
    }


@pytest.fixture
def mock_config():
    """Create a mock config."""
    return MagicMock()


@pytest.fixture
def mock_repository():
    """Create a mock repository with async methods."""
    repository = MagicMock()
    repository.get_holidays = AsyncMock()
    repository.add_holiday = AsyncMock()
    repository.remove_holiday = AsyncMock()
    repository.update_holiday = AsyncMock()
    return repository


@pytest.fixture
def mock_role_manager():
    """Create a mock role manager for testing."""
    return MagicMock()


@pytest.mark.asyncio
async def test_validate_holiday_exists_found(mock_config, mock_repository, mock_holidays):
    """Test validating an existing holiday."""
    mock_repository.get_holidays.return_value = mock_holidays
    service = HolidayService(config=mock_config, repository=mock_repository)
    exists, message = await service.validate_holiday_exists(mock_holidays, "HolidayA")
    assert exists is True
    assert message is None


@pytest.mark.asyncio
async def test_validate_holiday_exists_edge_cases(mock_config, mock_repository, mock_holidays):
    """Test edge cases for holiday validation."""
    mock_repository.get_holidays.return_value = mock_holidays
    service = HolidayService(config=mock_config, repository=mock_repository)

    # Test with extra whitespace
    exists, message = await service.validate_holiday_exists(mock_holidays, "  HolidayA  ")
    assert exists is True
    assert message is None

    # Test with partial match
    exists, message = await service.validate_holiday_exists(mock_holidays, "Holiday")
    assert exists is True
    assert message is None

    # Test with empty name
    exists, message = await service.validate_holiday_exists(mock_holidays, "")
    assert exists is False
    assert "Holiday name cannot be empty" in message


@pytest.mark.asyncio
async def test_validate_holiday_exists_not_found(mock_config, mock_repository, mock_holidays):
    """Test validating a non-existent holiday."""
    mock_repository.get_holidays.return_value = mock_holidays
    service = HolidayService(config=mock_config, repository=mock_repository)
    exists, message = await service.validate_holiday_exists(mock_holidays, "NonexistentHoliday")
    assert exists is False
    assert "No holiday found matching" in message


###############################################################################
# Tests for Holiday Sorting
###############################################################################


@pytest.mark.asyncio
async def test_get_sorted_holidays(mock_config, mock_repository, mock_holidays):
    """Test holiday sorting business logic."""
    mock_repository.get_holidays.return_value = mock_holidays
    service = HolidayService(config=mock_config, repository=mock_repository)

    with patch("cogs.seasonalroles.holiday_management.DateUtil.now") as mock_now:
        mock_now.return_value = datetime.datetime(2023, 5, 1, tzinfo=timezone.utc)
        sorted_holidays, upcoming_holiday, days_until = await service.get_sorted_holidays(MagicMock())
        assert sorted_holidays is not None
        assert upcoming_holiday == "HolidayA"
        assert days_until["HolidayA"] == 4


@pytest.mark.asyncio
async def test_get_sorted_holidays_edge_cases(mock_config, mock_repository, mock_holidays):
    """Test edge cases for holiday sorting."""
    mock_repository.get_holidays.return_value = mock_holidays
    service = HolidayService(config=mock_config, repository=mock_repository)

    with patch("cogs.seasonalroles.holiday_management.DateUtil.now") as mock_now:
        mock_now.return_value = datetime.datetime(2023, 5, 1, tzinfo=timezone.utc)
        sorted_holidays, upcoming_holiday, days_until = await service.get_sorted_holidays(MagicMock())
        assert sorted_holidays is not None
        assert len(sorted_holidays) == 3  # All holidays should be included
        assert all(days_until[h] > 0 for h in days_until if h != "HolidayB")


@pytest.mark.asyncio
async def test_parse_holiday_date(mock_config, mock_repository):
    """Test parsing holiday dates."""
    from cogs.seasonalroles.holiday.holiday_validator import validate_date_format
    assert validate_date_format("05-05") is True


@pytest.mark.asyncio
async def test_parse_holiday_date_invalid(mock_config, mock_repository):
    """Test parsing invalid holiday dates."""
    from cogs.seasonalroles.holiday.holiday_validator import validate_date_format
    assert validate_date_format("13-45") is False  # Invalid month and day
    assert validate_date_format("invalid") is False  # Invalid format


@pytest.mark.asyncio
async def test_add_holiday(mock_config, mock_repository):
    """Test adding a new holiday."""
    service = HolidayService(config=mock_config, repository=mock_repository)
    mock_repository.add_holiday.return_value = True

    holiday_data = HolidayData(
        name="New Holiday",
        date="05-05",
        color="#68855A"
    )
    success, message = await service.add_holiday(MagicMock(), holiday_data)
    assert success is True
    assert "added successfully" in message
    mock_repository.add_holiday.assert_called_once()


@pytest.mark.asyncio
async def test_remove_holiday(mock_config, mock_repository):
    """Test removing a holiday."""
    service = HolidayService(config=mock_config, repository=mock_repository)
    mock_repository.remove_holiday.return_value = True

    success, message = await service.remove_holiday(MagicMock(), "Kids Day")
    assert success is True
    assert "removed successfully" in message
    mock_repository.remove_holiday.assert_called_once()


@pytest.mark.asyncio
async def test_edit_holiday(mock_config, mock_repository):
    """Test editing a holiday."""
    service = HolidayService(config=mock_config, repository=mock_repository)
    mock_repository.update_holiday.return_value = True

    holiday_data = HolidayData(
        name="Kids Day",
        date="05-05",
        color="#68855A"
    )
    success, message = await service.edit_holiday(MagicMock(), holiday_data)
    assert success is True
    assert "updated successfully" in message
    mock_repository.update_holiday.assert_called_once()
