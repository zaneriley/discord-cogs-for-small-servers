"""
Utility module for counting tokens across different LLM providers.

This module provides functions to count tokens for different LLM services
(Anthropic, OpenAI, Gemini) with a consistent interface.
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod

import aiohttp

logger = logging.getLogger(__name__)

class TokenCounter(ABC):

    """Base class for counting tokens across different LLM providers."""

    @abstractmethod
    async def count_tokens(self, text, **kwargs):
        """Count tokens in the provided text."""


class AnthropicTokenCounter(TokenCounter):

    """Token counter for Anthropic models."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("No Anthropic API key found. Token counting will fail.")

    async def count_tokens(self, text, model="claude-3-sonnet-20240229", **kwargs):
        """
        Count tokens using Anthropic's count_tokens endpoint.

        Args:
            text: String or dictionary to count tokens for
            model: Anthropic model to use for token counting

        Returns:
            dict with token count information

        """
        if not self.api_key:
            msg = "Anthropic API key is required for token counting"
            raise ValueError(msg)

        # Convert dictionary to string if needed
        if isinstance(text, dict):
            text = json.dumps(text)

        # Prepare the request for Anthropic's count_tokens endpoint
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        # Format the messages structure expected by Anthropic
        data = {
            "model": model,
            "messages": [{"role": "user", "content": text}]
        }

        async with aiohttp.ClientSession() as session, session.post(
            "https://api.anthropic.com/v1/messages/count_tokens",
            headers=headers,
            json=data
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                msg = f"Anthropic API error: {response.status} - {error_text}"
                raise ValueError(msg)

            result = await response.json()
            return {
                "token_count": result.get("input_tokens", 0),
                "provider": "anthropic",
                "model": model,
                "raw_response": result
            }


class OpenAITokenCounter(TokenCounter):

    """Token counter for OpenAI models."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    async def count_tokens(self, text, model="gpt-4", **kwargs):
        """
        Count tokens using tiktoken library or OpenAI API.

        Args:
            text: String or dictionary to count tokens for
            model: OpenAI model to use for token counting

        Returns:
            dict with token count information

        """
        try:
            import tiktoken

            # Convert dictionary to string if needed
            if isinstance(text, dict):
                text = json.dumps(text)

            # Use tiktoken for local counting
            encoding = tiktoken.encoding_for_model(model)
            tokens = encoding.encode(text)

            return {
                "token_count": len(tokens),
                "provider": "openai",
                "model": model
            }
        except ImportError:
            logger.warning("tiktoken not installed, using fallback estimation")
            # Simple fallback if tiktoken is not available
            return await estimate_tokens(text, provider="openai")


class GeminiTokenCounter(TokenCounter):

    """Token counter for Google's Gemini models."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    async def count_tokens(self, text, **kwargs):
        """
        Count tokens using Gemini's tokenizer.

        Args:
            text: String or dictionary to count tokens for

        Returns:
            dict with token count information

        """
        # Gemini doesn't have a straightforward token counting API yet
        # This is a placeholder implementation that uses the estimate function
        return await estimate_tokens(text, provider="gemini")


def get_token_counter(provider="anthropic"):
    """
    Get a token counter for the specified provider.

    Args:
        provider: The LLM provider to use ("anthropic", "openai", or "gemini")

    Returns:
        TokenCounter: An instance of the appropriate token counter

    """
    counters = {
        "anthropic": AnthropicTokenCounter,
        "openai": OpenAITokenCounter,
        "gemini": GeminiTokenCounter,
    }

    counter_class = counters.get(provider.lower())
    if not counter_class:
        msg = f"Unsupported provider: {provider}"
        raise ValueError(msg)

    return counter_class()


async def count_tokens(text, provider="anthropic", **kwargs):
    """
    Count tokens using the specified provider.

    Args:
        text: String or structured content to count tokens for
        provider: The LLM provider to use ("anthropic", "openai", or "gemini")
        **kwargs: Additional provider-specific parameters

    Returns:
        dict: Token count information with at least {"token_count": int}

    Example:
        # Count tokens with default provider (Anthropic)
        token_info = await count_tokens("Hello, world")
        print(f"Token count: {token_info['token_count']}")

        # Count tokens with OpenAI
        token_info = await count_tokens("Hello, world", provider="openai", model="gpt-4")

    """
    counter = get_token_counter(provider)
    return await counter.count_tokens(text, **kwargs)


async def estimate_tokens(text, provider="anthropic"):
    """
    Get a rough token count estimate without API calls.

    This is less accurate but doesn't require API access.

    Args:
        text: String or dictionary to estimate tokens for
        provider: The LLM provider to use for estimation

    Returns:
        dict with estimated token count information

    """
    # Convert dictionary to string if needed
    if isinstance(text, dict):
        text = json.dumps(text)

    # Approximate token count based on whitespace and punctuation
    # This is a rough estimate - different models tokenize differently
    words = len(text.split())
    chars = len(text)

    # Different providers have different tokenization approaches
    # These are rough approximations
    if provider.lower() == "anthropic":
        # Claude tends to use more tokens per word than GPT
        estimated_tokens = int(words * 1.4)
    elif provider.lower() == "openai":
        # GPT models average about 4 chars per token
        estimated_tokens = int(chars / 4)
    else:
        # Generic fallback
        estimated_tokens = int(words * 1.3)

    return {
        "token_count": estimated_tokens,
        "provider": provider,
        "estimation_method": "approximate",
        "words": words,
        "characters": chars
    }


async def compare_token_counts(text_a, text_b, provider="anthropic", **kwargs):
    """
    Compare token counts between two different text formats.

    Args:
        text_a: First text or dictionary to compare
        text_b: Second text or dictionary to compare
        provider: The LLM provider to use
        **kwargs: Additional provider-specific parameters

    Returns:
        dict with comparison information

    """
    counter = get_token_counter(provider)

    # Count tokens for both formats
    count_a = await counter.count_tokens(text_a, **kwargs)
    count_b = await counter.count_tokens(text_b, **kwargs)

    # Calculate differences
    token_diff = count_a["token_count"] - count_b["token_count"]
    if count_a["token_count"] > 0:
        percent_reduction = (token_diff / count_a["token_count"]) * 100
    else:
        percent_reduction = 0

    return {
        "format_a": count_a,
        "format_b": count_b,
        "difference": token_diff,
        "percent_reduction": percent_reduction
    }


async def count_tokens_batch(texts, provider="anthropic", **kwargs):
    """
    Count tokens for multiple texts in parallel.

    Args:
        texts: List of strings or dictionaries to count tokens for
        provider: The LLM provider to use
        **kwargs: Additional provider-specific parameters

    Returns:
        list of token count information dictionaries

    """
    counter = get_token_counter(provider)

    tasks = []
    for text in texts:
        tasks.append(counter.count_tokens(text, **kwargs))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error counting tokens for item {i}: {result}")
            processed_results.append({
                "token_count": 0,
                "error": str(result),
                "provider": provider
            })
        else:
            processed_results.append(result)

    return processed_results
