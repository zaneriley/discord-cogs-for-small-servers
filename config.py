import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseSettings, ValidationError, validator

# Get the cogs directory path
COGS_DIR = Path(__file__).parent
DEFAULT_ENV_FILE = COGS_DIR / ".env"

class BaseConfig(BaseSettings):

    """Base configuration class that other configs inherit from."""

    class Config:
        env_file = str(DEFAULT_ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = True

class GlobalConfig(BaseConfig):

    """Global configuration settings shared across all cogs."""

    # Required settings
    guild_id: int

    # Optional settings with defaults
    debug: bool = False
    testing: bool = False

    @validator("guild_id")
    def validate_guild_id(self, v: Optional[int]) -> int:
        if not v:
            msg = "GUILD_ID must be provided"
            raise ValueError(msg)
        return v

class LLMConfig(BaseConfig):

    """Configuration specific to the LLM cog."""

    openai_api_key: str
    llm_debug: bool = False
    default_providers: list[str] = ["openai"]

    @validator("openai_api_key")
    def validate_openai_api_key(self, v: str) -> str:
        if not v:
            msg = "OPENAI_API_KEY must be provided"
            raise ValueError(msg)
        return v

class WeatherConfig(BaseConfig):

    """Configuration specific to the Weather cog."""

    wx_locations: dict[str, Any] = {}

def load_config(config_class: type[BaseConfig] = GlobalConfig, env_file: Optional[str] = None) -> BaseConfig:
    """
    Loads and validates configuration settings.

    Args:
    ----
        config_class: The configuration class to instantiate (defaults to GlobalConfig)
        env_file: Optional path to a specific .env file to use

    Returns:
    -------
        An instance of the specified config class with validated settings

    Raises:
    ------
        RuntimeError: If validation fails

    """
    try:
        # Override env_file if specified
        if env_file:
            config_class.Config.env_file = env_file

        config = config_class()

        # Special handling for testing environment
        if isinstance(config, GlobalConfig) and os.getenv("TESTING") == "true":
            config.testing = True
            config.debug = True

        return config
    except ValidationError as e:
        msg = f"Configuration validation error: {e}"
        raise RuntimeError(msg) from e

# Example usage if this module is run directly:
if __name__ == "__main__":
    global_config = load_config()
    llm_config = load_config(LLMConfig)
    weather_config = load_config(WeatherConfig)
