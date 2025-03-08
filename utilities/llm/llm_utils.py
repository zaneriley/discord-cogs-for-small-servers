"""
Utility module for LLM integration.

This module provides functions to build and expose an LLMChain
that can be used by other plugins. This avoids relying on a standalone LLM cog.
"""

import logging
from pathlib import Path

from utilities.llm.chain import LLMChain
from utilities.llm.config import LLMConfig
from utilities.llm.providers.anthropic_provider import AnthropicProvider
from utilities.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Try to ensure environment variables are loaded
try:
    from dotenv import load_dotenv
    # Look for .env in project root
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        logger.info("Loading environment variables from %s", env_path)
        load_dotenv(dotenv_path=env_path)
    else:
        logger.warning("No .env file found at %s", env_path)
except ImportError:
    logger.warning("python-dotenv not installed, skipping .env loading in llm_utils")


def create_llm_chain() -> LLMChain:
    """
    Create and return an LLMChain instance based on configuration.

    The chain is configured with the debug flag and default providers (e.g. OpenAI, Anthropic).

    Returns
    -------
        LLMChain: A configured LLM processing chain.

    """
    config = LLMConfig()
    chain = LLMChain(debug=config.debug)

    # Track if any providers were added
    providers_added = False

    # Add OpenAI provider if configured
    if "openai" in config.default_providers:
        if config.openai_api_key:
            logger.info("Adding OpenAI provider to LLM chain")
            chain.add_node(
                name="openai_default",
                provider=OpenAIProvider(),
                prompt_modifier=lambda p: f"{p} [Respond in under 500 characters]"
            )
            providers_added = True
        else:
            logger.error("OpenAI provider requested but OPENAI_API_KEY is not set.")

    # Add Anthropic provider if configured
    if "anthropic" in config.default_providers:
        if config.anthropic_api_key:
            logger.info("Adding Anthropic provider to LLM chain")
            chain.add_node(
                name="anthropic_default",
                provider=AnthropicProvider(),
                prompt_modifier=lambda p: f"{p} [Respond in under 500 characters]"
            )
            providers_added = True
        else:
            logger.error("Anthropic provider requested but ANTHROPIC_API_KEY is not set.")

    # Warn if no providers were added
    if not providers_added:
        logger.warning("Creating LLM chain without any providers due to missing API keys.")

    return chain
