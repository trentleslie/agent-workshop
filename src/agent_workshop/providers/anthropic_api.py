"""
Anthropic API provider for production use.

Uses the Anthropic API with actual token counts and costs.
Recommended for production deployments.
"""

import tiktoken
from anthropic import AsyncAnthropic, AnthropicError
from langfuse import get_client, observe

from .base import (
    AuthenticationError,
    InvalidRequestError,
    LLMProvider,
    ProviderError,
    RateLimitError,
)


class AnthropicAPIProvider(LLMProvider):
    """
    Production provider using Anthropic API.

    Features:
    - Actual token counts from API
    - Real API costs
    - Production-grade error handling
    - Full Langfuse observability

    Pricing (Claude Sonnet 4):
    - Input: $3.00 / 1M tokens
    - Output: $15.00 / 1M tokens
    """

    # Pricing per token (Claude Sonnet 4)
    INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
    OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        langfuse_enabled: bool = True,
    ):
        """
        Initialize Anthropic API provider.

        Args:
            api_key: Anthropic API key
            model: Model identifier
            max_tokens: Default max tokens for responses
            langfuse_enabled: Enable Langfuse tracing
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.langfuse_enabled = langfuse_enabled

        # Use GPT-4 tokenizer as approximation for estimation
        # Actual counts come from API
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self.model

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using GPT-4 tokenizer.

        Note: This is an approximation. Actual token counts
        come from the API response.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return len(self.tokenizer.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate actual API cost from token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        input_cost = input_tokens * self.INPUT_COST_PER_TOKEN
        output_cost = output_tokens * self.OUTPUT_COST_PER_TOKEN
        return input_cost + output_cost

    @observe(name="anthropic_api_completion", as_type="generation")
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """
        Generate completion using Anthropic API.

        Langfuse automatically captures:
        - Full message history
        - Model parameters
        - Actual token counts from API
        - Actual costs
        - Execution time

        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum response tokens (uses default if None)
            **kwargs: Additional model parameters

        Returns:
            Model response text

        Raises:
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded
            InvalidRequestError: If request is malformed
            ProviderError: For other API errors
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        try:
            response = await self.client.messages.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # Extract response text
            output_text = response.content[0].text

            # Calculate actual cost
            actual_cost = self.estimate_cost(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            # Update Langfuse trace with actual metrics
            if self.langfuse_enabled:
                try:
                    langfuse = get_client()
                    langfuse.update_current_generation(
                        model=self.model,
                        model_parameters={
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            **kwargs,
                        },
                        input=messages,
                        output=output_text,
                        usage={
                            "input": response.usage.input_tokens,
                            "output": response.usage.output_tokens,
                            "total": (
                                response.usage.input_tokens + response.usage.output_tokens
                            ),
                            "unit": "TOKENS",
                        },
                        metadata={
                            "provider": "anthropic_api",
                            "environment": "production",
                            "actual_cost_usd": actual_cost,
                            "stop_reason": response.stop_reason,
                        },
                    )

                    # Add cost as custom score
                    langfuse.score_current_span(
                        name="actual_api_cost",
                        value=actual_cost,
                        comment=f"Actual API cost: ${actual_cost:.6f}",
                    )

                    # Add token efficiency score
                    if response.usage.input_tokens > 0:
                        efficiency = (
                            response.usage.output_tokens / response.usage.input_tokens
                        )
                        langfuse.score_current_span(
                            name="token_efficiency",
                            value=efficiency,
                            comment=f"Output/Input ratio: {efficiency:.2f}",
                        )
                except Exception:
                    # Silently continue if Langfuse is not properly configured
                    pass

            return output_text

        except AnthropicError as e:
            # Map Anthropic errors to our error types
            error_str = str(e)

            if "authentication" in error_str.lower() or "api_key" in error_str.lower():
                raise AuthenticationError(
                    "Invalid Anthropic API key",
                    provider="anthropic",
                    original_error=e,
                ) from e
            elif "rate_limit" in error_str.lower() or "429" in error_str:
                raise RateLimitError(
                    "Anthropic API rate limit exceeded",
                    provider="anthropic",
                    original_error=e,
                ) from e
            elif "invalid" in error_str.lower() or "400" in error_str:
                raise InvalidRequestError(
                    f"Invalid request to Anthropic API: {error_str}",
                    provider="anthropic",
                    original_error=e,
                ) from e
            else:
                raise ProviderError(
                    f"Anthropic API error: {error_str}",
                    provider="anthropic",
                    original_error=e,
                ) from e
