"""
Pytest configuration for agent-workshop tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    """
    Isolate environment variables for each test.

    This prevents tests from affecting each other through env vars.
    """
    # Store original environment
    original_env = dict(os.environ)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def clean_env(monkeypatch):
    """
    Provide a clean environment with no Langfuse/Agent Workshop vars.

    Use this fixture when you want to start with a completely clean slate.
    """
    langfuse_vars = [
        "LANGFUSE_ENABLED",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_DEBUG",
    ]

    agent_vars = [
        "AGENT_WORKSHOP_ENV",
        "CLAUDE_SDK_ENABLED",
        "CLAUDE_MODEL",
        "ANTHROPIC_API_KEY",
    ]

    for var in langfuse_vars + agent_vars:
        monkeypatch.delenv(var, raising=False)

    return monkeypatch
