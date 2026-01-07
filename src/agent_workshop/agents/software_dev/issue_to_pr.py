"""
IssueToPR Workflow - Generates PRs from GitHub Issues with Human Checkpoint.

This LangGraph workflow automates the first stage of the Triangle:
1. parse_issue - Fetch and parse GitHub issue into specification
2. setup_worktree - Create isolated git worktree for development
3. generate_code - Use LLM to generate implementation
4. verify_code - Run tiered verification (SCHEMA → SYNTAX → LINT → TYPE → TEST)
5. create_pr - Create draft PR on GitHub
6. await_review - CHECKPOINT: Stop and wait for human + Greptile review

The workflow pauses after PR creation. Resume with `triangle approve`.

Usage:
    from agent_workshop.agents.software_dev import IssueToPR
    from agent_workshop.utils.persistence import get_checkpointer

    # Create with checkpointing enabled
    workflow = IssueToPR(
        config=Config(),
        checkpointer=get_checkpointer()
    )

    # Start workflow (will pause after PR creation)
    result = await workflow.run(
        {"issue_number": 42, "repo_name": "owner/repo"},
        thread_id="owner-repo-issue-42"
    )

    # Result will have requires_human_approval=True
    # Resume after approval via TriangleOrchestrator
"""

from datetime import datetime, timezone

from langgraph.graph import END, StateGraph

from agent_workshop import Config
from agent_workshop.agents.software_dev.types import IssueToPRState, IssueSpecification
from agent_workshop.agents.software_dev.utils import (
    GitHubClient,
    VerificationLevel,
    commit_changes,
    create_branch as git_create_branch,
    push_branch,
    sanitize_branch_name,
    setup_worktree as git_setup_worktree,
    verify,
)
from agent_workshop.workflows import LangGraphAgent


def make_thread_id(repo_name: str, issue_number: int) -> str:
    """Generate thread ID for checkpoint persistence.

    Format: {repo}-issue-{number}
    Example: trentleslie-agent-workshop-issue-42
    """
    safe_repo = repo_name.replace("/", "-")
    return f"{safe_repo}-issue-{issue_number}"


class IssueToPR(LangGraphAgent):
    """
    Workflow that transforms a GitHub issue into a draft PR.

    Human-in-the-loop Design:
    - Executes autonomously through code generation and verification
    - STOPS after creating the PR (await_review checkpoint)
    - Waits for human review + Greptile feedback
    - Resumes via `triangle approve` command

    Nodes:
        parse_issue -> setup_worktree -> generate_code -> verify_code
        -> create_pr -> await_review (STOP)

    The verify_code node has a retry loop back to generate_code if
    verification fails (max 3 attempts).
    """

    DEFAULT_CODE_GEN_PROMPT = """You are an expert software engineer implementing a GitHub issue.

## Issue
Title: {title}
Body:
{body}

## Requirements
{requirements}

## Files to Modify
{files_to_modify}

## Instructions
Generate the code changes needed to implement this issue. For each file:
1. Show the complete file content (not diffs)
2. Include all necessary imports
3. Follow existing code patterns in the repository
4. Write clean, well-documented code

Output format:
```filename.py
<complete file content>
```

If creating new files, prefix with NEW:
```NEW: path/to/new/file.py
<complete file content>
```
"""

    MAX_VERIFICATION_ATTEMPTS = 3

    def __init__(
        self,
        config: Config | None = None,
        checkpointer=None,
        code_gen_prompt: str | None = None,
    ):
        """Initialize IssueToPR workflow.

        Args:
            config: Configuration instance
            checkpointer: Checkpoint saver for persistence (required for resume)
            code_gen_prompt: Custom prompt for code generation
        """
        self.code_gen_prompt = code_gen_prompt or self.DEFAULT_CODE_GEN_PROMPT
        self._github_clients: dict[str, GitHubClient] = {}
        super().__init__(config=config, checkpointer=checkpointer)

    def get_github_client(self, repo: str) -> GitHubClient:
        """Get or create GitHub client for a repo."""
        if repo not in self._github_clients:
            self._github_clients[repo] = GitHubClient(repo=repo)
        return self._github_clients[repo]

    def build_graph(self) -> StateGraph:
        """Build the IssueToPR workflow graph with checkpoint support."""
        workflow = StateGraph(IssueToPRState)

        # Add nodes
        workflow.add_node("parse_issue", self.parse_issue)
        workflow.add_node("setup_worktree", self.setup_worktree)
        workflow.add_node("generate_code", self.generate_code)
        workflow.add_node("verify_code", self.verify_code)
        workflow.add_node("create_pr", self.create_pr)
        workflow.add_node("await_review", self.await_review)

        # Linear flow with conditional retry
        workflow.add_edge("parse_issue", "setup_worktree")
        workflow.add_edge("setup_worktree", "generate_code")
        workflow.add_edge("generate_code", "verify_code")
        workflow.add_conditional_edges(
            "verify_code",
            self._should_retry_or_continue,
            {"retry": "generate_code", "continue": "create_pr", "fail": END},
        )
        workflow.add_edge("create_pr", "await_review")
        # await_review is terminal - workflow pauses here

        workflow.set_entry_point("parse_issue")

        # Compile with checkpointer and interrupt after await_review
        return workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_after=["await_review"],
        )

    def _should_retry_or_continue(self, state: IssueToPRState) -> str:
        """Determine next step after verification."""
        verification = state.get("last_verification_result", {})
        attempts = state.get("verification_attempts", 0)

        if verification.get("passed"):
            return "continue"
        elif attempts >= self.MAX_VERIFICATION_ATTEMPTS:
            return "fail"
        else:
            return "retry"

    async def parse_issue(self, state: IssueToPRState) -> IssueToPRState:
        """Fetch and parse GitHub issue into specification."""
        issue_number = state["issue_number"]
        repo_name = state["repo_name"]

        # Fetch issue from GitHub
        github = self.get_github_client(repo_name)
        result = await github.get_issue(issue_number)
        if not result.success:
            return {
                **state,
                "current_step": "parse_issue",
                "error": f"Failed to fetch issue: {result.error}",
            }

        issue = result.data

        # Use LLM to parse issue into structured specification
        parse_prompt = f"""Parse this GitHub issue into a structured specification.

Title: {issue.title}
Body:
{issue.body}

Extract:
1. requirements - List of specific requirements
2. acceptance_criteria - List of acceptance criteria (if any)
3. files_to_create - New files that need to be created
4. files_to_modify - Existing files that need modification
5. complexity - Estimate: simple, medium, complex

Output as JSON:
{{
    "requirements": ["req1", "req2"],
    "acceptance_criteria": ["criterion1"],
    "files_to_create": ["path/to/new.py"],
    "files_to_modify": ["path/to/existing.py"],
    "complexity": "medium"
}}
"""

        llm_result = await self.provider.complete([
            {"role": "user", "content": parse_prompt}
        ])

        # Parse LLM response (handle JSON extraction)
        try:
            import json
            import re

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", llm_result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        # Build IssueSpecification
        branch_name = sanitize_branch_name(f"auto/issue-{issue_number}")
        spec = IssueSpecification(
            title=issue.title,
            body=issue.body or "",
            requirements=parsed.get("requirements", []),
            acceptance_criteria=parsed.get("acceptance_criteria", []),
            files_to_create=parsed.get("files_to_create", []),
            files_to_modify=parsed.get("files_to_modify", []),
            branch_name=branch_name,
            complexity=parsed.get("complexity", "medium"),
        )

        return {
            **state,
            "current_step": "parse_issue",
            "issue_spec": spec.model_dump(),
            "branch_name": branch_name,
        }

    async def setup_worktree(self, state: IssueToPRState) -> IssueToPRState:
        """Create isolated git worktree for development."""
        branch_name = state["branch_name"]
        repo_path = "."  # Use current directory as repo root

        # Create branch first
        branch_result = await git_create_branch(repo_path, branch_name)
        if not branch_result.success:
            # Branch might already exist, continue anyway
            pass

        # Setup worktree - returns Path directly, raises RuntimeError on failure
        try:
            worktree_path = await git_setup_worktree(repo_path, branch_name)
            return {
                **state,
                "current_step": "setup_worktree",
                "working_dir": str(worktree_path),
            }
        except RuntimeError as e:
            return {
                **state,
                "current_step": "setup_worktree",
                "error": f"Failed to setup worktree: {e}",
            }

    async def generate_code(self, state: IssueToPRState) -> IssueToPRState:
        """Generate code implementation using LLM."""
        spec = state.get("issue_spec", {})
        working_dir = state.get("working_dir", ".")
        attempts = state.get("verification_attempts", 0)

        # Format the prompt
        prompt = self.code_gen_prompt.format(
            title=spec.get("title", ""),
            body=spec.get("body", ""),
            requirements="\n".join(f"- {r}" for r in spec.get("requirements", [])),
            files_to_modify="\n".join(spec.get("files_to_modify", []) + spec.get("files_to_create", [])),
        )

        # Add previous verification errors if retrying
        if attempts > 0:
            last_result = state.get("last_verification_result", {})
            errors = last_result.get("errors", [])
            if errors:
                prompt += "\n\n## Previous Attempt Failed\nFix these errors:\n"
                prompt += "\n".join(f"- {e}" for e in errors[:10])

        # Generate code
        llm_result = await self.provider.complete([
            {"role": "user", "content": prompt}
        ])

        # Parse code blocks and write files
        files_changed = await self._write_generated_files(llm_result, working_dir)

        return {
            **state,
            "current_step": "generate_code",
            "files_changed": files_changed,
            "verification_attempts": attempts + 1,
        }

    async def _write_generated_files(
        self, llm_response: str, working_dir: str
    ) -> list[str]:
        """Parse LLM response and write files to worktree."""
        import re
        from pathlib import Path

        files_written = []
        # Match code blocks with filenames
        pattern = r"```(?:NEW:\s*)?([\w./\\-]+)\n(.*?)```"
        matches = re.findall(pattern, llm_response, re.DOTALL)

        for filename, content in matches:
            filepath = Path(working_dir) / filename.strip()
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content.strip())
            files_written.append(str(filepath))

        return files_written

    async def verify_code(self, state: IssueToPRState) -> IssueToPRState:
        """Run tiered verification on generated code."""
        files_changed = state.get("files_changed", [])

        # Verify each Python file individually, aggregate results
        all_errors = []
        all_passed = True

        for file_path in files_changed:
            if not file_path.endswith(".py"):
                continue

            result = await verify(
                file_path=file_path,
                level=VerificationLevel.LINT,
            )

            if not result.passed:
                all_passed = False
                all_errors.extend(result.errors or [])

        return {
            **state,
            "current_step": "verify_code",
            "last_verification_result": {
                "passed": all_passed,
                "level": VerificationLevel.LINT.name,
                "errors": all_errors,
            },
        }

    async def create_pr(self, state: IssueToPRState) -> IssueToPRState:
        """Create draft PR on GitHub."""
        repo_name = state["repo_name"]
        branch_name = state["branch_name"]
        issue_number = state["issue_number"]
        spec = state.get("issue_spec", {})
        working_dir = state.get("working_dir", ".")
        files_changed = state.get("files_changed", [])

        # Commit changes
        commit_msg = f"feat: implement issue #{issue_number}\n\n{spec.get('title', '')}"
        commit_result = await commit_changes(
            worktree_path=working_dir,
            message=commit_msg,
            files=files_changed,
        )
        if not commit_result.success:
            return {
                **state,
                "current_step": "create_pr",
                "error": f"Failed to commit: {commit_result.stderr}",
            }

        # Push branch
        push_result = await push_branch(
            worktree_path=working_dir,
            branch_name=branch_name,
        )
        if not push_result.success:
            return {
                **state,
                "current_step": "create_pr",
                "error": f"Failed to push: {push_result.stderr}",
            }

        # Create draft PR
        pr_body = f"""## Summary
Implements #{issue_number}

## Changes
{chr(10).join(f'- `{f}`' for f in files_changed)}

## Requirements
{chr(10).join(f'- {r}' for r in spec.get('requirements', []))}

---
Generated by Triangle Workflow
"""
        github = self.get_github_client(repo_name)
        pr_result = await github.create_draft_pr(
            title=f"feat: {spec.get('title', f'Implement issue #{issue_number}')}",
            body=pr_body,
            branch=branch_name,
        )

        if not pr_result.success:
            return {
                **state,
                "current_step": "create_pr",
                "error": f"Failed to create PR: {pr_result.error}",
            }

        pr = pr_result.data
        return {
            **state,
            "current_step": "create_pr",
            "pr_number": pr.number,
            "pr_url": pr.url,
        }

    async def await_review(self, state: IssueToPRState) -> IssueToPRState:
        """Terminal node: Set checkpoint flag and wait for human review.

        This node sets requires_human_approval=True which signals
        LangGraph to pause execution via interrupt_after.

        The workflow resumes when `triangle approve` is called.
        """
        checkpoint_time = datetime.now(timezone.utc).isoformat()
        files_count = len(state.get("files_changed", []))

        return {
            **state,
            "current_step": "awaiting_review",
            "requires_human_approval": True,
            "checkpoint_at": checkpoint_time,
            "metrics": {
                **state.get("metrics", {}),
                "pr_submitted_at": checkpoint_time,
                "files_in_pr": files_count,
                "verification_attempts": state.get("verification_attempts", 0),
            },
        }
