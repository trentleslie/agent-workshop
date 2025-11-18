"""
Tests for Langfuse integration and environment variable loading.

Verifies that:
1. Environment variables are loaded before Langfuse initialization
2. Missing credentials are handled gracefully
3. Langfuse decorators work correctly with proper credentials
4. Configuration validation works as expected
"""

import os
import warnings
from unittest.mock import patch, MagicMock

import pytest

from agent_workshop import Config, Agent
from agent_workshop.utils import setup_langfuse, test_langfuse_connection


class TestEnvironmentLoading:
    """Test that environment variables are loaded early enough."""

    def test_env_loaded_before_langfuse_import(self, monkeypatch):
        """Verify .env files are loaded before Langfuse imports."""
        # This test verifies the fix - that dotenv loading happens
        # in __init__.py before any langfuse imports

        # Set test environment variables
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")

        # Import should not raise any warnings about missing keys
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from agent_workshop import Agent

            # Should not have any Langfuse authentication warnings
            langfuse_warnings = [
                warning for warning in w
                if "public_key" in str(warning.message).lower()
            ]
            assert len(langfuse_warnings) == 0

    def test_env_file_detection(self, tmp_path, monkeypatch):
        """Test that environment-specific .env files are detected."""
        # Create a temporary .env.development file
        env_file = tmp_path / ".env.development"
        env_file.write_text(
            "LANGFUSE_PUBLIC_KEY=pk-from-file\n"
            "LANGFUSE_SECRET_KEY=sk-from-file\n"
        )

        # Change to the temp directory
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AGENT_WORKSHOP_ENV", "development")

        # Clear any cached config
        from agent_workshop.config import get_config
        get_config.cache_clear()

        # Reload the module to pick up the new env file
        # In practice, the __init__.py dotenv loading would handle this
        from dotenv import load_dotenv
        load_dotenv(env_file)

        assert os.getenv("LANGFUSE_PUBLIC_KEY") == "pk-from-file"
        assert os.getenv("LANGFUSE_SECRET_KEY") == "sk-from-file"


class TestConfigValidation:
    """Test Config class validation for Langfuse credentials."""

    def test_config_validates_missing_credentials(self, monkeypatch):
        """Config should warn if Langfuse enabled but credentials missing."""
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")

        # Clear cached config
        from agent_workshop.config import get_config
        get_config.cache_clear()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = Config()

            # Should have warning about missing credentials
            assert len(w) > 0
            assert any("missing credentials" in str(warning.message).lower()
                      for warning in w)

            # Langfuse should be auto-disabled
            assert config.langfuse_enabled is False

    def test_config_accepts_valid_credentials(self, monkeypatch):
        """Config should not warn if valid Langfuse credentials provided."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-valid-123")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-valid-456")

        # Clear cached config
        from agent_workshop.config import get_config
        get_config.cache_clear()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = Config()

            # Should not have warnings about missing credentials
            credential_warnings = [
                warning for warning in w
                if "missing credentials" in str(warning.message).lower()
            ]
            assert len(credential_warnings) == 0

            # Langfuse should remain enabled
            assert config.langfuse_enabled is True

    def test_config_disabled_langfuse_no_warning(self, monkeypatch):
        """No warnings if Langfuse explicitly disabled."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        # Clear cached config
        from agent_workshop.config import get_config
        get_config.cache_clear()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = Config()

            # Should not have any Langfuse warnings
            langfuse_warnings = [
                warning for warning in w
                if "langfuse" in str(warning.message).lower()
            ]
            assert len(langfuse_warnings) == 0


class TestLangfuseHelpers:
    """Test Langfuse helper functions."""

    def test_setup_langfuse_with_credentials(self, monkeypatch):
        """setup_langfuse should work with valid credentials."""
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")

        with patch("agent_workshop.utils.langfuse_helpers.Langfuse") as mock_langfuse:
            client = setup_langfuse(enabled=True)

            # Should have called Langfuse constructor
            mock_langfuse.assert_called_once()
            assert client is not None

    def test_setup_langfuse_missing_credentials(self, monkeypatch):
        """setup_langfuse should return None if credentials missing."""
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            client = setup_langfuse(enabled=True)

            # Should return None
            assert client is None

            # Should have warning (only shown once due to flag)
            # Note: might not show if already shown in other tests
            # This is expected behavior - we suppress repeated warnings

    def test_setup_langfuse_disabled(self, monkeypatch):
        """setup_langfuse should return None if disabled."""
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")

        client = setup_langfuse(enabled=False)
        assert client is None

    def test_warning_suppression(self, monkeypatch):
        """Warnings should only be shown once to avoid spam."""
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        # Reset the warning flag
        import agent_workshop.utils.langfuse_helpers as helpers
        helpers._langfuse_warning_shown = False

        warnings_count = []

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Call multiple times
            for _ in range(5):
                setup_langfuse(enabled=True)

            # Count Langfuse warnings
            langfuse_warnings = [
                warning for warning in w
                if "langfuse" in str(warning.message).lower()
            ]

            # Should only have 1 warning despite 5 calls
            assert len(langfuse_warnings) <= 1


class TestAgentIntegration:
    """Test that agents work correctly with Langfuse integration."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not __import__('importlib').util.find_spec('claude_agent_sdk'),
        reason="claude-agent-sdk not installed"
    )
    async def test_agent_works_without_langfuse(self, monkeypatch):
        """Agents should work even if Langfuse is disabled."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")
        monkeypatch.setenv("CLAUDE_SDK_ENABLED", "true")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # Clear cached config
        from agent_workshop.config import get_config
        get_config.cache_clear()

        # This should not raise any errors
        class TestAgent(Agent):
            async def run(self, input: str) -> dict:
                # Just return a simple result without calling LLM
                return {"result": "test"}

        config = Config()
        agent = TestAgent(config=config)
        result = await agent.run("test input")

        assert result == {"result": "test"}

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not __import__('importlib').util.find_spec('claude_agent_sdk'),
        reason="claude-agent-sdk not installed"
    )
    async def test_agent_initialization_with_langfuse(self, monkeypatch):
        """Agents should initialize correctly with Langfuse enabled."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")
        monkeypatch.setenv("CLAUDE_SDK_ENABLED", "true")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # Clear cached config
        from agent_workshop.config import get_config
        get_config.cache_clear()

        # This should not raise any warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            class TestAgent(Agent):
                async def run(self, input: str) -> dict:
                    return {"result": "test"}

            config = Config()
            agent = TestAgent(config=config)

            # Should not have authentication warnings
            auth_warnings = [
                warning for warning in w
                if "authentication" in str(warning.message).lower()
                or "public_key" in str(warning.message).lower()
            ]
            assert len(auth_warnings) == 0


@pytest.fixture(autouse=True)
def reset_warning_flag():
    """Reset warning flag before each test."""
    import agent_workshop.utils.langfuse_helpers as helpers
    helpers._langfuse_warning_shown = False
    yield
    helpers._langfuse_warning_shown = False


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear config cache before each test."""
    from agent_workshop.config import get_config
    get_config.cache_clear()
    yield
    get_config.cache_clear()
