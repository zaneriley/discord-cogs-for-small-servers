from unittest.mock import patch

# Using cogs prefix as it's in PYTHONPATH in Docker
from utilities.llm.llm_utils import create_llm_chain
from utilities.llm.providers.anthropic_provider import AnthropicProvider
from utilities.llm.providers.openai_provider import OpenAIProvider


def test_create_llm_chain_openai_only():
    """Test create_llm_chain with only OpenAI provider configured."""
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "test-openai-key",
        "LLM_PROVIDERS": "openai"
    }, clear=True):
        chain = create_llm_chain()

        # Verify the chain has one node with an OpenAI provider
        assert len(chain.nodes) == 1
        assert isinstance(chain.nodes[0].provider, OpenAIProvider)
        assert chain.nodes[0].name == "openai_default"


def test_create_llm_chain_anthropic_only():
    """Test create_llm_chain with only Anthropic provider configured."""
    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "LLM_PROVIDERS": "anthropic"
    }, clear=True):
        chain = create_llm_chain()

        # Verify the chain has one node with an Anthropic provider
        assert len(chain.nodes) == 1
        assert isinstance(chain.nodes[0].provider, AnthropicProvider)
        assert chain.nodes[0].name == "anthropic_default"


def test_create_llm_chain_both_providers():
    """Test create_llm_chain with both providers configured."""
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "LLM_PROVIDERS": "openai,anthropic"
    }, clear=True):
        chain = create_llm_chain()

        # Verify the chain has two nodes with correct providers
        assert len(chain.nodes) == 2
        assert isinstance(chain.nodes[0].provider, OpenAIProvider)
        assert chain.nodes[0].name == "openai_default"
        assert isinstance(chain.nodes[1].provider, AnthropicProvider)
        assert chain.nodes[1].name == "anthropic_default"


def test_create_llm_chain_no_api_keys():
    """Test create_llm_chain with providers configured but no API keys."""
    with patch.dict("os.environ", {
        "LLM_PROVIDERS": "openai,anthropic"
    }, clear=True):
        chain = create_llm_chain()

        # Verify the chain has no nodes
        assert len(chain.nodes) == 0


def test_create_llm_chain_missing_one_key():
    """Test create_llm_chain with one missing API key."""
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "test-openai-key",
        "LLM_PROVIDERS": "openai,anthropic"
    }, clear=True):
        chain = create_llm_chain()

        # Verify only OpenAI node is added
        assert len(chain.nodes) == 1
        assert isinstance(chain.nodes[0].provider, OpenAIProvider)
        assert chain.nodes[0].name == "openai_default"
