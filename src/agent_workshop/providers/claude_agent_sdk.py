"""
Claude Agent SDK provider for development use.

Uses Claude Agent SDK for cost-effective development ($20/month flat rate).
Automatically switches to Anthropic API for production.

NOTE: Requires claude-agent-sdk package (install with --extras claude-agent)
"""

import tiktoken
from langfuse import get_client, observe

from .base import LLMProvider, ProviderError

try:
    from claude_agent_sdk import ClaudeSDKClient, query
    from claude_agent_sdk import ClaudeAgentOptions

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False
    ClaudeSDKClient = None
    query = None
    ClaudeAgentOptions = None


class ClaudeAgentSDKProvider(LLMProvider):
    """
    Development provider using Claude Agent SDK.

    Features:
    - Unlimited usage for $20/month
    - Full Langfuse tracing
    - Token/cost estimation for production planning
    - Identical interface to production providers

    Pattern: Single-message completion (no streaming)

    Metrics Tracked:
    - Input/output tokens (estimated via tiktoken)
    - Projected API costs (for production planning)
    - Latency
    - Model performance

    Note: Install with: uv add agent-workshop[claude-agent]
    """

    # Claude Sonnet 4 pricing for projection
    INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
    OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000

    def __init__(
        self,
        model: str = "sonnet",
        langfuse_enabled: bool = True,
    ):
        """
        Initialize Claude Agent SDK provider.

        Args:
            model: Claude model variant ("opus", "sonnet", "haiku")
            langfuse_enabled: Enable Langfuse tracing

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if not CLAUDE_SDK_AVAILABLE:
            raise ImportError(
                "claude-agent-sdk is not installed. "
                "Install with: uv add agent-workshop[claude-agent]"
            )

        self.model = model
        self.langfuse_enabled = langfuse_enabled

        # Use GPT-4 tokenizer for estimation
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")

    @property
    def provider_name(self) -> str:
        return "claude_sdk"

    @property
    def model_name(self) -> str:
        return f"claude-{self.model}"

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using GPT-4 tokenizer.

        Close enough for Claude cost estimation.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return len(self.tokenizer.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Project what this request would cost on Anthropic API.

        Useful for:
        - Understanding production cost implications
        - Optimizing prompts before deployment
        - Budget planning

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Projected cost in USD
        """
        input_cost = input_tokens * self.INPUT_COST_PER_TOKEN
        output_cost = output_tokens * self.OUTPUT_COST_PER_TOKEN
        return input_cost + output_cost

    @observe(name="claude_sdk_completion", as_type="generation")
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        Generate completion using Claude Agent SDK.

        Langfuse automatically captures:
        - Full message history
        - Estimated token counts
        - Projected API costs
        - Response text
        - Execution time

        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature (currently not supported by SDK)
            max_tokens: Maximum response tokens (currently not supported by SDK)
            **kwargs: Additional parameters (reserved for future use)

        Returns:
            Model response text

        Raises:
            ProviderError: If SDK call fails

        Note: Claude Agent SDK uses single prompt queries.
        Multi-message conversations are concatenated.
        """
        try:
            # Convert messages to single prompt
            # Claude SDK doesn't use the messages format directly
            prompt = self._messages_to_prompt(messages)

            # Estimate input tokens
            input_tokens = self.estimate_tokens(prompt)

            # Use the query function for single completion
            response_text = ""
            async for message in query(prompt=prompt):
                # Accumulate response (could be multiple message chunks)
                if hasattr(message, "content") and message.content:
                    if isinstance(message.content, list):
                        for block in message.content:
                            if hasattr(block, "text"):
                                response_text += block.text
                    elif hasattr(message.content, "text"):
                        response_text += message.content.text
                    elif isinstance(message.content, str):
                        response_text += message.content

                # Extract cost if available
                if hasattr(message, "total_cost_usd"):
                    actual_cost = message.total_cost_usd
                else:
                    actual_cost = 0.0

            # Estimate output tokens
            output_tokens = self.estimate_tokens(response_text)

            # Project API cost
            projected_cost = self.estimate_cost(input_tokens, output_tokens)

            # Update Langfuse trace
            if self.langfuse_enabled:
                try:
                    langfuse = get_client()
                    langfuse.update_current_generation(
                        model=self.model_name,
                        model_parameters={
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            **kwargs,
                        },
                        input=messages,
                        output=response_text,
                        usage={
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens,
                            "unit": "TOKENS",
                        },
                        metadata={
                            "provider": "claude_sdk",
                            "environment": "development",
                            "projected_api_cost_usd": projected_cost,
                            "actual_cost_usd": actual_cost,
                            "cost_note": "Included in $20/month Claude Code subscription",
                        },
                    )

                    # Add projected cost score
                    langfuse.score_current_span(
                        name="projected_api_cost",
                        value=projected_cost,
                        comment=f"Estimated API cost: ${projected_cost:.6f}",
                    )

                    # Add token efficiency score
                    if input_tokens > 0:
                        efficiency = output_tokens / input_tokens
                        langfuse.score_current_span(
                            name="token_efficiency",
                            value=efficiency,
                            comment=f"Output/Input ratio: {efficiency:.2f}",
                        )
                except Exception:
                    # Silently continue if Langfuse is not properly configured
                    pass

            return response_text

        except Exception as e:
            raise ProviderError(
                f"Claude Agent SDK error: {str(e)}",
                provider="claude_sdk",
                original_error=e,
            ) from e

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """
        Convert OpenAI-style messages to single prompt for Claude SDK.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Concatenated prompt string
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")

        return "\n\n".join(parts)
