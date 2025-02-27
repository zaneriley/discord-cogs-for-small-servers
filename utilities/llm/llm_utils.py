"""
Utility module for LLM integration.

This module provides functions to build and expose an LLMChain
that can be used by other plugins. This avoids relying on a standalone LLM cog.
"""

from cogs.llm.config import LLMConfig

from utilities.llm.chain import LLMChain
from utilities.llm.providers.openai_provider import OpenAIProvider


def create_llm_chain() -> LLMChain:
    """
    Create and return an LLMChain instance based on configuration.

    The chain is configured with the debug flag and default providers (e.g. OpenAI).

    Returns
    -------
        LLMChain: A configured LLM processing chain.

    """
    config = LLMConfig()
    chain = LLMChain(debug=config.debug)

    if "openai" in config.default_providers:
        chain.add_node(
            name="openai_default",
            provider=OpenAIProvider(),
            prompt_modifier=lambda p: f"{p} [Respond in under 500 characters]"
        )

    # Additional providers can be added here based on future configuration settings.

    return chain
