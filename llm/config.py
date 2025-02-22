import os


class LLMConfig:
    @property
    def debug(self) -> bool:
        return os.getenv("LLM_DEBUG", "false").lower() == "true"

    @property
    def default_providers(self) -> list:
        return os.getenv("LLM_PROVIDERS", "openai").split(",")
