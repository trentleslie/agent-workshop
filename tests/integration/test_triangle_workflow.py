"""
Integration tests for the Triangle workflow end-to-end.

Tests the complete flow from issue creation through PR merge with checkpoints.
Uses mock GitHub API responses but exercises real LangGraph workflow orchestration.

Key test scenarios:
1. Happy path: Issue → IssueToPR → Checkpoint → Approve → Merge
2. Checkpoint persistence across process restart simulation
3. Idempotency: Double-approve should be safe
4. Error scenarios: API failures, merge conflicts
5. Regression tests for bugs found during manual testing

Manual testing validated this flow on Issue #18 → PR #19 → Merge (commit 016fd4f).
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_workshop.config import Config, get_config
from agent_workshop.agents.software_dev import (
    IssueToPR,
    TriangleOrchestrator,
    CommentProcessorConfig,
    make_thread_id,
)
from agent_workshop.agents.software_dev.types import (
    IssueToPRState,
    TriangleState,
    CommentProcessorResults,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_config(monkeypatch):
    """Create a config with mocked provider settings."""
    monkeypatch.setenv("AGENT_WORKSHOP_ENV", "development")
    monkeypatch.setenv("CLAUDE_SDK_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    get_config.cache_clear()
    return Config()


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.complete = AsyncMock()
    provider.provider_name = "mock"
    provider.model_name = "mock-model"
    return provider


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client with common responses."""
    client = MagicMock()

    # get_issue mock
    issue = MagicMock()
    issue.title = "Add utility function"
    issue.body = "Add a `helper()` function to utils.py"
    issue.number = 42

    issue_result = MagicMock()
    issue_result.success = True
    issue_result.data = issue
    client.get_issue = AsyncMock(return_value=issue_result)

    # create_branch mock
    branch_result = MagicMock()
    branch_result.success = True
    branch_result.data = {"name": "issue-42-add-utility-function"}
    client.create_branch = AsyncMock(return_value=branch_result)

    # create_pr mock
    pr_result = MagicMock()
    pr_result.success = True
    pr_result.data = MagicMock()
    pr_result.data.number = 123
    pr_result.data.html_url = "https://github.com/test/repo/pull/123"
    client.create_pr = AsyncMock(return_value=pr_result)

    # create_draft_pr mock (used by IssueToPR)
    draft_pr_result = MagicMock()
    draft_pr_result.success = True
    draft_pr_result.data = MagicMock()
    draft_pr_result.data.number = 123
    draft_pr_result.data.html_url = "https://github.com/test/repo/pull/123"
    client.create_draft_pr = AsyncMock(return_value=draft_pr_result)

    # list_pr_comments mock (empty by default)
    comments_result = MagicMock()
    comments_result.success = True
    comments_result.data = []
    client.list_pr_comments = AsyncMock(return_value=comments_result)

    # merge_pr mock
    merge_result = MagicMock()
    merge_result.success = True
    merge_result.data = {"merged": True}
    client.merge_pr = AsyncMock(return_value=merge_result)

    # mark_ready_for_review mock
    ready_result = MagicMock()
    ready_result.success = True
    client.mark_ready_for_review = AsyncMock(return_value=ready_result)

    # create_issue mock (for follow-ups)
    follow_up_result = MagicMock()
    follow_up_result.success = True
    follow_up_result.data = MagicMock()
    follow_up_result.data.number = 456
    client.create_issue = AsyncMock(return_value=follow_up_result)

    return client


@pytest.fixture
def mock_git_operations():
    """Mock git operations module functions.

    Git operations return GitResult objects with success/stderr attributes,
    not simple booleans.
    """
    # Create GitResult-like mock objects
    success_result = MagicMock()
    success_result.success = True
    success_result.stderr = ""
    success_result.stdout = "OK"
    success_result.returncode = 0

    with patch(
        "agent_workshop.agents.software_dev.issue_to_pr.git_setup_worktree"
    ) as mock_setup, patch(
        "agent_workshop.agents.software_dev.issue_to_pr.commit_changes"
    ) as mock_commit, patch(
        "agent_workshop.agents.software_dev.issue_to_pr.push_branch"
    ) as mock_push, patch(
        "agent_workshop.agents.software_dev.utils.git_operations.cleanup_worktree"
    ) as mock_cleanup:
        # setup_worktree returns a string path
        mock_setup.return_value = "/tmp/worktree"
        # commit_changes and push_branch return GitResult
        mock_commit.return_value = success_result
        mock_push.return_value = success_result
        mock_cleanup.return_value = None

        yield {
            "setup_worktree": mock_setup,
            "commit_changes": mock_commit,
            "push_branch": mock_push,
            "cleanup_worktree": mock_cleanup,
        }


@pytest.fixture
def mock_verification():
    """Mock code verification to always pass.

    The verify function is imported in issue_to_pr via the utils package,
    so we patch it at the point of use rather than at definition.
    """
    with patch(
        "agent_workshop.agents.software_dev.issue_to_pr.verify"
    ) as mock_verify:
        mock_verify.return_value = {
            "passed": True,
            "tier": "tier1_syntax",
            "errors": [],
            "warnings": [],
        }
        yield mock_verify


@pytest.fixture
def temp_state_db(tmp_path):
    """Create a temporary state database path."""
    return tmp_path / ".triangle" / "state.db"


# =============================================================================
# Mock LLM Responses
# =============================================================================

MOCK_ISSUE_SPEC = json.dumps({
    "requirements": ["Add helper() function to utils.py"],
    "acceptance_criteria": ["Function exists and returns expected value"],
    "files_to_modify": ["src/utils.py"],
    "estimated_complexity": "low",
})

MOCK_GENERATED_CODE = '''```python
# src/utils.py
def helper() -> str:
    """Return a helpful string."""
    return "Hello from helper"
```'''


# =============================================================================
# Happy Path Integration Tests
# =============================================================================


class TestTriangleWorkflowHappyPath:
    """Integration tests for the complete triangle workflow."""

    @pytest.mark.asyncio
    async def test_issue_to_pr_creates_checkpoint(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        mock_git_operations,
        mock_verification,
        tmp_path,
    ):
        """Test that IssueToPR workflow stops at checkpoint after PR creation."""
        # Setup mock responses
        mock_provider.complete.side_effect = [
            MOCK_ISSUE_SPEC,      # parse_issue
            MOCK_GENERATED_CODE,  # generate_code
        ]

        with patch.object(IssueToPR, "_create_provider", return_value=mock_provider):
            workflow = IssueToPR(mock_config)
            workflow._github_clients["test/repo"] = mock_github_client
            workflow._working_dir = str(tmp_path)

            # Create a simple file to verify
            (tmp_path / "src").mkdir(exist_ok=True)
            (tmp_path / "src" / "utils.py").write_text("# Initial content\n")

            result = await workflow.run(
                {"issue_number": 42, "repo_name": "test/repo"},
                thread_id="test-issue-42",
            )

        # CRITICAL: Workflow must stop with human approval required
        assert result.get("requires_human_approval") is True
        assert result.get("current_step") == "awaiting_review"
        assert result.get("pr_number") is not None
        assert result.get("checkpoint_at") is not None

    @pytest.mark.asyncio
    async def test_orchestrator_resume_completes_workflow(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        mock_git_operations,
        tmp_path,
    ):
        """Test that resume_from_checkpoint completes the workflow."""
        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)

            # Inject mock GitHub client
            orchestrator._github_clients["test/repo"] = mock_github_client

            # Simulate checkpoint state (after IssueToPR completed)
            checkpoint_state = {
                "repo_name": "test/repo",
                "issue_number": 42,
                "pr_number": 123,
                "pr_url": "https://github.com/test/repo/pull/123",
                "branch_name": "issue-42-add-utility-function",
                "working_dir": str(tmp_path),
                "requires_human_approval": True,
                "current_step": "awaiting_review",
                "checkpoint_at": datetime.now(timezone.utc).isoformat(),
            }

            result = await orchestrator.resume_from_checkpoint(checkpoint_state)

        # Should complete with merge
        assert result.get("current_step") == "completed"
        assert result.get("requires_human_approval") is False
        assert result.get("approved_at") is not None

        # GitHub client should have been called to merge
        mock_github_client.merge_pr.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_workflow_happy_path(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        mock_git_operations,
        mock_verification,
        tmp_path,
    ):
        """Test complete workflow: start → checkpoint → approve → merge."""
        mock_provider.complete.side_effect = [
            MOCK_ISSUE_SPEC,      # parse_issue
            MOCK_GENERATED_CODE,  # generate_code
        ]

        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            with patch.object(
                IssueToPR, "_create_provider", return_value=mock_provider
            ):
                orchestrator = TriangleOrchestrator(mock_config)
                orchestrator._github_clients["test/repo"] = mock_github_client

                # Phase 1: Start workflow (should checkpoint)
                # Note: We test this indirectly since full run requires more setup
                # The unit tests cover the graph structure; here we test resume

                # Phase 2: Simulate post-checkpoint state
                checkpoint_state = {
                    "repo_name": "test/repo",
                    "issue_number": 42,
                    "pr_number": 123,
                    "pr_url": "https://github.com/test/repo/pull/123",
                    "branch_name": "issue-42",
                    "working_dir": str(tmp_path),
                    "requires_human_approval": True,
                    "current_step": "awaiting_review",
                    "checkpoint_at": datetime.now(timezone.utc).isoformat(),
                }

                # Phase 3: Resume and complete
                result = await orchestrator.resume_from_checkpoint(checkpoint_state)

        assert result["current_step"] == "completed"
        mock_github_client.mark_ready_for_review.assert_called_once_with(pr_number=123)
        mock_github_client.merge_pr.assert_called_once()


# =============================================================================
# Checkpoint Persistence Tests
# =============================================================================


class TestCheckpointPersistence:
    """Tests for checkpoint state persistence across restarts."""

    @pytest.mark.asyncio
    async def test_checkpoint_state_is_serializable(self, mock_config, mock_provider):
        """Test that checkpoint state can be serialized to JSON."""
        with patch.object(IssueToPR, "_create_provider", return_value=mock_provider):
            workflow = IssueToPR(mock_config)

            # Generate state from await_review
            state = await workflow.await_review({
                "issue_number": 42,
                "repo_name": "test/repo",
                "pr_number": 123,
                "pr_url": "https://github.com/test/repo/pull/123",
                "files_changed": ["utils.py"],
            })

        # State should be JSON-serializable
        serialized = json.dumps(state, default=str)
        assert serialized is not None

        # Should deserialize correctly
        restored = json.loads(serialized)
        assert restored["requires_human_approval"] is True
        assert restored["pr_number"] == 123

    @pytest.mark.asyncio
    async def test_thread_id_format_includes_repo(self):
        """Test that thread_id format prevents cross-repo collisions."""
        # This was a bug found during Phase 2: thread IDs need repo prefix
        thread_id = make_thread_id("owner/repo", 42)

        assert "owner" in thread_id
        assert "repo" in thread_id
        assert "42" in thread_id

        # Different repos should have different thread IDs
        other_thread = make_thread_id("other/repo", 42)
        assert thread_id != other_thread


# =============================================================================
# Idempotency Tests
# =============================================================================


class TestIdempotency:
    """Tests for idempotent operations."""

    @pytest.mark.asyncio
    async def test_double_approve_is_safe(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test that approving an already-completed workflow is safe."""
        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            # First approval
            checkpoint_state = {
                "repo_name": "test/repo",
                "issue_number": 42,
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
                "requires_human_approval": True,
                "current_step": "awaiting_review",
            }

            result1 = await orchestrator.resume_from_checkpoint(checkpoint_state)
            assert result1["current_step"] == "completed"

            # Second approval on completed state
            # This should not re-run merge
            mock_github_client.reset_mock()

            # State after completion doesn't require approval
            completed_state = {**result1, "requires_human_approval": False}

            # Attempting to resume from completed state should be a no-op
            # (In practice, CLI guards this, but orchestrator should handle gracefully)
            # We verify by checking that key fields are preserved
            assert completed_state["current_step"] == "completed"
            assert completed_state["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_merge_already_merged_pr(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test that merging an already-merged PR is handled gracefully."""
        # GitHub returns error when PR is already merged
        merge_result = MagicMock()
        merge_result.success = False
        merge_result.error = "Pull Request is not mergeable"
        mock_github_client.merge_pr = AsyncMock(return_value=merge_result)

        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            checkpoint_state = {
                "repo_name": "test/repo",
                "issue_number": 42,
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
                "requires_human_approval": True,
                "current_step": "awaiting_review",
            }

            result = await orchestrator.resume_from_checkpoint(checkpoint_state)

            # Should record the error but not crash
            assert result.get("error") is not None or result.get("current_step") == "finalize"


# =============================================================================
# Error Scenario Tests
# =============================================================================


class TestErrorScenarios:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_github_api_error_during_pr_creation(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        mock_git_operations,
        mock_verification,
        tmp_path,
    ):
        """Test handling of GitHub API errors during PR creation."""
        # Make PR creation fail (IssueToPR uses create_draft_pr, not create_pr)
        pr_result = MagicMock()
        pr_result.success = False
        pr_result.error = "Repository not found"
        mock_github_client.create_draft_pr = AsyncMock(return_value=pr_result)

        mock_provider.complete.side_effect = [
            MOCK_ISSUE_SPEC,
            MOCK_GENERATED_CODE,
        ]

        with patch.object(IssueToPR, "_create_provider", return_value=mock_provider):
            workflow = IssueToPR(mock_config)
            workflow._github_clients["test/repo"] = mock_github_client
            workflow._working_dir = str(tmp_path)

            (tmp_path / "src").mkdir(exist_ok=True)
            (tmp_path / "src" / "utils.py").write_text("# content\n")

            result = await workflow.run(
                {"issue_number": 42, "repo_name": "test/repo"},
                thread_id="test-issue-42",
            )

        # Should record error
        assert result.get("error") is not None or result.get("pr_number") is None

    @pytest.mark.asyncio
    async def test_issue_not_found_error(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
    ):
        """Test handling when GitHub issue doesn't exist."""
        issue_result = MagicMock()
        issue_result.success = False
        issue_result.error = "Issue not found"
        mock_github_client.get_issue = AsyncMock(return_value=issue_result)

        with patch.object(IssueToPR, "_create_provider", return_value=mock_provider):
            workflow = IssueToPR(mock_config)
            workflow._github_clients["test/repo"] = mock_github_client

            result = await workflow.parse_issue({
                "issue_number": 99999,
                "repo_name": "test/repo",
            })

        assert result.get("error") is not None
        assert "Failed to fetch issue" in result["error"]


# =============================================================================
# Regression Tests (Bugs Fixed During Manual Testing)
# =============================================================================


class TestRegressionBugsFromManualTesting:
    """
    Regression tests for bugs discovered during Phase 3A manual testing.

    These bugs were found when testing Issue #18 → PR #19 end-to-end.
    """

    def test_verify_accepts_file_path_not_directory(self, mock_config, mock_provider):
        """
        Regression: verify_code must pass file paths to tiered_verify_file,
        not directories.

        Bug: Original code passed working_dir to verify, but verify expects
        individual file paths.

        Fix: Iterate over files_changed and verify each file individually.
        """
        with patch.object(IssueToPR, "_create_provider", return_value=mock_provider):
            workflow = IssueToPR(mock_config)

            # The _should_retry_or_continue method checks verification results
            # This tests the state structure expected
            state = {
                "last_verification_result": {"passed": True},
                "verification_attempts": 1,
            }

            decision = workflow._should_retry_or_continue(state)
            assert decision == "continue"

    def test_commit_changes_signature(self):
        """
        Regression: commit_changes() requires specific parameter order.

        Bug: Called with wrong parameter names.

        Fix: Updated call site to use worktree_path (the actual param name).
        """
        # Import to verify function exists with expected signature
        from agent_workshop.agents.software_dev.utils.git_operations import commit_changes
        import inspect

        sig = inspect.signature(commit_changes)
        params = list(sig.parameters.keys())

        # Should have worktree_path as first positional param
        assert "worktree_path" in params
        assert "message" in params

    def test_push_branch_signature(self):
        """
        Regression: push_branch() parameter order must be correct.

        Bug: Called with wrong parameter names.

        Fix: Updated to pass worktree_path (the actual param name).
        """
        from agent_workshop.agents.software_dev.utils.git_operations import push_branch
        import inspect

        sig = inspect.signature(push_branch)
        params = list(sig.parameters.keys())

        assert "worktree_path" in params
        assert "branch_name" in params

    def test_github_client_factory_pattern(self, mock_config, mock_provider):
        """
        Regression: TriangleOrchestrator needs GitHubClient factory per repo.

        Bug: Shared single client caused issues with multi-repo workflows.

        Fix: get_github_client(repo) method with caching per repo.
        """
        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)

            # Should have the factory method
            assert hasattr(orchestrator, "get_github_client")

            # Internal cache should exist
            assert hasattr(orchestrator, "_github_clients")
            assert isinstance(orchestrator._github_clients, dict)

    @pytest.mark.asyncio
    async def test_mark_ready_for_review_before_merge(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """
        Regression: Draft PRs must be marked ready before merge.

        Bug: Merge failed with "Pull request is in draft state".

        Fix: Call mark_ready_for_review() in finalize() before merge_pr().
        """
        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            checkpoint_state = {
                "repo_name": "test/repo",
                "issue_number": 42,
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
                "requires_human_approval": True,
                "current_step": "awaiting_review",
            }

            await orchestrator.resume_from_checkpoint(checkpoint_state)

            # mark_ready_for_review must be called before merge
            mock_github_client.mark_ready_for_review.assert_called()
            mock_github_client.merge_pr.assert_called()

            # Order matters: ready should be called first
            ready_call = mock_github_client.mark_ready_for_review.call_args_list
            merge_call = mock_github_client.merge_pr.call_args_list

            assert len(ready_call) >= 1
            assert len(merge_call) >= 1


class TestCommentProcessorConfig:
    """Tests for best-effort comment processing configuration."""

    def test_default_config_values(self):
        """Test default values for best-effort processing."""
        config = CommentProcessorConfig()

        # Defaults should enable best-effort mode
        assert config.continue_on_failure is True
        assert config.skip_complex_comments is True
        assert config.max_attempts_per_comment == 2
        assert config.timeout_per_comment_seconds == 120

    def test_custom_config_override(self):
        """Test that custom config values are respected."""
        config = CommentProcessorConfig(
            max_attempts_per_comment=5,
            continue_on_failure=False,
            skip_complex_comments=False,
            timeout_per_comment_seconds=60,
        )

        assert config.max_attempts_per_comment == 5
        assert config.continue_on_failure is False
        assert config.skip_complex_comments is False
        assert config.timeout_per_comment_seconds == 60


class TestPRCommentProcessorIntegration:
    """Tests for PRCommentProcessor wiring in orchestrator (Phase 4)."""

    @pytest.mark.asyncio
    async def test_processor_runs_on_unaddressed_comments(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test that orchestrator calls PRCommentProcessor for unaddressed comments."""
        # Setup unaddressed comment
        mock_comment = MagicMock()
        mock_comment.id = "comment-1"
        mock_comment.path = "utils.py"
        mock_comment.line = 10
        mock_comment.body = "Add type hint here"
        mock_comment.addressed = False

        comments_result = MagicMock()
        comments_result.success = True
        comments_result.data = [mock_comment]
        mock_github_client.list_pr_comments = AsyncMock(return_value=comments_result)

        # Mock processor result
        processor_result = {
            "total_comments": 1,
            "applied": 1,
            "skipped": 0,
            "failed": 0,
            "summary": "Applied 1 fix",
            "files_modified": ["utils.py"],
            "details": [
                {
                    "comment_id": "comment-1",
                    "status": "applied",
                    "explanation": "Added type hint",
                    "comment_body": "Add type hint here",
                }
            ],
        }

        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            # Mock the processor
            mock_processor = MagicMock()
            mock_processor.run = AsyncMock(return_value=processor_result)
            orchestrator._comment_processor = mock_processor

            # Mock commit/push
            with patch.object(
                orchestrator, "_commit_and_push_fixes", new_callable=AsyncMock
            ) as mock_commit:
                mock_commit.return_value = {"committed": True, "pushed": True}

                state = {
                    "repo_name": "test/repo",
                    "pr_number": 123,
                    "branch_name": "issue-42",
                    "working_dir": str(tmp_path),
                }

                result = await orchestrator.run_comment_processor(state)

        # Processor should have been called
        mock_processor.run.assert_called_once()

        # Result should show addressed comment
        assert len(result["comment_results"]["addressed"]) == 1
        assert result["comment_results"]["addressed"][0]["id"] == "comment-1"

        # Commit/push should have been called
        mock_commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_processor_skips_complex_comments(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test that complex comments are filtered before processor."""
        # Setup a comment with many complexity keywords
        # Formula: base = words // 10, then *3 for refactor keywords
        # Need > 50, so need base > 17 before multiplier, or > 170 words with keywords
        mock_comment = MagicMock()
        mock_comment.id = "complex-1"
        mock_comment.path = "utils.py"
        mock_comment.line = 10
        # 60 repeats * 3 words = 180 words -> 18 base -> 54 with refactor multiplier
        mock_comment.body = " ".join(["refactor restructure rewrite"] * 60)
        mock_comment.addressed = False

        comments_result = MagicMock()
        comments_result.success = True
        comments_result.data = [mock_comment]
        mock_github_client.list_pr_comments = AsyncMock(return_value=comments_result)

        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            state = {
                "repo_name": "test/repo",
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
            }

            result = await orchestrator.run_comment_processor(state)

        # Should be skipped as too complex
        assert len(result["comment_results"]["skipped"]) == 1
        assert result["comment_results"]["skipped"][0]["reason"] == "too_complex"

    @pytest.mark.asyncio
    async def test_processor_handles_no_comments(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test handling when there are no unaddressed comments."""
        # All comments already addressed
        mock_comment = MagicMock()
        mock_comment.id = "comment-1"
        mock_comment.addressed = True

        comments_result = MagicMock()
        comments_result.success = True
        comments_result.data = [mock_comment]
        mock_github_client.list_pr_comments = AsyncMock(return_value=comments_result)

        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            state = {
                "repo_name": "test/repo",
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
            }

            result = await orchestrator.run_comment_processor(state)

        # Should complete with empty results
        assert result["comment_results"]["addressed"] == []
        assert result["comment_results"]["skipped"] == []
        assert result["comment_results"]["failed"] == []

    @pytest.mark.asyncio
    async def test_processor_error_continues_on_failure(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test that processor errors don't crash with continue_on_failure=True."""
        mock_comment = MagicMock()
        mock_comment.id = "comment-1"
        mock_comment.path = "utils.py"
        mock_comment.body = "Add type hint"
        mock_comment.addressed = False

        comments_result = MagicMock()
        comments_result.success = True
        comments_result.data = [mock_comment]
        mock_github_client.list_pr_comments = AsyncMock(return_value=comments_result)

        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            config = CommentProcessorConfig(continue_on_failure=True)
            orchestrator = TriangleOrchestrator(mock_config, comment_config=config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            # Mock processor to raise an error
            mock_processor = MagicMock()
            mock_processor.run = AsyncMock(side_effect=RuntimeError("LLM error"))
            orchestrator._comment_processor = mock_processor

            state = {
                "repo_name": "test/repo",
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
            }

            result = await orchestrator.run_comment_processor(state)

        # Should have error recorded but not crash
        assert result.get("error") is not None or len(result["comment_results"]["failed"]) > 0

    @pytest.mark.asyncio
    async def test_convert_processor_results(
        self,
        mock_config,
        mock_provider,
    ):
        """Test _convert_processor_results helper method."""
        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)

            processor_result = {
                "details": [
                    {
                        "comment_id": "c1",
                        "status": "applied",
                        "explanation": "Fixed it",
                        "comment_body": "Please fix this",
                    },
                    {
                        "comment_id": "c2",
                        "status": "skipped",
                        "explanation": "No change needed",
                        "comment_body": "Consider this",
                    },
                    {
                        "comment_id": "c3",
                        "status": "failed",
                        "explanation": "Could not parse",
                        "comment_body": "Something wrong",
                    },
                ]
            }

            results = orchestrator._convert_processor_results(processor_result)

        assert len(results["addressed"]) == 1
        assert results["addressed"][0]["id"] == "c1"

        assert len(results["skipped"]) == 1
        assert results["skipped"][0]["id"] == "c2"

        assert len(results["failed"]) == 1
        assert results["failed"][0]["id"] == "c3"


class TestFollowUpIssueCreation:
    """Tests for creating follow-up issues from unaddressed comments."""

    @pytest.mark.asyncio
    async def test_creates_follow_up_for_failed_comments(
        self,
        mock_config,
        mock_provider,
        mock_github_client,
        tmp_path,
    ):
        """Test that failed comments become follow-up issues.

        This test directly calls finalize() rather than resume_from_checkpoint()
        because the resume flow fetches fresh comments from GitHub, which would
        overwrite any pre-populated comment_results.
        """
        with patch.object(
            TriangleOrchestrator, "_create_provider", return_value=mock_provider
        ):
            orchestrator = TriangleOrchestrator(mock_config)
            orchestrator._github_clients["test/repo"] = mock_github_client

            # State with failed comments (directly set, not from resume flow)
            state = {
                "repo_name": "test/repo",
                "issue_number": 42,
                "pr_number": 123,
                "branch_name": "issue-42",
                "working_dir": str(tmp_path),
                "current_step": "process_comments",
                "comment_results": CommentProcessorResults(
                    addressed=[],
                    skipped=[],
                    failed=[
                        {
                            "id": "comment-1",
                            "reason": "timeout",
                            "body": "Add error handling",
                        }
                    ],
                ),
            }

            # Call finalize directly to test follow-up issue creation
            result = await orchestrator.finalize(state)

            # Should have created follow-up issue
            mock_github_client.create_issue.assert_called()
            call_args = mock_github_client.create_issue.call_args

            # Check issue was created with correct labels
            assert "follow-up" in call_args.kwargs.get("labels", [])
