"""
LangGraph Agent base class for multi-step workflows.

Enables complex agent workflows with state management
while maintaining single-message pattern externally.
"""

from typing import Any

from langfuse import observe
from langgraph.graph import StateGraph

from ..config import Config, get_config
from ..providers import AnthropicAPIProvider, ClaudeAgentSDKProvider, LLMProvider


class LangGraphAgent:
    """
    Base class for multi-step workflows using LangGraph.

    Pattern: One input → Orchestrated steps → One output

    KEY: Still single-message pattern externally!
    Multiple LLM calls happen internally, but from the
    outside it's one invocation with one result.

    Perfect for:
    - Complex validation pipelines
    - Multi-stage analysis
    - Iterative refinement
    - Agent collaboration

    NOT for:
    - Streaming conversations
    - Real-time chat interfaces

    Example:
        ```python
        from agent_workshop.workflows import LangGraphAgent
        from langgraph.graph import StateGraph, END

        class ValidationPipeline(LangGraphAgent):
            def build_graph(self):
                workflow = StateGraph(dict)

                # Define steps
                workflow.add_node("scan", self.quick_scan)
                workflow.add_node("verify", self.verify)

                # Define flow
                workflow.add_edge("scan", "verify")
                workflow.add_edge("verify", END)

                workflow.set_entry_point("scan")

                return workflow.compile()

            async def quick_scan(self, state):
                result = await self.provider.complete([{
                    "role": "user",
                    "content": f"Quick scan: {state['content']}"
                }])
                return {"scan_result": result, **state}

            async def verify(self, state):
                result = await self.provider.complete([{
                    "role": "user",
                    "content": f"Verify: {state['scan_result']}"
                }])
                return {"final_result": result}

        # Usage (still single invocation!)
        pipeline = ValidationPipeline()
        result = await pipeline.run({"content": report})
        ```

    Attributes:
        config: Configuration instance
        provider: LLM provider (automatically selected)
        graph: Compiled LangGraph workflow
    """

    def __init__(self, config: Config | None = None):
        """
        Initialize LangGraph agent with configuration.

        Args:
            config: Configuration instance (uses get_config() if None)
        """
        self.config = config or get_config()
        self.provider = self._create_provider()
        self.graph = self.build_graph()

    def _create_provider(self) -> LLMProvider:
        """
        Create appropriate provider based on configuration.

        Returns:
            Configured LLM provider instance

        Raises:
            ValueError: If provider configuration is invalid
        """
        provider_config = self.config.get_provider_config()
        provider_type = provider_config["type"]

        if provider_type == "claude_sdk":
            return ClaudeAgentSDKProvider(
                model=provider_config["model"],
                langfuse_enabled=self.config.langfuse_enabled,
            )
        elif provider_type == "anthropic":
            return AnthropicAPIProvider(
                api_key=provider_config["api_key"],
                model=provider_config["model"],
                max_tokens=provider_config["max_tokens"],
                langfuse_enabled=self.config.langfuse_enabled,
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

    def build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        Override this method to define your workflow.

        Each node should be a method that:
        1. Takes state dict as input
        2. Calls self.provider.complete() for LLM interactions
        3. Returns updated state dict

        Returns:
            Compiled StateGraph

        Raises:
            NotImplementedError: Must be implemented by subclass

        Example:
            ```python
            def build_graph(self):
                workflow = StateGraph(dict)

                workflow.add_node("step1", self.step1)
                workflow.add_node("step2", self.step2)

                workflow.add_edge("step1", "step2")
                workflow.add_edge("step2", END)

                workflow.set_entry_point("step1")

                return workflow.compile()
            ```
        """
        raise NotImplementedError(
            "Subclasses must implement the build_graph() method. "
            "See the LangGraphAgent docstring for examples."
        )

    @observe(name="langgraph_workflow")
    async def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the LangGraph workflow.

        Automatically traced with Langfuse for full observability.
        Each node in the graph gets its own Langfuse span.

        Args:
            input: Input state dictionary

        Returns:
            Final state dictionary after all workflow steps

        Raises:
            Exception: If workflow execution fails
        """
        result = await self.graph.ainvoke(input)
        return result

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return self.provider.estimate_tokens(text)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        return self.provider.estimate_cost(input_tokens, output_tokens)

    @property
    def provider_name(self) -> str:
        """Get current provider name."""
        return self.provider.provider_name

    @property
    def model_name(self) -> str:
        """Get current model name."""
        return self.provider.model_name
