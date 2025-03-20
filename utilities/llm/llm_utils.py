"""
Utility module for LLM integration.

This module provides functions to build and expose an LLMChain
that can be used by other plugins. This avoids relying on a standalone LLM cog.
"""

import logging
import os
from pathlib import Path

# Handle imports to work both locally and in Docker
try:
    # First try the Docker path
    from utilities.llm.chain import LLMChain
    from utilities.llm.config import LLMConfig
    from utilities.llm.providers.anthropic_provider import AnthropicProvider
    from utilities.llm.providers.openai_provider import OpenAIProvider
except ImportError:
    try:
        # If that fails, try the local path
        from cogs.utilities.llm.chain import LLMChain
        from cogs.utilities.llm.config import LLMConfig
        from cogs.utilities.llm.providers.anthropic_provider import AnthropicProvider
        from cogs.utilities.llm.providers.openai_provider import OpenAIProvider
    except ImportError:
        # Last resort, try relative imports for local development
        from .chain import LLMChain
        from .config import LLMConfig
        from .providers.anthropic_provider import AnthropicProvider
        from .providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Try to ensure environment variables are loaded
try:
    from dotenv import load_dotenv
    # Look for .env in project root
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        logger.info("[LLM Utils] Loading environment variables from %s", env_path)
        load_dotenv(dotenv_path=env_path)
        # Check if critical variables were loaded
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        logger.debug("[LLM Utils] API Keys loaded: OpenAI=%s, Anthropic=%s",
                    "Yes" if openai_key else "No",
                    "Yes" if anthropic_key else "No")
    else:
        logger.warning("[LLM Utils] No .env file found at %s", env_path)
        # Log current environment without exposing sensitive values
        env_vars = {k: "[SET]" if any(secret in k.upper() for secret in ["KEY", "TOKEN", "SECRET"])
                    else v for k, v in os.environ.items()
                    if k.startswith(("OPENAI_", "ANTHROPIC_", "LLM_"))}
        logger.debug("[LLM Utils] Current LLM environment variables: %s", env_vars)
except ImportError:
    logger.warning("[LLM Utils] python-dotenv not installed, skipping .env loading in llm_utils")


def create_llm_chain() -> LLMChain:
    """
    Create and return an LLMChain instance based on configuration.

    The chain is configured with the debug flag and default providers (e.g. OpenAI, Anthropic).

    Returns
    -------
        LLMChain: A configured LLM processing chain.

    """
    logger.debug("[LLM Utils] Creating LLM chain...")
    config = LLMConfig()

    # Add logging for API key availability (without revealing the actual keys)
    logger.debug("[LLM Utils] API keys available: OpenAI=%s, Anthropic=%s",
               "Yes" if config.openai_api_key else "No",
               "Yes" if config.anthropic_api_key else "No")
    logger.debug("[LLM Utils] Default providers configured: %s", config.default_providers)

    chain = LLMChain(debug=config.debug)
    logger.debug("[LLM Utils] Created chain with debug=%s", config.debug)

    # Track if any providers were added
    providers_added = False

    # Add OpenAI provider if configured
    if "openai" in config.default_providers:
        if config.openai_api_key:
            logger.info("[LLM Utils] Adding OpenAI provider to LLM chain")
            try:
                chain.add_node(
                    name="openai_default",
                    provider=OpenAIProvider(),
                    prompt_modifier=lambda p: f"{p} [Respond in under 500 characters]"
                )
                providers_added = True
                logger.debug("[LLM Utils] Successfully added OpenAI provider")
            except Exception:
                logger.exception("[LLM Utils] Error creating OpenAI provider")
        else:
            logger.error("[LLM Utils] OpenAI provider requested but OPENAI_API_KEY is not set or is empty")

    # Add Anthropic provider if configured
    if "anthropic" in config.default_providers:
        if config.anthropic_api_key:
            logger.info("[LLM Utils] Adding Anthropic provider to LLM chain")
            try:
                chain.add_node(
                    name="anthropic_default",
                    provider=AnthropicProvider(),
                    prompt_modifier=lambda p: f"{p} [Respond in under 500 characters]"
                )
                providers_added = True
                logger.debug("[LLM Utils] Successfully added Anthropic provider")
            except Exception:
                logger.exception("[LLM Utils] Error creating Anthropic provider")
        else:
            logger.error("[LLM Utils] Anthropic provider requested but ANTHROPIC_API_KEY is not set or is empty")

    # Warn if no providers were added
    if not providers_added:
        logger.warning("[LLM Utils] Creating LLM chain without any providers due to missing or invalid API keys")

    return chain
