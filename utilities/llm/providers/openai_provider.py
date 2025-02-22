import os

import aiohttp

from .base import BaseLLMProvider, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    async def send_prompt(self, prompt: str, **kwargs) -> LLMResponse:
        payload = {
            "model": kwargs.get("model", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7)
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = kwargs.get("timeout", 10)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint, json=payload, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()
                    data = await response.json()
                    # Extract the first choice's message content; adjust if provider returns differently
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    tokens_used = data.get("usage", {}).get("total_tokens", 0)
                    return LLMResponse(content=content, tokens_used=tokens_used)
        except Exception as e:
            return LLMResponse(content="", tokens_used=0, error=True, error_message=str(e))
