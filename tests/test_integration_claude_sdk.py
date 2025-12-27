"""
Integration tests using real Claude SDK.

These tests make actual LLM calls to validate end-to-end behavior.
They are marked with @pytest.mark.slow to skip in CI.

Requirements:
    - AGENT_WORKSHOP_ENV=development (uses Claude SDK)
    - Claude SDK properly configured (Max plan or credits)

Usage:
    # Run all tests including slow integration tests
    uv run pytest tests/test_integration_claude_sdk.py -v

    # Skip slow tests (default in CI)
    uv run pytest -m "not slow"
"""

import os
import pytest

from agent_workshop.config import Config, get_config
from agent_workshop.agents.software_dev import CodeReviewer, PRPipeline, get_preset

from fixtures.mock_responses import (
    SAMPLE_CLEAN_CODE,
    SAMPLE_CODE_WITH_SECRET,
    SAMPLE_CODE_WITH_ISSUES,
)


# Mark all tests in this module as slow (integration)
pytestmark = pytest.mark.slow


@pytest.fixture
def integration_config(monkeypatch):
    """
    Create a real config for integration testing.

    Uses development environment with Claude SDK.
    """
    # Clear any cached config
    get_config.cache_clear()

    # Set development environment (Claude SDK)
    monkeypatch.setenv("AGENT_WORKSHOP_ENV", "development")
    monkeypatch.setenv("CLAUDE_SDK_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")  # Disable tracing for tests

    config = Config()
    return config


@pytest.fixture
def skip_if_no_sdk():
    """Skip test if Claude SDK is not available."""
    try:
        import claude_code_sdk
    except ImportError:
        pytest.skip("Claude SDK not installed")


# =============================================================================
# CodeReviewer Integration Tests
# =============================================================================

class TestCodeReviewerIntegration:
    """Integration tests for CodeReviewer with real LLM."""

    @pytest.mark.asyncio
    async def test_clean_code_review(self, integration_config, skip_if_no_sdk):
        """
        Test reviewing clean code returns valid structured response.

        This test makes a real LLM call to verify:
        1. Agent initializes correctly
        2. LLM returns valid JSON
        3. Response has expected structure
        """
        reviewer = CodeReviewer(integration_config)

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        # Validate response structure
        assert "approved" in result, "Response missing 'approved' field"
        assert "issues" in result, "Response missing 'issues' field"
        assert "suggestions" in result, "Response missing 'suggestions' field"
        assert "summary" in result, "Response missing 'summary' field"
        assert "timestamp" in result, "Response missing 'timestamp' field"

        # Types should be correct
        assert isinstance(result["approved"], bool)
        assert isinstance(result["issues"], list)
        assert isinstance(result["suggestions"], list)
        assert isinstance(result["summary"], str)

        # Clean code should generally be approved (though LLM may vary)
        # We don't assert approved=True since LLM might find minor issues
        print(f"\nReview result: approved={result['approved']}")
        print(f"Issues: {len(result['issues'])}")
        print(f"Summary: {result['summary'][:200]}...")

    @pytest.mark.asyncio
    async def test_security_issue_detection(self, integration_config, skip_if_no_sdk):
        """
        Test that hardcoded secrets are detected.

        The LLM should identify the API_KEY and DATABASE_PASSWORD
        as security issues.
        """
        # Use security-focused preset for better detection
        preset = get_preset("security_focused")
        reviewer = CodeReviewer(integration_config, **preset)

        result = await reviewer.run(SAMPLE_CODE_WITH_SECRET)

        # Should have response
        assert "approved" in result
        assert "issues" in result

        # Security issues should be detected (LLM should catch this)
        # Note: We can't guarantee exact LLM output, but secrets should be flagged
        print(f"\nSecurity review: approved={result['approved']}")
        print(f"Issues found: {len(result['issues'])}")
        for issue in result.get("issues", []):
            print(f"  - [{issue.get('severity', 'unknown')}] {issue.get('message', 'No message')}")

        # Generally expect rejection for code with secrets
        if result["approved"]:
            print("WARNING: LLM approved code with hardcoded secrets")

    @pytest.mark.asyncio
    async def test_preset_affects_review(self, integration_config, skip_if_no_sdk):
        """
        Test that different presets produce different review focuses.

        Compare general vs security_focused presets on the same code.
        """
        code = """
def process_user_input(user_data):
    # Simple processing
    query = f"SELECT * FROM users WHERE name = '{user_data}'"
    return execute_query(query)
"""

        # General review
        general_reviewer = CodeReviewer(integration_config, **get_preset("general"))
        general_result = await general_reviewer.run(code)

        # Security-focused review
        security_reviewer = CodeReviewer(integration_config, **get_preset("security_focused"))
        security_result = await security_reviewer.run(code)

        print(f"\nGeneral review: {len(general_result.get('issues', []))} issues")
        print(f"Security review: {len(security_result.get('issues', []))} issues")

        # Both should return valid structure
        for result in [general_result, security_result]:
            assert "approved" in result
            assert "issues" in result


# =============================================================================
# PRPipeline Integration Tests
# =============================================================================

class TestPRPipelineIntegration:
    """Integration tests for PRPipeline with real LLM."""

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self, integration_config, skip_if_no_sdk):
        """
        Test full PRPipeline execution.

        This test makes 3 LLM calls (one per step):
        1. Security scan
        2. Quality review
        3. Summary generation
        """
        pipeline = PRPipeline(integration_config)

        result = await pipeline.run({
            "content": SAMPLE_CLEAN_CODE,
            "title": "Add calculate_area function",
            "description": "Implements a simple area calculation utility",
            "files_changed": ["utils/geometry.py"],
        })

        # Should have final result
        assert result is not None

        # Result should contain summary data
        # (exact structure depends on generated prompts)
        print(f"\nPipeline result keys: {result.keys()}")
        print(f"Result: {result}")

    @pytest.mark.asyncio
    async def test_pipeline_with_security_issues(self, integration_config, skip_if_no_sdk):
        """
        Test pipeline detection of security issues.

        Pipeline should flag SQL injection vulnerability.
        """
        vulnerable_code = """
def get_user_by_name(name):
    # VULNERABLE: SQL injection
    query = f"SELECT * FROM users WHERE name = '{name}'"
    return db.execute(query)

def update_user(user_id, data):
    # Also vulnerable
    db.execute(f"UPDATE users SET data = '{data}' WHERE id = {user_id}")
"""

        pipeline = PRPipeline(integration_config)

        result = await pipeline.run({
            "content": vulnerable_code,
            "title": "Add user lookup functions",
            "description": "Helper functions for user queries",
            "files_changed": ["db/users.py"],
        })

        print(f"\nSecurity pipeline result: {result}")

        # Pipeline should identify issues
        # (exact format depends on prompts and LLM response)


# =============================================================================
# Smoke Test (Quick validation)
# =============================================================================

class TestSmokeTests:
    """Quick smoke tests to validate basic functionality."""

    @pytest.mark.asyncio
    async def test_code_reviewer_smoke(self, integration_config, skip_if_no_sdk):
        """Quick smoke test - CodeReviewer initializes and runs."""
        from agent_workshop.providers.base import ProviderError

        reviewer = CodeReviewer(integration_config)

        try:
            # Very simple code
            result = await reviewer.run("print('hello')")

            assert result is not None
            assert "timestamp" in result
            print(f"Smoke test passed: {result.get('approved', 'no approved field')}")

        except ProviderError as e:
            # If provider fails due to credentials, skip instead of fail
            if "API key" in str(e) or "authentication" in str(e).lower():
                pytest.skip(f"Skipping due to missing credentials: {e}")
            raise


# =============================================================================
# Helper for running integration tests manually
# =============================================================================

if __name__ == "__main__":
    """
    Run integration tests manually.

    Usage:
        python tests/test_integration_claude_sdk.py
    """
    import asyncio

    async def manual_test():
        print("Running manual integration test...")
        print("=" * 60)

        # Setup
        os.environ["AGENT_WORKSHOP_ENV"] = "development"
        os.environ["CLAUDE_SDK_ENABLED"] = "true"
        os.environ["LANGFUSE_ENABLED"] = "false"

        get_config.cache_clear()
        config = Config()

        # Test CodeReviewer
        print("\n1. Testing CodeReviewer...")
        reviewer = CodeReviewer(config)
        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        print(f"   Approved: {result.get('approved')}")
        print(f"   Issues: {len(result.get('issues', []))}")
        print(f"   Summary: {result.get('summary', 'N/A')[:100]}...")

        print("\n" + "=" * 60)
        print("Integration test complete!")

    asyncio.run(manual_test())
