import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in project root (3 directories up from this file)
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        logger.info("Loading environment variables from %s", env_path)
        load_dotenv(dotenv_path=env_path)
    else:
        logger.warning("No .env file found at %s", env_path)
except ImportError:
    logger.warning("python-dotenv not installed, skipping .env loading in LLM config")


class LLMConfig:

    """
    Configuration for LLM utilities.

    This class provides configuration settings for LLM services,
    reading values from environment variables.
    """

    @property
    def debug(self) -> bool:
        """Whether debug mode is enabled."""
        return os.getenv("LLM_DEBUG", "false").lower() == "true"

    @property
    def default_providers(self) -> list:
        """List of enabled LLM providers."""
        return os.getenv("LLM_PROVIDERS", "openai").split(",")

    @property
    def openai_api_key(self) -> str:
        """The OpenAI API key."""
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def anthropic_api_key(self) -> str:
        """The Anthropic API key."""
        return os.getenv("ANTHROPIC_API_KEY", "")
