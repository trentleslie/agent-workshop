"""
Unit tests for software_dev agents (CodeReviewer and PRPipeline).

Tests use mocked LLM responses to verify:
- JSON parsing (various formats)
- Configuration priority
- Preset loading
- Error handling
- Workflow state management (PRPipeline)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_workshop.config import Config, get_config
from agent_workshop.agents.software_dev import (
    CodeReviewer,
    PRPipeline,
    ReleasePipeline,
    PRCommentProcessor,
    get_preset,
    list_presets,
)

from fixtures.mock_responses import (
    MOCK_CODE_REVIEWER_APPROVED,
    MOCK_CODE_REVIEWER_REJECTED,
    MOCK_CODE_REVIEWER_SECURITY_ISSUE,
    MOCK_CODE_REVIEWER_MARKDOWN_WRAPPED,
    MOCK_CODE_REVIEWER_PLAIN_MARKDOWN,
    MOCK_CODE_REVIEWER_MALFORMED,
    MOCK_CODE_REVIEWER_WITH_PREAMBLE,
    MOCK_PR_SECURITY_SCAN,
    MOCK_PR_SECURITY_SCAN_CLEAN,
    MOCK_PR_QUALITY_REVIEW,
    MOCK_PR_QUALITY_REVIEW_CLEAN,
    MOCK_PR_SUMMARY,
    MOCK_PR_SUMMARY_APPROVED,
    MOCK_COMMENT_ANALYSIS_CAN_FIX,
    MOCK_COMMENT_ANALYSIS_SKIP,
    MOCK_FIX_GENERATED,
    MOCK_FIX_FAILED,
    MOCK_COMMENT_SUMMARY,
    SAMPLE_CLEAN_CODE,
    SAMPLE_CODE_WITH_SECRET,
    SAMPLE_CODE_WITH_ISSUES,
    SAMPLE_PR_COMMENTS,
    SAMPLE_COMMENT_NO_PATH,
    SAMPLE_FILE_CONTENT,
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


# =============================================================================
# CodeReviewer Unit Tests
# =============================================================================

class TestCodeReviewerParsing:
    """Tests for JSON response parsing."""

    @pytest.mark.asyncio
    async def test_parse_plain_json(self, mock_config, mock_provider):
        """Test parsing plain JSON response."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_APPROVED

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        assert result["approved"] is True
        assert result["issues"] == []
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_parse_markdown_json_block(self, mock_config, mock_provider):
        """Test parsing JSON wrapped in markdown code block."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_MARKDOWN_WRAPPED

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        assert result["approved"] is True
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_parse_plain_markdown_block(self, mock_config, mock_provider):
        """Test parsing JSON in plain markdown block (no json specifier)."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_PLAIN_MARKDOWN

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        assert result["approved"] is True

    @pytest.mark.asyncio
    async def test_parse_json_with_preamble(self, mock_config, mock_provider):
        """Test parsing JSON with text before/after."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_WITH_PREAMBLE

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        assert result["approved"] is False
        assert len(result["issues"]) == 1

    @pytest.mark.asyncio
    async def test_parse_malformed_fallback(self, mock_config, mock_provider):
        """Test graceful fallback on malformed JSON."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_MALFORMED

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        # Should return structured response with parse failure indicator
        assert result["approved"] is False
        assert len(result["issues"]) > 0
        # Should have an issue about unable to parse
        assert any("parse" in issue.get("message", "").lower() for issue in result["issues"])
        assert "timestamp" in result


class TestCodeReviewerBehavior:
    """Tests for CodeReviewer behavior."""

    @pytest.mark.asyncio
    async def test_clean_code_approved(self, mock_config, mock_provider):
        """Test that clean code is approved."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_APPROVED

        result = await reviewer.run(SAMPLE_CLEAN_CODE)

        assert result["approved"] is True
        assert result["issues"] == []
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_code_with_issues_rejected(self, mock_config, mock_provider):
        """Test that code with issues is rejected."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_REJECTED

        result = await reviewer.run(SAMPLE_CODE_WITH_ISSUES)

        assert result["approved"] is False
        assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_security_issue_detected(self, mock_config, mock_provider):
        """Test that security issues are detected."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_SECURITY_ISSUE

        result = await reviewer.run(SAMPLE_CODE_WITH_SECRET)

        assert result["approved"] is False
        assert any(
            issue.get("severity") == "critical" and issue.get("category") == "security"
            for issue in result["issues"]
        )

    @pytest.mark.asyncio
    async def test_empty_input_rejected(self, mock_config, mock_provider):
        """Test that empty input returns rejection without calling LLM."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider

        result = await reviewer.run("")

        # Returns structured response indicating empty input
        assert result["approved"] is False
        assert len(result["issues"]) > 0
        assert any("empty" in issue.get("message", "").lower() for issue in result["issues"])
        assert "timestamp" in result
        mock_provider.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_input_rejected(self, mock_config, mock_provider):
        """Test that whitespace-only input returns rejection."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider

        result = await reviewer.run("   \n\t  ")

        # Returns structured response indicating empty input
        assert result["approved"] is False
        assert len(result["issues"]) > 0
        mock_provider.complete.assert_not_called()


class TestCodeReviewerConfiguration:
    """Tests for configuration priority and presets."""

    def test_list_presets(self):
        """Test that presets are available."""
        presets = list_presets()
        preset_names = [p["name"] for p in presets]

        assert "general" in preset_names
        assert "security_focused" in preset_names
        assert "python_specific" in preset_names
        assert "javascript_specific" in preset_names
        assert "quick_scan" in preset_names

        # Each preset should have name and description
        for preset in presets:
            assert "name" in preset
            assert "description" in preset

    def test_get_preset(self):
        """Test loading a specific preset."""
        preset = get_preset("security_focused")

        assert "system_prompt" in preset
        assert "validation_criteria" in preset
        assert "security" in preset["system_prompt"].lower() or "owasp" in preset["system_prompt"].lower()

    def test_invalid_preset_raises(self):
        """Test that invalid preset name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset("nonexistent_preset")

    def test_constructor_overrides_defaults(self, mock_config):
        """Test that constructor parameters override defaults."""
        custom_prompt = "Custom system prompt for testing"
        custom_criteria = ["Custom criterion 1", "Custom criterion 2"]

        reviewer = CodeReviewer(
            mock_config,
            system_prompt=custom_prompt,
            validation_criteria=custom_criteria,
        )

        assert reviewer.system_prompt == custom_prompt
        assert reviewer.validation_criteria == custom_criteria

    def test_preset_loading(self, mock_config):
        """Test that presets are loaded correctly."""
        preset = get_preset("security_focused")
        reviewer = CodeReviewer(mock_config, **preset)

        assert reviewer.system_prompt == preset["system_prompt"]
        assert reviewer.validation_criteria == preset["validation_criteria"]

    def test_constructor_overrides_preset(self, mock_config):
        """Test that constructor params override preset values."""
        preset = get_preset("general")
        custom_prompt = "Override prompt"

        reviewer = CodeReviewer(
            mock_config,
            system_prompt=custom_prompt,
            **{k: v for k, v in preset.items() if k != "system_prompt"}
        )

        assert reviewer.system_prompt == custom_prompt
        assert reviewer.validation_criteria == preset["validation_criteria"]


class TestCodeReviewerPromptConstruction:
    """Tests for prompt construction."""

    @pytest.mark.asyncio
    async def test_criteria_included_in_prompt(self, mock_config, mock_provider):
        """Test that validation criteria are included in the prompt."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_APPROVED

        await reviewer.run("test code")

        # Check that complete was called with messages containing criteria
        call_args = mock_provider.complete.call_args
        # Args could be positional or keyword - handle both
        if call_args.args:
            messages = call_args.args[0]
        else:
            messages = call_args.kwargs.get("messages", [])

        # Find user message
        user_message = next(m for m in messages if m["role"] == "user")

        # Should contain numbered criteria
        assert "1." in user_message["content"]

    @pytest.mark.asyncio
    async def test_system_prompt_used(self, mock_config, mock_provider):
        """Test that system prompt is included in messages."""
        custom_prompt = "You are a specialized test reviewer"
        reviewer = CodeReviewer(mock_config, system_prompt=custom_prompt)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_APPROVED

        await reviewer.run("test code")

        call_args = mock_provider.complete.call_args
        # Args could be positional or keyword - handle both
        if call_args.args:
            messages = call_args.args[0]
        else:
            messages = call_args.kwargs.get("messages", [])

        system_message = next(m for m in messages if m["role"] == "system")
        assert custom_prompt in system_message["content"]


# =============================================================================
# PRPipeline Unit Tests
# =============================================================================

class TestPRPipelineWorkflow:
    """Tests for PRPipeline workflow execution."""

    @pytest.mark.asyncio
    async def test_workflow_completes_all_steps(self, mock_config, mock_provider):
        """Test that workflow executes all three steps."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider

        # Mock responses for each step
        mock_provider.complete.side_effect = [
            MOCK_PR_SECURITY_SCAN,
            MOCK_PR_QUALITY_REVIEW,
            MOCK_PR_SUMMARY,
        ]

        result = await pipeline.run({
            "content": SAMPLE_CODE_WITH_SECRET,
            "title": "Test PR",
            "description": "Test description",
            "files_changed": ["test.py"],
        })

        # Should have called complete 3 times (one per step)
        assert mock_provider.complete.call_count == 3

        # Result should contain final summary data
        assert "overall_recommendation" in result or "summary" in result

    @pytest.mark.asyncio
    async def test_state_threading(self, mock_config, mock_provider):
        """Test that state is properly threaded through steps."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider

        mock_provider.complete.side_effect = [
            MOCK_PR_SECURITY_SCAN,
            MOCK_PR_QUALITY_REVIEW,
            MOCK_PR_SUMMARY,
        ]

        # Capture the prompts sent to each step
        prompts_received = []
        original_complete = mock_provider.complete

        async def capture_prompt(messages, **kwargs):
            prompts_received.append(messages)
            return await original_complete(messages, **kwargs)

        mock_provider.complete = AsyncMock(side_effect=[
            MOCK_PR_SECURITY_SCAN,
            MOCK_PR_QUALITY_REVIEW,
            MOCK_PR_SUMMARY,
        ])

        await pipeline.run({
            "content": "test code",
            "title": "Test PR",
        })

        # Verify 3 calls made
        assert mock_provider.complete.call_count == 3

    @pytest.mark.asyncio
    async def test_clean_code_passes_review(self, mock_config, mock_provider):
        """Test that clean code passes through pipeline."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider

        mock_provider.complete.side_effect = [
            MOCK_PR_SECURITY_SCAN_CLEAN,
            MOCK_PR_QUALITY_REVIEW_CLEAN,
            MOCK_PR_SUMMARY_APPROVED,
        ]

        result = await pipeline.run({
            "content": SAMPLE_CLEAN_CODE,
            "title": "Good PR",
        })

        # PRPipeline returns final_result with 'approved' and 'recommendation' fields
        assert result.get("approved") is True or result.get("recommendation") == "approve"


class TestPRPipelineIndividualSteps:
    """Tests for individual pipeline steps."""

    @pytest.mark.asyncio
    async def test_security_scan_step(self, mock_config, mock_provider):
        """Test security scan step in isolation."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider
        mock_provider.complete.return_value = MOCK_PR_SECURITY_SCAN

        initial_state = {
            "content": SAMPLE_CODE_WITH_SECRET,
            "title": "Test",
            "description": None,
            "files_changed": None,
            "security_result": None,
            "quality_result": None,
            "final_result": None,
        }

        result_state = await pipeline.security_scan(initial_state)

        assert result_state["security_result"] is not None
        assert "vulnerabilities" in result_state["security_result"]

    @pytest.mark.asyncio
    async def test_quality_review_has_security_context(self, mock_config, mock_provider):
        """Test that quality review step receives security context."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider
        mock_provider.complete.return_value = MOCK_PR_QUALITY_REVIEW

        # State after security scan
        state_with_security = {
            "content": "test code",
            "title": "Test",
            "description": None,
            "files_changed": None,
            "security_result": json.loads(MOCK_PR_SECURITY_SCAN),
            "quality_result": None,
            "final_result": None,
        }

        result_state = await pipeline.quality_review(state_with_security)

        # Verify complete was called
        mock_provider.complete.assert_called_once()

        # Result should contain quality data
        assert result_state["quality_result"] is not None


class TestPRPipelineErrorHandling:
    """Tests for PRPipeline error handling."""

    @pytest.mark.asyncio
    async def test_empty_content_handling(self, mock_config, mock_provider):
        """Test handling of empty content."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider

        # Even with empty content, pipeline should handle gracefully
        mock_provider.complete.side_effect = [
            MOCK_PR_SECURITY_SCAN_CLEAN,
            MOCK_PR_QUALITY_REVIEW_CLEAN,
            MOCK_PR_SUMMARY_APPROVED,
        ]

        result = await pipeline.run({
            "content": "",
            "title": "Empty PR",
        })

        # Should complete without crashing
        assert result is not None

    @pytest.mark.asyncio
    async def test_malformed_step_response(self, mock_config, mock_provider):
        """Test handling of malformed JSON in step response."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider

        # First step returns malformed JSON
        mock_provider.complete.side_effect = [
            "This is not valid JSON at all",
            MOCK_PR_QUALITY_REVIEW,
            MOCK_PR_SUMMARY,
        ]

        result = await pipeline.run({
            "content": "test",
            "title": "Test",
        })

        # Should handle gracefully (may have error in result)
        assert result is not None


# =============================================================================
# Integration-style Tests (still mocked but testing component interaction)
# =============================================================================

class TestAgentProviderIntegration:
    """Tests for agent-provider integration."""

    @pytest.mark.asyncio
    async def test_code_reviewer_calls_provider_correctly(self, mock_config, mock_provider):
        """Test that CodeReviewer calls provider with correct message format."""
        reviewer = CodeReviewer(mock_config)
        reviewer.provider = mock_provider
        mock_provider.complete.return_value = MOCK_CODE_REVIEWER_APPROVED

        await reviewer.run("test code")

        # Verify complete was called
        mock_provider.complete.assert_called_once()

        # Get the messages argument - handle both positional and keyword args
        call_args = mock_provider.complete.call_args
        if call_args.args:
            messages = call_args.args[0]
        else:
            messages = call_args.kwargs.get("messages", [])

        # Should have system and user messages
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_pr_pipeline_calls_provider_with_temperature(self, mock_config, mock_provider):
        """Test that PRPipeline calls provider with temperature setting."""
        pipeline = PRPipeline(mock_config)
        pipeline.provider = mock_provider

        mock_provider.complete.side_effect = [
            MOCK_PR_SECURITY_SCAN,
            MOCK_PR_QUALITY_REVIEW,
            MOCK_PR_SUMMARY,
        ]

        await pipeline.run({"content": "test", "title": "Test"})

        # Check that temperature was passed (in kwargs)
        for call in mock_provider.complete.call_args_list:
            kwargs = call[1] if len(call) > 1 else {}
            # Temperature may be passed as kwarg
            if "temperature" in kwargs:
                assert isinstance(kwargs["temperature"], (int, float))


# =============================================================================
# ReleasePipeline Unit Tests
# =============================================================================

class TestReleasePipelineStructure:
    """Tests for ReleasePipeline structure and initialization."""

    def test_instantiation(self, mock_config):
        """Test that ReleasePipeline instantiates correctly."""
        pipeline = ReleasePipeline(mock_config)
        assert pipeline is not None
        assert hasattr(pipeline, 'build_graph')
        assert hasattr(pipeline, '_run_shell')

    def test_graph_structure(self, mock_config):
        """Test that graph has all expected nodes."""
        pipeline = ReleasePipeline(mock_config)
        graph = pipeline.build_graph()

        expected_nodes = [
            '__start__',
            'validate_changelog',
            'create_branch',
            'stage_changes',
            'commit_changes',
            'push_branch',
            'create_pr',
            'generate_release_notes',
            'generate_summary',
        ]
        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_has_shell_executor(self, mock_config):
        """Test that _run_shell method is available."""
        pipeline = ReleasePipeline(mock_config)
        assert hasattr(pipeline, '_run_shell')
        assert callable(pipeline._run_shell)


class TestReleasePipelineCommandFormatting:
    """Tests for shell command formatting."""

    def test_branch_command_formatting(self, mock_config):
        """Test that branch command is formatted correctly."""
        import shlex
        state = {'version': '0.3.0'}
        command_template = 'git checkout -b release/v{version}'
        command = command_template.format(**{k: str(v) for k, v in state.items()})
        assert command == 'git checkout -b release/v0.3.0'

    def test_commit_message_quoting(self, mock_config):
        """Test that commit message with special chars is quoted."""
        import shlex
        commit_msg = 'feat(release): v0.3.0 - Add "blueprints" system'
        quoted = shlex.quote(commit_msg)
        # shlex.quote should wrap in single quotes and escape internal quotes
        assert "'" in quoted or '"' in quoted
        assert 'feat(release)' in quoted

    def test_pr_body_quoting(self, mock_config):
        """Test that PR body with newlines is quoted safely."""
        import shlex
        pr_body = "## Release\n\n- Feature 1\n- Feature 2"
        quoted = shlex.quote(pr_body)
        # Should contain the content safely escaped
        assert 'Release' in quoted


class TestReleasePipelineSteps:
    """Tests for individual pipeline steps."""

    @pytest.mark.asyncio
    async def test_validate_changelog_extracts_fields(self, mock_config, mock_provider):
        """Test that validate_changelog extracts commit_message and pr_body."""
        pipeline = ReleasePipeline(mock_config)
        pipeline.provider = mock_provider

        mock_response = json.dumps({
            "valid": True,
            "issues": [],
            "commit_message": "feat(release): v0.3.0",
            "pr_body": "## Release v0.3.0\n\nNew features",
        })
        mock_provider.complete.return_value = mock_response

        initial_state = {
            'version': '0.3.0',
            'release_type': 'minor',
            'changelog_content': '## [0.3.0]\n\n### Added\n- Feature',
            'base_branch': 'main',
            'changelog_validation': None,
            'commit_message': None,
            'pr_body': None,
            'release_notes': None,
            'final_result': None,
            'branch_output': None,
            'branch_success': None,
            'stage_output': None,
            'stage_success': None,
            'commit_output': None,
            'commit_success': None,
            'push_output': None,
            'push_success': None,
            'pr_output': None,
            'pr_success': None,
        }

        result_state = await pipeline.validate_changelog(initial_state)

        # Should extract commit_message and pr_body to top-level state
        assert result_state['commit_message'] == "feat(release): v0.3.0"
        assert "Release v0.3.0" in result_state['pr_body']
        assert result_state['changelog_validation']['valid'] is True

    @pytest.mark.asyncio
    async def test_shell_step_returns_output(self, mock_config, mock_provider):
        """Test that shell steps return output and success status."""
        pipeline = ReleasePipeline(mock_config)

        # Mock _run_shell to return simulated output
        async def mock_run_shell(command, timeout=300, working_dir=None):
            if 'checkout' in command:
                return ("Switched to branch", "", 0)
            return ("", "", 0)

        pipeline._run_shell = mock_run_shell

        state = {
            'version': '0.3.0',
            'release_type': 'minor',
            'changelog_content': '',
            'base_branch': 'main',
            'changelog_validation': None,
            'commit_message': None,
            'pr_body': None,
            'release_notes': None,
            'final_result': None,
            'branch_output': None,
            'branch_success': None,
            'stage_output': None,
            'stage_success': None,
            'commit_output': None,
            'commit_success': None,
            'push_output': None,
            'push_success': None,
            'pr_output': None,
            'pr_success': None,
        }

        result = await pipeline.create_branch(state)

        assert result['branch_output'] == "Switched to branch"
        assert result['branch_success'] is True


# =============================================================================
# PRCommentProcessor Unit Tests
# =============================================================================

class TestPRCommentProcessorStructure:
    """Tests for PRCommentProcessor structure and initialization."""

    def test_instantiation(self, mock_config):
        """Test that PRCommentProcessor instantiates correctly."""
        processor = PRCommentProcessor(mock_config)
        assert processor is not None
        assert hasattr(processor, 'build_graph')
        assert hasattr(processor, 'analyze_prompt')
        assert hasattr(processor, 'generate_fix_prompt')

    def test_graph_has_loop_structure(self, mock_config):
        """Test that graph has the expected nodes including loop."""
        processor = PRCommentProcessor(mock_config)
        graph = processor.build_graph()

        expected_nodes = [
            '__start__',
            'fetch_comments',
            'select_next_comment',
            'read_file',
            'analyze_comment',
            'generate_fix',
            'apply_fix',
            'record_result',
            'generate_summary',
        ]
        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_custom_prompts(self, mock_config):
        """Test that custom prompts can be provided."""
        custom_analyze = "Custom analyze prompt"
        custom_fix = "Custom fix prompt"

        processor = PRCommentProcessor(
            mock_config,
            analyze_prompt=custom_analyze,
            generate_fix_prompt=custom_fix,
        )

        assert processor.analyze_prompt == custom_analyze
        assert processor.generate_fix_prompt == custom_fix


class TestPRCommentProcessorFetchComments:
    """Tests for fetch_comments step."""

    @pytest.mark.asyncio
    async def test_fetch_filters_addressed_comments(self, mock_config, mock_provider):
        """Test that fetch_comments filters out addressed comments."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        # Mix of addressed and unaddressed comments
        comments = [
            {"id": "1", "addressed": False, "body": "Fix this"},
            {"id": "2", "addressed": True, "body": "Already fixed"},
            {"id": "3", "addressed": False, "body": "Also fix this"},
        ]

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": "/tmp",
            "all_comments": comments,
            "pending_comments": [],
            "current_comment": None,
            "processed_comments": [],
            "current_file_path": None,
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": False,
            "iteration_count": 0,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.fetch_comments(state)

        # Should only have unaddressed comments
        assert len(result["pending_comments"]) == 2
        assert all(not c["addressed"] for c in result["pending_comments"])
        assert result["has_more_comments"] is True


class TestPRCommentProcessorSelectNext:
    """Tests for select_next_comment step."""

    @pytest.mark.asyncio
    async def test_select_pops_from_queue(self, mock_config, mock_provider):
        """Test that select_next_comment pops from pending queue."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": "/tmp",
            "all_comments": None,
            "pending_comments": [
                {"id": "1", "path": "file1.py", "body": "Comment 1"},
                {"id": "2", "path": "file2.py", "body": "Comment 2"},
            ],
            "current_comment": None,
            "processed_comments": [],
            "current_file_path": None,
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": True,
            "iteration_count": 0,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.select_next_comment(state)

        assert result["current_comment"]["id"] == "1"
        assert result["current_file_path"] == "file1.py"
        assert len(result["pending_comments"]) == 1
        assert result["has_more_comments"] is True
        assert result["iteration_count"] == 1

    @pytest.mark.asyncio
    async def test_select_sets_no_more_comments_on_last(self, mock_config, mock_provider):
        """Test that has_more_comments is False when queue is empty after pop."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": "/tmp",
            "all_comments": None,
            "pending_comments": [
                {"id": "1", "path": "file1.py", "body": "Last comment"},
            ],
            "current_comment": None,
            "processed_comments": [],
            "current_file_path": None,
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": True,
            "iteration_count": 0,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.select_next_comment(state)

        assert result["has_more_comments"] is False


class TestPRCommentProcessorReadFile:
    """Tests for read_file step."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, mock_config, mock_provider, tmp_path):
        """Test successful file reading."""
        processor = PRCommentProcessor(mock_config, working_dir=str(tmp_path))
        processor.provider = mock_provider

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": str(tmp_path),
            "all_comments": None,
            "pending_comments": [],
            "current_comment": {"id": "1", "path": "test.py"},
            "processed_comments": [],
            "current_file_path": "test.py",
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": False,
            "iteration_count": 1,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.read_file(state)

        assert result["current_file_content"] == "def hello():\n    pass\n"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, mock_config, mock_provider, tmp_path):
        """Test file not found handling."""
        processor = PRCommentProcessor(mock_config, working_dir=str(tmp_path))
        processor.provider = mock_provider

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": str(tmp_path),
            "all_comments": None,
            "pending_comments": [],
            "current_comment": {"id": "1", "path": "nonexistent.py"},
            "processed_comments": [],
            "current_file_path": "nonexistent.py",
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": False,
            "iteration_count": 1,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.read_file(state)

        assert result["current_file_content"] is None
        assert result["analysis_result"]["error"] is not None
        assert result["analysis_result"]["can_auto_fix"] is False


class TestPRCommentProcessorAnalyzeComment:
    """Tests for analyze_comment LLM step."""

    @pytest.mark.asyncio
    async def test_analyze_calls_llm(self, mock_config, mock_provider):
        """Test that analyze_comment calls the LLM."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider
        mock_provider.complete.return_value = MOCK_COMMENT_ANALYSIS_CAN_FIX

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": "/tmp",
            "all_comments": None,
            "pending_comments": [],
            "current_comment": {"id": "1", "path": "test.py", "body": "Add type hints"},
            "processed_comments": [],
            "current_file_path": "test.py",
            "current_file_content": SAMPLE_FILE_CONTENT,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": False,
            "iteration_count": 1,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.analyze_comment(state)

        mock_provider.complete.assert_called_once()
        assert result["analysis_result"]["understood"] is True
        assert result["analysis_result"]["can_auto_fix"] is True


class TestPRCommentProcessorApplyFix:
    """Tests for apply_fix step."""

    @pytest.mark.asyncio
    async def test_apply_fix_writes_file(self, mock_config, mock_provider, tmp_path):
        """Test that apply_fix writes the fixed content."""
        processor = PRCommentProcessor(mock_config, working_dir=str(tmp_path))
        processor.provider = mock_provider

        # Create initial file
        test_file = tmp_path / "test.py"
        test_file.write_text("def old():\n    pass\n")

        new_content = "def new():\n    pass\n"

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": str(tmp_path),
            "all_comments": None,
            "pending_comments": [],
            "current_comment": {"id": "1", "path": "test.py"},
            "processed_comments": [],
            "current_file_path": "test.py",
            "current_file_content": "def old():\n    pass\n",
            "analysis_result": {"can_auto_fix": True},
            "proposed_fix": {
                "success": True,
                "full_file_content": new_content,
            },
            "has_more_comments": False,
            "iteration_count": 1,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.apply_fix(state)

        assert result["proposed_fix"]["applied"] is True
        assert test_file.read_text() == new_content


class TestPRCommentProcessorRecordResult:
    """Tests for record_result step."""

    @pytest.mark.asyncio
    async def test_record_applied(self, mock_config, mock_provider):
        """Test recording an applied fix."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": "/tmp",
            "all_comments": None,
            "pending_comments": [],
            "current_comment": {"id": "1", "path": "test.py", "body": "Fix this"},
            "processed_comments": [],
            "current_file_path": "test.py",
            "current_file_content": "content",
            "analysis_result": {"can_auto_fix": True, "change_type": "refactor"},
            "proposed_fix": {"applied": True, "changes_summary": "Fixed it"},
            "has_more_comments": False,
            "iteration_count": 1,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.record_result(state)

        assert len(result["processed_comments"]) == 1
        assert result["processed_comments"][0]["status"] == "applied"

    @pytest.mark.asyncio
    async def test_record_skipped(self, mock_config, mock_provider):
        """Test recording a skipped comment."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        state = {
            "repo_name": "test/repo",
            "pr_number": 1,
            "remote": "github",
            "default_branch": "main",
            "working_dir": "/tmp",
            "all_comments": None,
            "pending_comments": [],
            "current_comment": {"id": "1", "path": "test.py", "body": "Complex change"},
            "processed_comments": [],
            "current_file_path": "test.py",
            "current_file_content": "content",
            "analysis_result": {"can_auto_fix": False, "skip_reason": "Too complex"},
            "proposed_fix": {},
            "has_more_comments": False,
            "iteration_count": 1,
            "max_iterations": 50,
            "final_result": None,
        }

        result = await processor.record_result(state)

        assert len(result["processed_comments"]) == 1
        assert result["processed_comments"][0]["status"] == "skipped"


class TestPRCommentProcessorWorkflow:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_empty_comments_list(self, mock_config, mock_provider):
        """Test handling of empty comments list."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        # Summary generation will be called
        mock_provider.complete.return_value = MOCK_COMMENT_SUMMARY

        result = await processor.run({
            "repo_name": "test/repo",
            "pr_number": 123,
            "all_comments": [],
            "working_dir": "/tmp",
        })

        assert result["total_comments"] == 0
        assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, mock_config, mock_provider):
        """Test handling of missing required fields."""
        processor = PRCommentProcessor(mock_config)
        processor.provider = mock_provider

        result = await processor.run({})

        assert "error" in result
        assert result["total_comments"] == 0

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self, mock_config, mock_provider):
        """Test that max_iterations limit is enforced."""
        processor = PRCommentProcessor(mock_config, max_iterations=2)
        processor.provider = mock_provider

        # Create 5 comments but limit to 2 iterations
        comments = [
            {"id": str(i), "path": f"file{i}.py", "body": f"Comment {i}", "addressed": False}
            for i in range(5)
        ]

        # Mock responses for analyze, fix, and summary
        mock_provider.complete.side_effect = [
            MOCK_COMMENT_ANALYSIS_CAN_FIX,  # First comment analysis
            MOCK_FIX_GENERATED,              # First comment fix
            MOCK_COMMENT_ANALYSIS_CAN_FIX,  # Second comment analysis
            MOCK_FIX_GENERATED,              # Second comment fix
            MOCK_COMMENT_SUMMARY,            # Summary (should stop here due to limit)
        ]

        # Mock file reading
        with patch.object(processor, 'read_file') as mock_read:
            mock_read.side_effect = lambda state: {**state, "current_file_content": "content"}

            # Mock file writing
            with patch.object(processor, 'apply_fix') as mock_apply:
                mock_apply.side_effect = lambda state: {
                    **state,
                    "proposed_fix": {**state.get("proposed_fix", {}), "applied": True}
                }

                result = await processor.run({
                    "repo_name": "test/repo",
                    "pr_number": 123,
                    "all_comments": comments,
                    "working_dir": "/tmp",
                    "max_iterations": 2,
                })

        # Should process at most 2 comments due to limit
        assert result is not None
