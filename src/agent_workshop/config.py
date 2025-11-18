"""
Configuration system for agent-workshop.

Handles environment-based configuration with Pydantic Settings.
Supports automatic provider switching between development and production.
"""

import os
from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Environment types for agent execution."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    STAGING = "staging"


class Config(BaseSettings):
    """
    Application configuration with environment-based settings.

    Configuration priority:
    1. Environment variables
    2. Variables from .env file
    3. Default field values

    Example .env file:
        AGENT_WORKSHOP_ENV=development
        CLAUDE_MODEL=sonnet
        LANGFUSE_PUBLIC_KEY=pk-lf-...
        LANGFUSE_SECRET_KEY=sk-lf-...
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    agent_workshop_env: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Runtime environment (development, staging, production)",
    )

    # Claude Agent SDK settings (for development)
    claude_sdk_enabled: bool = Field(
        default=True,
        description="Enable Claude Agent SDK for development",
    )
    claude_model: Literal["opus", "sonnet", "haiku"] = Field(
        default="sonnet",
        description="Claude model variant to use",
    )

    # Anthropic API settings (for production)
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for production use",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Full Anthropic model identifier",
    )
    anthropic_max_tokens: int = Field(
        default=4096,
        description="Maximum tokens for Anthropic API responses",
    )

    # OpenAI settings (future support)
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key (optional alternative provider)",
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model to use",
    )

    # Langfuse observability settings
    langfuse_enabled: bool = Field(
        default=True,
        description="Enable Langfuse tracing",
    )
    langfuse_public_key: str | None = Field(
        default=None,
        description="Langfuse public API key",
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        description="Langfuse secret API key",
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse instance URL",
    )
    langfuse_debug: bool = Field(
        default=False,
        description="Enable Langfuse debug logging",
    )
    langfuse_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for traces (0.0-1.0)",
    )

    # LangGraph settings
    langgraph_checkpointer: Literal["memory", "postgres", "sqlite"] = Field(
        default="memory",
        description="Checkpointer backend for LangGraph workflows",
    )
    langgraph_postgres_url: str | None = Field(
        default=None,
        description="PostgreSQL connection URL for LangGraph checkpointing",
    )

    # General settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    @model_validator(mode="after")
    def validate_langfuse_credentials(self):
        """Validate Langfuse credentials if Langfuse is enabled."""
        import warnings

        if self.langfuse_enabled:
            missing_credentials = []
            if not self.langfuse_public_key:
                missing_credentials.append("LANGFUSE_PUBLIC_KEY")
            if not self.langfuse_secret_key:
                missing_credentials.append("LANGFUSE_SECRET_KEY")

            if missing_credentials:
                warning_msg = (
                    f"Langfuse is enabled but missing credentials: {', '.join(missing_credentials)}. "
                    f"Observability will be disabled. Set these environment variables or disable "
                    f"Langfuse with LANGFUSE_ENABLED=false"
                )
                warnings.warn(warning_msg, UserWarning, stacklevel=2)
                # Disable Langfuse if credentials are missing to avoid repeated errors
                self.langfuse_enabled = False

        return self

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.agent_workshop_env == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.agent_workshop_env == Environment.PRODUCTION

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.agent_workshop_env == Environment.STAGING

    def get_provider_type(self) -> str:
        """
        Determine which LLM provider to use based on environment.

        Returns:
            Provider type: "claude_sdk", "anthropic", or "openai"
        """
        if self.is_development and self.claude_sdk_enabled:
            return "claude_sdk"
        elif self.anthropic_api_key:
            return "anthropic"
        elif self.openai_api_key:
            return "openai"
        else:
            raise ValueError(
                "No valid provider configuration found. "
                "Set ANTHROPIC_API_KEY or enable Claude SDK for development."
            )

    def get_provider_config(self) -> dict:
        """
        Get provider-specific configuration.

        Returns:
            Configuration dictionary for the active provider
        """
        provider_type = self.get_provider_type()

        if provider_type == "claude_sdk":
            return {
                "model": self.claude_model,
                "type": "claude_sdk",
            }
        elif provider_type == "anthropic":
            return {
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "max_tokens": self.anthropic_max_tokens,
                "type": "anthropic",
            }
        elif provider_type == "openai":
            return {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "type": "openai",
            }
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")


@lru_cache
def get_config() -> Config:
    """
    Get cached configuration instance.

    Uses lru_cache to avoid repeated .env file reads.
    Clear cache with get_config.cache_clear() if needed.

    Returns:
        Cached Config instance
    """
    # Check for environment-specific .env file
    env = os.getenv("AGENT_WORKSHOP_ENV", "development")
    env_file = f".env.{env}"

    if os.path.exists(env_file):
        return Config(_env_file=env_file)

    return Config()
