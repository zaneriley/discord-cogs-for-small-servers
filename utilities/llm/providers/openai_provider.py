import logging
import os
from pathlib import Path

import aiohttp

from utilities.llm.config import LLMConfig

from .base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        config = LLMConfig()
        self.api_key = config.openai_api_key
        self.endpoint = "https://api.openai.com/v1/chat/completions"

        if not self.api_key:
            # Log available environment variables to help diagnose the issue
            env_vars = {k: "***" if "KEY" in k else v for k, v in os.environ.items()}
            logger.error("OpenAI API key not found in environment variables.")
            logger.debug("Current environment variables: %s", env_vars)

            # Check if .env file exists
            env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
            if env_path.exists():
                logger.info(".env file exists at %s", env_path)
            else:
                logger.warning("No .env file found at expected path: %s", env_path)

    async def send_prompt(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.api_key:
            error_msg = "OpenAI API key not configured. Set OPENAI_API_KEY environment variable in your .env file."
            logger.error(error_msg)
            return LLMResponse(
                content="",
                tokens_used=0,
                error=True,
                error_message=error_msg
            )

        payload = {
            "model": kwargs.get("model", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7)
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = kwargs.get("timeout", 10)
        try:
            async with aiohttp.ClientSession() as session:
                async with await session.post(self.endpoint, json=payload, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()
                    data = await response.json()
                    # Extract the first choice's message content; adjust if provider returns differently
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    tokens_used = data.get("usage", {}).get("total_tokens", 0)
                    return LLMResponse(content=content, tokens_used=tokens_used)
        except Exception as e:
            return LLMResponse(content="", tokens_used=0, error=True, error_message=str(e))
