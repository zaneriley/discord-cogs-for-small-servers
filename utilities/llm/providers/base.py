from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    tokens_used: int = 0
    error: bool = False
    error_message: str = ""

class BaseLLMProvider(ABC):
    @abstractmethod
    async def send_prompt(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Sends a prompt to the LLM and returns a standardized LLMResponse.
        """
