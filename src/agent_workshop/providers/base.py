"""
Base provider interface for LLM providers.

All provider implementations must inherit from LLMProvider
and implement the required abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers (Claude SDK, Anthropic API, OpenAI) implement
    this interface to ensure consistent behavior across the framework.

    Pattern: Single-message completion (input → output)
    NOT streaming conversations.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """
        Generate a single completion from messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **kwargs: Provider-specific parameters

        Returns:
            Generated text response

        Raises:
            ProviderError: If the API call fails
        """
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Used for cost projection and context management.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        pass

    @abstractmethod
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get provider name for logging/debugging.

        Returns:
            Provider identifier (e.g., "claude_sdk", "anthropic", "openai")
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Get current model name.

        Returns:
            Model identifier
        """
        pass


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        original_error: Exception | None = None,
    ):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class RateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""

    pass


class AuthenticationError(ProviderError):
    """Raised when provider authentication fails."""

    pass


class InvalidRequestError(ProviderError):
    """Raised when request to provider is invalid."""

    pass
