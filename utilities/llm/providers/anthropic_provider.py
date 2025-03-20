import logging
import os
from pathlib import Path

import aiohttp

# Handle imports to work both locally and in Docker
try:
    # First try the Docker path
    from utilities.llm.config import LLMConfig
except ImportError:
    try:
        # If that fails, try the local path relative to providers directory
        from ..config import LLMConfig
    except ImportError:
        # Last resort - try the full absolute path
        from cogs.utilities.llm.config import LLMConfig

from .base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        config = LLMConfig()
        self.api_key = config.anthropic_api_key
        self.endpoint = "https://api.anthropic.com/v1/messages"
        self.api_version = "2023-06-01"  # Default Anthropic API version

        if not self.api_key:
            # Check if we can load directly from environment
            self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

            if not self.api_key:
                # Log available environment variables to help diagnose the issue (without showing key values)
                env_keys = list(os.environ.keys())
                logger.error("[Anthropic] API key not found in environment variables.")
                logger.debug("[Anthropic] Available environment variables: %s",
                            ", ".join([k for k in env_keys if not any(secret in k.upper() for secret in ["KEY", "TOKEN", "SECRET", "PASS"])]))

                # Check if .env file exists
                env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
                if env_path.exists():
                    logger.info("[Anthropic] .env file exists at %s", env_path)
                    # Try to load directly
                    try:
                        from dotenv import load_dotenv
                        load_dotenv(dotenv_path=env_path)
                        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                        if self.api_key:
                            logger.info("[Anthropic] Successfully loaded API key from .env file")
                    except ImportError:
                        logger.warning("[Anthropic] python-dotenv not installed, can't load from .env file")
                else:
                    logger.warning("[Anthropic] No .env file found at expected path: %s", env_path)

    async def send_prompt(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.api_key:
            error_msg = "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable in your .env file."
            logger.error("[Anthropic] %s", error_msg)
            return LLMResponse(
                content="",
                tokens_used=0,
                error=True,
                error_message=error_msg
            )

        # Anthropic API parameters - default to Claude 3 Sonnet if not specified
        model = kwargs.get("model", "claude-3-sonnet-20240229")
        max_tokens = kwargs.get("max_tokens", 1024)
        temperature = kwargs.get("temperature", 0.7)
        system = kwargs.get("system", "")

        # Build Anthropic-specific payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        # Add system prompt if provided
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json"
        }

        timeout = kwargs.get("timeout", 30)
        try:
            async with aiohttp.ClientSession() as session:
                async with await session.post(self.endpoint, json=payload, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()
                    data = await response.json()

                    # Parse Anthropic response
                    if "content" in data and len(data["content"]) > 0 and "text" in data["content"][0]:
                        content = data["content"][0]["text"]
                    else:
                        content = ""

                    # Calculate tokens used
                    input_tokens = data.get("usage", {}).get("input_tokens", 0)
                    output_tokens = data.get("usage", {}).get("output_tokens", 0)
                    tokens_used = input_tokens + output_tokens

                    return LLMResponse(content=content, tokens_used=tokens_used)
        except Exception as e:
            error_message = str(e)
            logger.exception("[Anthropic] Error calling API: %s", error_message)
            return LLMResponse(content="", tokens_used=0, error=True, error_message=error_message)
