"""
Langfuse integration utilities.

Provides helpers for setting up and managing Langfuse tracing.
"""

import os
import warnings
from typing import Any

from langfuse import Langfuse

# Track whether we've already shown the warning to avoid spam
_langfuse_warning_shown = False


def setup_langfuse(
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str = "https://cloud.langfuse.com",
    enabled: bool = True,
    debug: bool = False,
) -> Langfuse | None:
    """
    Set up Langfuse client for observability.

    Environment variables (if parameters not provided):
    - LANGFUSE_PUBLIC_KEY: Public API key
    - LANGFUSE_SECRET_KEY: Secret API key
    - LANGFUSE_HOST: Langfuse instance URL

    Args:
        public_key: Langfuse public API key
        secret_key: Langfuse secret API key
        host: Langfuse instance URL
        enabled: Whether to enable Langfuse
        debug: Enable debug logging

    Returns:
        Configured Langfuse client or None if disabled

    Example:
        ```python
        from agent_workshop.utils import setup_langfuse

        # Auto-configure from environment
        langfuse = setup_langfuse()

        # Or provide explicit credentials
        langfuse = setup_langfuse(
            public_key="pk-lf-...",
            secret_key="sk-lf-...",
        )
        ```
    """
    global _langfuse_warning_shown

    if not enabled:
        return None

    # Use provided keys or fall back to environment
    public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
    host = host or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        if not _langfuse_warning_shown:
            missing = []
            if not public_key:
                missing.append("LANGFUSE_PUBLIC_KEY")
            if not secret_key:
                missing.append("LANGFUSE_SECRET_KEY")

            warnings.warn(
                f"Langfuse is enabled but missing credentials: {', '.join(missing)}. "
                f"Observability will be disabled. Set these environment variables or disable "
                f"Langfuse with LANGFUSE_ENABLED=false",
                UserWarning,
                stacklevel=2,
            )
            _langfuse_warning_shown = True
        return None

    try:
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            debug=debug,
        )

        if debug:
            print(f"✓ Langfuse initialized successfully. Host: {host}")

        return client

    except Exception as e:
        if not _langfuse_warning_shown:
            warnings.warn(
                f"Failed to initialize Langfuse: {e}. Observability will be disabled.",
                UserWarning,
                stacklevel=2,
            )
            _langfuse_warning_shown = True
        return None


def create_trace(
    langfuse: Langfuse,
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
):
    """
    Create a new Langfuse trace.

    Args:
        langfuse: Langfuse client instance
        name: Trace name
        user_id: Optional user identifier
        session_id: Optional session identifier
        metadata: Optional metadata dictionary
        tags: Optional list of tags

    Returns:
        Trace object

    Example:
        ```python
        langfuse = setup_langfuse()
        trace = create_trace(
            langfuse,
            name="validation_workflow",
            user_id="user_123",
            tags=["production", "validation"],
        )
        ```
    """
    return langfuse.trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {},
        tags=tags or [],
    )


def test_langfuse_connection() -> bool:
    """
    Test Langfuse connection with current configuration.

    Returns:
        True if connection successful, False otherwise

    Example:
        ```python
        from agent_workshop.utils import test_langfuse_connection

        if test_langfuse_connection():
            print("✓ Langfuse configured correctly")
        else:
            print("✗ Langfuse connection failed")
        ```
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        print("✗ Missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY")
        return False

    try:
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

        # Create a test trace to verify connection
        test_trace = client.trace(name="connection_test")
        client.flush()  # Ensure the trace is sent

        print(f"✓ Langfuse connection successful (host: {host})")
        return True

    except Exception as e:
        print(f"✗ Langfuse connection failed: {e}")
        return False
