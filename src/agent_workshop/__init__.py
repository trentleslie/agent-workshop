"""
agent-workshop: Framework for building automation-focused AI agents with observability.

Simple agents (80% of users):
    from agent_workshop import Agent, Config

    class MyAgent(Agent):
        async def run(self, input):
            return await self.complete(...)

LangGraph workflows (15% of users):
    from agent_workshop.workflows import LangGraphAgent

    class MyWorkflow(LangGraphAgent):
        def build_graph(self):
            # Define multi-step workflow
            ...

Environment management:
    - Development: Claude Agent SDK ($20/month flat)
    - Production: Anthropic API (pay-per-token)
    - Automatic provider switching via env vars
    - Full Langfuse observability in both

Setup:
    1. uv add agent-workshop
    2. Create .env.development and .env.production
    3. Configure Langfuse (optional but recommended)
    4. Build agents!

Documentation: https://github.com/trentleslie/agent-workshop
"""

# CRITICAL: Load environment variables BEFORE any imports that use Langfuse
# This ensures Langfuse decorators (@observe) can read LANGFUSE_PUBLIC_KEY and
# LANGFUSE_SECRET_KEY from .env files when they initialize at import time.
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Determine which environment we're running in
    env = os.getenv("AGENT_WORKSHOP_ENV", "development")
    env_file = f".env.{env}"

    # Look for environment-specific .env file in current working directory
    env_path = Path.cwd() / env_file
    if env_path.exists():
        load_dotenv(env_path)
    # Fall back to generic .env if environment-specific file doesn't exist
    elif (Path.cwd() / ".env").exists():
        load_dotenv(Path.cwd() / ".env")

except ImportError:
    # python-dotenv is optional, but recommended for proper env loading
    # If not installed, environment variables must be set externally
    pass

__version__ = "0.3.0"

# Core classes
from .agent import Agent
from .config import Config, Environment, get_config

# Provider access (usually not needed directly)
from .providers import (
    AnthropicAPIProvider,
    AuthenticationError,
    ClaudeAgentSDKProvider,
    InvalidRequestError,
    LLMProvider,
    ProviderError,
    RateLimitError,
)

# LangGraph integration
from .workflows import LangGraphAgent

# Utilities
from .utils import setup_langfuse

__all__ = [
    # Version
    "__version__",
    # Core
    "Agent",
    "Config",
    "Environment",
    "get_config",
    # Providers
    "LLMProvider",
    "ClaudeAgentSDKProvider",
    "AnthropicAPIProvider",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidRequestError",
    # Workflows
    "LangGraphAgent",
    # Utils
    "setup_langfuse",
]
