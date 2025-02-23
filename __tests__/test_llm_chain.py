import pytest
from cogs.utilities.llm.chain import LLMChain, LLMNode
from cogs.utilities.llm.providers.base import BaseLLMProvider, LLMResponse


# Create a dummy provider that appends text to the prompt.
class DummyProvider(BaseLLMProvider):
    def __init__(self, simulate_error: bool = False):
        self.simulate_error = simulate_error

    async def send_prompt(self, prompt: str, **kwargs) -> LLMResponse:
        if self.simulate_error:
            return LLMResponse(content="", tokens_used=0, error=True, error_message="Simulated error")
        # Append fixed text for test purposes
        return LLMResponse(content=prompt + " processed", tokens_used=1)

@pytest.mark.asyncio
async def test_llm_node_process_normal():
    # Test that LLMNode applies the prompt modifier correctly.
    provider = DummyProvider()
    # Define a prompt modifier that uppercases the prompt
    def prompt_modifier(p):
        return p.upper()
    node = LLMNode(name="TestNode", provider=provider, prompt_modifier=prompt_modifier)
    input_prompt = "test"
    response = await node.process(input_prompt)
    # Expect the provider to receive "TEST" and then append " processed"
    assert response.content == "TEST processed"
    assert not response.error

@pytest.mark.asyncio
async def test_llm_chain_normal():
    # Create two nodes in the chain that process in sequence.
    provider = DummyProvider()
    node1 = LLMNode(name="Node1", provider=provider, prompt_modifier=lambda x: x + " step1")
    node2 = LLMNode(name="Node2", provider=provider, prompt_modifier=lambda x: x + " step2")
    chain = LLMChain(nodes=[node1, node2], debug=True)
    initial_prompt = "start"
    response = await chain.run(initial_prompt)
    # Expected sequence:
    # Node1: "start step1" => "start step1 processed"
    # Node2: "start step1 processed step2" => "start step1 processed step2 processed"
    expected = "start step1 processed step2 processed"
    assert response.content == expected
    assert not response.error

@pytest.mark.asyncio
async def test_llm_chain_stops_on_error():
    # Create a chain where the second node simulates an error.
    provider_ok = DummyProvider()
    provider_err = DummyProvider(simulate_error=True)

    node1 = LLMNode(name="Node1", provider=provider_ok, prompt_modifier=lambda x: x + " ok")
    node2 = LLMNode(name="Node2", provider=provider_err, prompt_modifier=lambda x: x + " error")
    chain = LLMChain(nodes=[node1, node2], debug=True)

    response = await chain.run("start")
    # Expect an error response from Node2
    assert response.error
    assert "Simulated error" in response.error_message

# Additional edge-case: Test chain with a single node and no prompt modifier.
@pytest.mark.asyncio
async def test_llm_chain_single_node_no_modifier():
    provider = DummyProvider()
    node = LLMNode(name="SingleNode", provider=provider)  # default modifier (identity)
    chain = LLMChain(nodes=[node])
    response = await chain.run("edge-case")
    assert response.content == "edge-case processed"
    assert not response.error
