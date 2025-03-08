
import pytest

# Using cogs prefix as it's in PYTHONPATH in Docker
from utilities.llm.chain import LLMChain, LLMNode
from utilities.llm.tests.conftest import MockLLMProvider


@pytest.mark.asyncio
async def test_llm_node_process():
    """Test LLMNode processes prompts correctly."""
    # Create a mock provider
    provider = MockLLMProvider(response_content="Test response")

    # Create a node with a modifier
    node = LLMNode(
        name="test_node",
        provider=provider,
        prompt_modifier=lambda p: f"Modified: {p}"
    )

    # Process a prompt
    response = await node.process("Test prompt")

    # Verify the prompt was modified and sent to provider
    assert provider.prompts[0][0] == "Modified: Test prompt"
    assert response.content == "Test response"
    assert not response.error


@pytest.mark.asyncio
async def test_llm_chain_single_node():
    """Test LLMChain with a single node."""
    # Create a mock provider
    provider = MockLLMProvider(response_content="Test response")

    # Create a chain with one node
    chain = LLMChain(debug=True)
    chain.add_node(name="test_node", provider=provider)

    # Run the chain
    response = await chain.run("Test prompt")

    # Verify the response
    assert response.content == "Test response"
    assert not response.error


@pytest.mark.asyncio
async def test_llm_chain_multiple_nodes():
    """Test LLMChain with multiple nodes."""
    # Create mock providers
    provider1 = MockLLMProvider(response_content="First response")
    provider2 = MockLLMProvider(response_content="Second response")

    # Create a chain with two nodes
    chain = LLMChain(debug=True)
    chain.add_node(name="node1", provider=provider1)
    chain.add_node(name="node2", provider=provider2)

    # Run the chain
    response = await chain.run("Test prompt")

    # Verify each node processed in sequence
    assert provider1.prompts[0][0] == "Test prompt"
    assert provider2.prompts[0][0] == "First response"
    assert response.content == "Second response"


@pytest.mark.asyncio
async def test_llm_chain_error_handling():
    """Test LLMChain handles errors correctly."""
    # Create a provider that returns an error
    error_provider = MockLLMProvider(
        response_content="",
        error=True,
        error_message="Test error"
    )

    # Create a chain with the error provider
    chain = LLMChain(debug=True)
    chain.add_node(name="error_node", provider=error_provider)

    # Run the chain
    response = await chain.run("Test prompt")

    # Verify the error is propagated
    assert response.error
    assert "Test error" in response.error_message


@pytest.mark.asyncio
async def test_llm_chain_prompt_modifier():
    """Test that prompt modifiers work in the LLMChain."""
    # Create a mock provider
    provider = MockLLMProvider(response_content="Test response")

    # Create a chain with a prompt modifier
    chain = LLMChain(debug=True)
    chain.add_node(
        name="test_node",
        provider=provider,
        prompt_modifier=lambda p: f"Modified: {p}"
    )

    # Run the chain
    await chain.run("Test prompt")

    # Verify the prompt was modified
    assert provider.prompts[0][0] == "Modified: Test prompt"
