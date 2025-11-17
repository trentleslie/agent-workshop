"""
Simple Agent base class for agent-workshop.

Provides a clean interface for building single-message agents
(input → output pattern) with automatic observability.
"""

from typing import Any

from langfuse import observe

from .config import Config, get_config
from .providers import AnthropicAPIProvider, ClaudeAgentSDKProvider, LLMProvider


class Agent:
    """
    Base class for simple single-message agents.

    Pattern: One input → One output

    Perfect for:
    - Automated validations
    - Batch processing
    - Scheduled jobs
    - CI/CD pipelines

    NOT for:
    - Streaming conversations
    - Interactive chat interfaces

    Example:
        ```python
        from agent_workshop import Agent, Config

        class DeliverableValidator(Agent):
            async def run(self, content: str) -> dict:
                messages = [{
                    "role": "user",
                    "content": f"Validate this deliverable:\\n\\n{content}"
                }]
                result = await self.complete(messages)
                return {"validation": result}

        # Usage
        config = Config()  # Auto-detects environment
        validator = DeliverableValidator(config)
        result = await validator.run(report_content)
        ```

    Attributes:
        config: Configuration instance
        provider: LLM provider (automatically selected based on config)
    """

    def __init__(self, config: Config | None = None):
        """
        Initialize agent with configuration.

        Args:
            config: Configuration instance (uses get_config() if None)
        """
        self.config = config or get_config()
        self.provider = self._create_provider()

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

    @observe(as_type="generation")
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """
        Generate a single completion from messages.

        Automatically traced with Langfuse for full observability.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **kwargs: Provider-specific parameters

        Returns:
            Generated text response

        Raises:
            ProviderError: If the LLM call fails
        """
        return await self.provider.complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def run(self, input: Any) -> Any:
        """
        Run the agent on input data.

        Override this method to implement your agent logic.

        Pattern:
        1. Prepare prompt from input
        2. Call self.complete() (single message)
        3. Parse and return result

        Args:
            input: Agent input (any type)

        Returns:
            Agent output (any type)

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError(
            "Subclasses must implement the run() method. "
            "Example:\n\n"
            "async def run(self, input: str) -> dict:\n"
            "    messages = [{'role': 'user', 'content': input}]\n"
            "    result = await self.complete(messages)\n"
            "    return {'result': result}\n"
        )

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Useful for:
        - Understanding context usage
        - Cost estimation
        - Prompt optimization

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
