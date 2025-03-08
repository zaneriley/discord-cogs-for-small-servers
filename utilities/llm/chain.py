import logging
import time
from typing import Callable, Optional

from .providers.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class LLMNode:
    def __init__(self, name: str, provider: BaseLLMProvider, prompt_modifier: Callable[[str], str] = lambda x: x):
        """
        Initializes the LLMNode.

        Args:
        ----
            name (str): A unique name for this node (for logging/debugging).
            provider (BaseLLMProvider): An instance of a provider that implements send_prompt.
            prompt_modifier (Callable[[str], str], optional): A function to modify the input prompt. Defaults to the identity function.

        """
        self.name = name
        self.provider = provider
        self.prompt_modifier = prompt_modifier

    async def process(self, input_prompt: str, **kwargs) -> LLMResponse:
        """
        Processes the input prompt by applying the prompt modifier and calling the provider's send_prompt method.

        Args:
        ----
            input_prompt (str): The prompt to process.
            kwargs: Additional arguments to pass to the provider.

        Returns:
        -------
            LLMResponse: The response from the provider.

        """
        modified_prompt = self.prompt_modifier(input_prompt)
        logger.debug(f"[{self.name}] Modified prompt: {modified_prompt}")
        response = await self.provider.send_prompt(modified_prompt, **kwargs)
        logger.debug(f"[{self.name}] Response: {response}")
        return response


class LLMChain:
    def __init__(self, nodes: Optional[list[LLMNode]] = None, debug: bool = False):
        """
        Initializes an LLMChain with a sequence of LLMNodes.

        Args:
        ----
            nodes (List[LLMNode], optional): The nodes in the chain, in processing order. Defaults to empty list.
            debug (bool, optional): Flag to enable debug logging. Defaults to False.

        """
        self.nodes = nodes or []
        self.debug = debug

    def add_node(self, name: str, provider: BaseLLMProvider, prompt_modifier: Callable[[str], str] = lambda x: x):
        """
        Add a node to the chain.

        Args:
        ----
            name (str): A unique name for this node.
            provider (BaseLLMProvider): An instance of a provider that implements send_prompt.
            prompt_modifier (Callable[[str], str], optional): A function to modify the input prompt.
                Defaults to the identity function.

        Returns:
        -------
            LLMChain: Self, for method chaining.

        """
        node = LLMNode(name=name, provider=provider, prompt_modifier=prompt_modifier)
        self.nodes.append(node)
        return self

    async def run(self, initial_prompt: str, **kwargs) -> LLMResponse:
        """
        Runs the chain by passing the prompt through each node sequentially.

        Args:
        ----
            initial_prompt (str): The initial prompt.
            kwargs: Additional arguments passed to each node's process.

        Returns:
        -------
            LLMResponse: The final response after processing all nodes.

        """
        debug_data = {}
        data = initial_prompt
        overall_start = time.time()

        for node in self.nodes:
            node_start = time.time()
            response = await node.process(data, **kwargs)
            node_elapsed = time.time() - node_start

            if self.debug:
                debug_data[node.name] = {
                    "input": data,
                    "output": response.content,
                    "latency": node_elapsed,
                    "error": response.error,
                    "error_message": response.error_message,
                }
            if response.error:
                logger.error(f"Error in node {node.name}: {response.error_message}")
                return LLMResponse(content=f"Error in node {node.name}: {response.error_message}", error=True, error_message=response.error_message)
            data = response.content

        overall_elapsed = time.time() - overall_start
        if self.debug:
            debug_data["total_latency"] = overall_elapsed
            logger.debug(f"LLMChain debug data: {debug_data}")
        # Aggregate token usage could be implemented here; currently set to 0
        return LLMResponse(content=data, tokens_used=0)
