from unittest.mock import patch

# Using cogs prefix as it's in PYTHONPATH in Docker
from utilities.llm.config import LLMConfig


def test_config_debug_property():
    """Test that debug property reads from environment correctly."""
    # Test default value
    with patch.dict("os.environ", {}, clear=True):
        config = LLMConfig()
        assert config.debug is False

    # Test true value
    with patch.dict("os.environ", {"LLM_DEBUG": "true"}, clear=True):
        config = LLMConfig()
        assert config.debug is True

    # Test false value
    with patch.dict("os.environ", {"LLM_DEBUG": "false"}, clear=True):
        config = LLMConfig()
        assert config.debug is False


def test_config_default_providers_property():
    """Test that default_providers property reads from environment correctly."""
    # Test default value
    with patch.dict("os.environ", {}, clear=True):
        config = LLMConfig()
        assert config.default_providers == ["openai"]

    # Test single provider
    with patch.dict("os.environ", {"LLM_PROVIDERS": "anthropic"}, clear=True):
        config = LLMConfig()
        assert config.default_providers == ["anthropic"]

    # Test multiple providers
    with patch.dict("os.environ", {"LLM_PROVIDERS": "openai,anthropic"}, clear=True):
        config = LLMConfig()
        assert "openai" in config.default_providers
        assert "anthropic" in config.default_providers
        assert len(config.default_providers) == 2


def test_config_api_keys():
    """Test that API key properties read from environment correctly."""
    # Test default values
    with patch.dict("os.environ", {}, clear=True):
        config = LLMConfig()
        assert config.openai_api_key == ""
        assert config.anthropic_api_key == ""

    # Test OpenAI key only
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-openai-key"}, clear=True):
        config = LLMConfig()
        assert config.openai_api_key == "test-openai-key"
        assert config.anthropic_api_key == ""

    # Test Anthropic key only
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-anthropic-key"}, clear=True):
        config = LLMConfig()
        assert config.openai_api_key == ""
        assert config.anthropic_api_key == "test-anthropic-key"

    # Test both keys
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key"
    }, clear=True):
        config = LLMConfig()
        assert config.openai_api_key == "test-openai-key"
        assert config.anthropic_api_key == "test-anthropic-key"
