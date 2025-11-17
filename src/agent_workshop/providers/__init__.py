"""
LLM provider abstraction layer for agent-workshop.

Supports multiple LLM providers with a unified interface:
- Claude Agent SDK (development)
- Anthropic API (production)
- OpenAI (optional)
"""

from .anthropic_api import AnthropicAPIProvider
from .base import (
    AuthenticationError,
    InvalidRequestError,
    LLMProvider,
    ProviderError,
    RateLimitError,
)
from .claude_agent_sdk import ClaudeAgentSDKProvider

__all__ = [
    "LLMProvider",
    "ClaudeAgentSDKProvider",
    "AnthropicAPIProvider",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidRequestError",
]
