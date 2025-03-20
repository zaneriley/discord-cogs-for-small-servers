from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from cogs.weatherchannel.config import ConfigManager
from discord import app_commands

# Fixtures now imported from conftest.py

@pytest.mark.asyncio
async def test_config_manager_init(mock_env, mock_cities_json, mock_cog, mock_config):
    """Test ConfigManager initialization."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        assert config.config == mock_config
        assert "cities" in config.cities_data

@pytest.mark.asyncio
async def test_get_default_locations(mock_env, mock_cities_json, mock_cog, mock_config):
    """Test getting default locations."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        mock_config.guild_from_id.return_value.default_locations = AsyncMock(return_value={
            "San Francisco": ("open-meteo", "37.7749,-122.4194"),
            "New York": ("open-meteo", "40.7128,-74.0060")
        })
        locations = await config.get_default_locations(123456789)
        assert isinstance(locations, dict)
        assert "San Francisco" in locations
        assert isinstance(locations["San Francisco"][1], tuple)

@pytest.mark.asyncio
async def test_get_city_choices(mock_env, mock_cities_json, mock_cog, mock_config):
    """Test getting city choices."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        choices = await config.get_city_choices()
        assert isinstance(choices, list)
        assert all(isinstance(choice, app_commands.Choice) for choice in choices)
        # Verify that all cities from cities.json are included
        assert len(choices) >= 2  # At least the cities from mock_cities_json
        # Verify that each city has a display name
        for choice in choices:
            assert choice.name
            assert choice.value

@pytest.mark.asyncio
async def test_set_and_get_weather_channel(mock_env, mock_cities_json, mock_cog, mock_config):
    """Test setting and getting weather channel ID."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        mock_config.guild_from_id.return_value.weather_channel_id = AsyncMock()
        await config.set_weather_channel(123456789, 987654321)
        mock_config.guild_from_id.return_value.weather_channel_id.set.assert_called_once_with(987654321)
        channel_id = await config.get_weather_channel(123456789)
        assert channel_id == mock_config.guild_from_id.return_value.weather_channel_id.return_value

@pytest.mark.asyncio
async def test_load_cities_data_missing_file(mock_env, mock_cog, mock_config):
    """Test loading cities data when file is missing."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config), \
         patch("cogs.weatherchannel.config.CITIES_FILE", Path("/nonexistent/file.json")):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        assert config.cities_data == {}

@pytest.mark.asyncio
async def test_load_cities_data_invalid_json(mock_env, mock_cog, mock_config, tmp_path):
    """Test loading cities data with invalid JSON."""
    invalid_json_file = tmp_path / "cities.json"
    invalid_json_file.write_text("invalid json")
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config), \
         patch("cogs.weatherchannel.config.CITIES_FILE", invalid_json_file):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        assert config.cities_data == {}

@pytest.mark.asyncio
async def test_validate_city_exists(mock_env, mock_cities_json, mock_cog, mock_config):
    """Test validating if a city exists."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        assert "San Francisco" in config.cities_data.get("cities", {})
        assert "NonexistentCity" not in config.cities_data.get("cities", {})

@pytest.mark.asyncio
async def test_get_city_coordinates(mock_env, mock_cities_json, mock_cog, mock_config):
    """Test getting coordinates for a city."""
    with patch("cogs.weatherchannel.config.Config.get_conf", return_value=mock_config):
        config = ConfigManager(guild_id=123456789, cog_instance=mock_cog)
        city_data = config.cities_data.get("cities", {}).get("San Francisco")
        assert city_data is not None
        assert city_data["coordinates"] == [37.7749, -122.4194]
