"""
Triangle Orchestrator - Full cycle workflow with human checkpoints.

Orchestrates the complete triangle workflow:
1. IssueToPR - Generate code from issue (CHECKPOINT after PR created)
2. PRCommentProcessor - Process review comments (best effort)
3. Finalize - Merge PR and create follow-up issues

Human-in-the-loop Design:
- Workflow pauses after IssueToPR creates the PR
- Human + Greptile review the PR
- `triangle approve` resumes the workflow
- PRCommentProcessor addresses comments (best effort)
- Unaddressed comments become new GitHub issues

Usage:
    from agent_workshop.agents.software_dev import TriangleOrchestrator
    from agent_workshop.utils.persistence import get_checkpointer

    orchestrator = TriangleOrchestrator(
        config=Config(),
        checkpointer=get_checkpointer()
    )

    # Start workflow (will pause at checkpoint)
    result = await orchestrator.run(
        {"issue_number": 42, "repo_name": "owner/repo"},
        thread_id="owner-repo-issue-42"
    )

    # After approval, resume with same thread_id
    result = await orchestrator.run(
        {},  # Empty input - state is restored from checkpoint
        thread_id="owner-repo-issue-42"
    )
"""

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from rich.console import Console

from agent_workshop import Config
from agent_workshop.agents.software_dev.issue_to_pr import IssueToPR
from agent_workshop.agents.software_dev.pr_comment_processor import PRCommentProcessor
from agent_workshop.agents.software_dev.types import (
    CommentProcessorResults,
    TriangleState,
)
from agent_workshop.agents.software_dev.utils import GitHubClient
from agent_workshop.agents.software_dev.utils.git_operations import (
    cleanup_worktree,
    commit_changes,
    push_branch,
)
from agent_workshop.agents.software_dev.utils.verification import (
    VerificationLevel,
    verify,
)
from agent_workshop.workflows import LangGraphAgent

console = Console()


class CommentProcessorConfig(BaseModel):
    """Configuration for best-effort comment processing."""

    max_attempts_per_comment: int = Field(
        default=2,
        description="Maximum retry attempts per comment",
    )
    continue_on_failure: bool = Field(
        default=True,
        description="Continue processing if a comment fix fails",
    )
    skip_complex_comments: bool = Field(
        default=True,
        description="Skip comments estimated to require > 50 lines",
    )
    timeout_per_comment_seconds: int = Field(
        default=120,
        description="Timeout for processing each comment",
    )


class TriangleOrchestrator(LangGraphAgent):
    """
    Orchestrates the full triangle workflow with human checkpoints.

    Workflow:
        issue_to_pr -> (CHECKPOINT) -> process_comments -> finalize -> END

    The checkpoint after issue_to_pr allows:
    - Human review of the generated PR
    - Greptile automated review
    - Manual intervention if needed

    After approval, PRCommentProcessor runs in best-effort mode,
    and any unaddressed comments become new GitHub issues.
    """

    def __init__(
        self,
        config: Config | None = None,
        checkpointer=None,
        comment_config: CommentProcessorConfig | None = None,
    ):
        """Initialize Triangle Orchestrator.

        Args:
            config: Configuration instance
            checkpointer: Checkpoint saver for persistence (required)
            comment_config: Configuration for comment processing
        """
        self.comment_config = comment_config or CommentProcessorConfig()
        self._github_clients: dict[str, GitHubClient] = {}
        self._issue_to_pr: IssueToPR | None = None
        self._comment_processor: PRCommentProcessor | None = None
        super().__init__(config=config, checkpointer=checkpointer)

    async def resume_from_checkpoint(
        self,
        checkpoint_state: dict[str, Any],
    ) -> TriangleState:
        """Resume workflow after human approval.

        This method continues the workflow from the checkpoint after IssueToPR
        has created a PR and paused for human review.

        Args:
            checkpoint_state: The saved state from the IssueToPR checkpoint.

        Returns:
            Final TriangleState after completion.
        """
        # Clear the approval flag and record approval time
        state: TriangleState = {
            **checkpoint_state,
            "requires_human_approval": False,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "current_step": "resuming",
        }

        console.print("[blue]Resuming workflow from checkpoint...[/blue]")

        # Step 1: Process comments (best effort)
        console.print("[blue]Step 1/2: Processing review comments...[/blue]")
        state = await self.run_comment_processor(state)

        if state.get("error"):
            console.print(f"[red]Error processing comments: {state['error']}[/red]")
            # Continue to finalize even with errors in best-effort mode
            if not self.comment_config.continue_on_failure:
                return state

        # Step 2: Finalize (merge PR, create follow-up issues)
        console.print("[blue]Step 2/2: Finalizing workflow...[/blue]")
        state = await self.finalize(state)

        # Clean up worktree if it exists
        working_dir = state.get("working_dir")
        branch_name = state.get("branch_name")
        if working_dir and branch_name:
            try:
                # Use current directory as repo root
                await cleanup_worktree(
                    repo_path=".",
                    branch_name=branch_name,
                    worktree_path=working_dir,
                )
                console.print(f"[dim]Cleaned up worktree: {working_dir}[/dim]")
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not clean up worktree: {e}[/yellow]"
                )

        return state

    def get_github_client(self, repo: str) -> GitHubClient:
        """Get or create GitHub client for a repo."""
        if repo not in self._github_clients:
            self._github_clients[repo] = GitHubClient(repo=repo)
        return self._github_clients[repo]

    def build_graph(self) -> StateGraph:
        """Build the orchestrator workflow graph."""
        workflow = StateGraph(TriangleState)

        # Add nodes
        workflow.add_node("issue_to_pr", self.run_issue_to_pr)
        workflow.add_node("process_comments", self.run_comment_processor)
        workflow.add_node("finalize", self.finalize)

        # Flow with checkpoint after issue_to_pr
        workflow.add_conditional_edges(
            "issue_to_pr",
            self._after_issue_to_pr,
            {"checkpoint": END, "error": END, "continue": "process_comments"},
        )
        workflow.add_edge("process_comments", "finalize")
        workflow.add_edge("finalize", END)

        workflow.set_entry_point("issue_to_pr")

        # Compile with checkpointer
        # Note: interrupt_after is handled by IssueToPR internally
        return workflow.compile(checkpointer=self.checkpointer)

    def _after_issue_to_pr(self, state: TriangleState) -> str:
        """Determine next step after IssueToPR."""
        if state.get("error"):
            return "error"
        if state.get("requires_human_approval"):
            return "checkpoint"
        return "continue"

    async def run_issue_to_pr(self, state: TriangleState) -> TriangleState:
        """Run IssueToPR workflow as first stage."""
        # If already has PR, we're resuming - skip to next stage
        if state.get("pr_number") and not state.get("requires_human_approval"):
            return {
                **state,
                "current_step": "issue_to_pr_completed",
            }

        # Initialize IssueToPR with same checkpointer
        if self._issue_to_pr is None:
            self._issue_to_pr = IssueToPR(
                config=self.config,
                checkpointer=self.checkpointer,
            )

        # Run IssueToPR (it will pause at await_review)
        result = await self._issue_to_pr.run(
            {
                "issue_number": state["issue_number"],
                "repo_name": state["repo_name"],
            },
            thread_id=f"{state['repo_name'].replace('/', '-')}-issue-{state['issue_number']}",
        )

        # Merge result into orchestrator state
        return {
            **state,
            "issue_to_pr_result": result,
            "pr_number": result.get("pr_number"),
            "pr_url": result.get("pr_url"),
            "branch_name": result.get("branch_name"),
            "working_dir": result.get("working_dir"),
            "current_step": result.get("current_step"),
            "requires_human_approval": result.get("requires_human_approval", False),
            "checkpoint_at": result.get("checkpoint_at"),
            "error": result.get("error"),
        }

    async def run_comment_processor(self, state: TriangleState) -> TriangleState:
        """Run PRCommentProcessor in best-effort mode.

        Fetches PR comments, runs the processor to generate and apply fixes,
        then commits and pushes the changes. Unaddressed comments are tracked
        for follow-up issue creation in the finalize step.
        """
        pr_number = state.get("pr_number")
        repo_name = state["repo_name"]
        working_dir = state.get("working_dir", ".")

        if not pr_number:
            return {
                **state,
                "current_step": "process_comments",
                "error": "No PR number - cannot process comments",
            }

        # Fetch comments from GitHub (includes Greptile comments)
        github = self.get_github_client(repo_name)
        comments_result = await github.list_pr_comments(pr_number=pr_number)

        if not comments_result.success:
            return {
                **state,
                "current_step": "process_comments",
                "comment_results": CommentProcessorResults(
                    addressed=[],
                    skipped=[],
                    failed=[{"error": comments_result.error}],
                ),
            }

        comments = comments_result.data

        # Filter unaddressed comments only
        unaddressed = [c for c in comments if not c.addressed]

        if not unaddressed:
            console.print("[green]No unaddressed comments to process[/green]")
            return {
                **state,
                "current_step": "process_comments",
                "comment_results": CommentProcessorResults(
                    addressed=[],
                    skipped=[],
                    failed=[],
                ),
            }

        console.print(f"[blue]Processing {len(unaddressed)} comments...[/blue]")

        # Pre-filter complex comments if configured
        filtered_comments = []
        skipped_complex = []

        for comment in unaddressed:
            if self.comment_config.skip_complex_comments:
                if self._estimate_complexity(comment.body) > 50:
                    skipped_complex.append(
                        {
                            "id": str(comment.id),
                            "reason": "too_complex",
                            "body": comment.body[:100],
                        }
                    )
                    continue
            filtered_comments.append(comment)

        if not filtered_comments:
            console.print("[yellow]All comments skipped (too complex)[/yellow]")
            return {
                **state,
                "current_step": "process_comments",
                "comment_results": CommentProcessorResults(
                    addressed=[],
                    skipped=skipped_complex,
                    failed=[],
                ),
            }

        # Initialize and run PRCommentProcessor
        if self._comment_processor is None:
            self._comment_processor = PRCommentProcessor(
                config=self.config,
                working_dir=working_dir,
            )

        # Convert comments to processor format
        processor_comments = [
            {
                "id": str(c.id),
                "path": getattr(c, "path", None),
                "line": getattr(c, "line", None),
                "body": c.body,
                "addressed": c.addressed,
            }
            for c in filtered_comments
        ]

        # Run the processor
        try:
            processor_result = await self._comment_processor.run(
                {
                    "repo_name": repo_name,
                    "pr_number": pr_number,
                    "remote": "github",
                    "default_branch": "main",
                    "working_dir": working_dir,
                    "all_comments": processor_comments,
                }
            )
        except Exception as e:
            console.print(f"[red]Comment processor error: {e}[/red]")
            if not self.comment_config.continue_on_failure:
                raise
            return {
                **state,
                "current_step": "process_comments",
                "error": f"Comment processor failed: {e}",
                "comment_results": CommentProcessorResults(
                    addressed=[],
                    skipped=skipped_complex,
                    failed=[{"error": str(e)}],
                ),
            }

        # If fixes were applied, commit and push
        applied_count = processor_result.get("applied", 0)
        files_modified = processor_result.get("files_modified", [])
        commit_result: dict[str, Any] = {}

        if applied_count > 0:
            console.print(f"[green]Applied {applied_count} fix(es)[/green]")
            commit_result = await self._commit_and_push_fixes(
                working_dir=working_dir,
                branch_name=state.get("branch_name"),
                applied_count=applied_count,
                files_modified=files_modified,
            )

        # Convert processor result to CommentProcessorResults
        results = self._convert_processor_results(processor_result)

        # Merge in pre-filtered complex comments
        results["skipped"].extend(skipped_complex)

        return {
            **state,
            "current_step": "process_comments",
            "comment_results": results,
            "processor_summary": processor_result.get("summary"),
            "files_modified_by_processor": files_modified,
            "fix_verification_warning": commit_result.get("verification_warning"),
        }

    def _estimate_complexity(self, comment_body: str) -> int:
        """Estimate lines of code needed to address a comment."""
        # Simple heuristic based on comment length and keywords
        base = len(comment_body.split()) // 10
        if any(
            word in comment_body.lower()
            for word in ["refactor", "restructure", "rewrite"]
        ):
            base *= 3
        if any(word in comment_body.lower() for word in ["add", "implement", "create"]):
            base *= 2
        return max(base, 5)

    async def _commit_and_push_fixes(
        self,
        working_dir: str,
        branch_name: str | None,
        applied_count: int,
        files_modified: list[str] | None = None,
    ) -> dict[str, Any]:
        """Commit and push fixes applied by PRCommentProcessor.

        Includes a quick lint check on modified Python files (warns but doesn't block).

        Args:
            working_dir: Path to the worktree/working directory
            branch_name: Name of the branch to push to
            applied_count: Number of fixes applied (for commit message)
            files_modified: List of modified file paths for verification

        Returns:
            Dict with commit/push status and any verification warnings.
        """
        result: dict[str, Any] = {
            "committed": False,
            "pushed": False,
            "verification_warning": None,
        }

        # Quick lint check on modified files (warn but don't block)
        if files_modified:
            for file_path in files_modified:
                if file_path.endswith(".py"):
                    try:
                        verification = await verify(
                            file_path=file_path,
                            level=VerificationLevel.LINT,
                        )
                        if not verification.passed:
                            errors_preview = (
                                verification.errors[:2] if verification.errors else []
                            )
                            console.print(
                                f"[yellow]⚠️ Fix may have issues in {file_path}: "
                                f"{errors_preview}[/yellow]"
                            )
                            result["verification_warning"] = True
                    except Exception as e:
                        console.print(f"[dim]Could not verify {file_path}: {e}[/dim]")

        # Commit all changes
        commit_msg = (
            f"fix: Address {applied_count} review comment(s)\n\n"
            f"Auto-applied fixes from PR review comments.\n\n"
            f"🤖 Generated by Triangle Workflow"
        )

        commit_result = await commit_changes(
            worktree_path=working_dir,
            message=commit_msg,
            all_changes=True,  # Stage all modified files
        )

        if not commit_result.success:
            console.print(
                f"[yellow]Warning: Could not commit fixes: {commit_result.stderr}[/yellow]"
            )
            return result

        result["committed"] = True
        console.print("[dim]Committed fixes[/dim]")

        # Push to remote
        if branch_name:
            push_result = await push_branch(
                worktree_path=working_dir,
                branch_name=branch_name,
            )

            if push_result.success:
                console.print(
                    f"[green]Pushed {applied_count} fix(es) to {branch_name}[/green]"
                )
                result["pushed"] = True
            else:
                console.print(
                    f"[yellow]Warning: Could not push fixes: {push_result.stderr}[/yellow]"
                )
        else:
            console.print("[yellow]Warning: No branch name - skipping push[/yellow]")

        return result

    def _convert_processor_results(
        self, processor_result: dict[str, Any]
    ) -> CommentProcessorResults:
        """Convert PRCommentProcessor output to CommentProcessorResults.

        Args:
            processor_result: Output from PRCommentProcessor.run()

        Returns:
            CommentProcessorResults TypedDict with addressed/skipped/failed lists.
        """
        addressed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for detail in processor_result.get("details", []):
            entry = {
                "id": detail.get("comment_id"),
                "reason": detail.get("explanation", ""),
                "body": detail.get("comment_body", "")[:100],
            }

            status = detail.get("status")
            if status == "applied":
                addressed.append(entry)
            elif status == "skipped":
                skipped.append(entry)
            elif status == "failed":
                failed.append(entry)

        return CommentProcessorResults(
            addressed=addressed,
            skipped=skipped,
            failed=failed,
        )

    async def finalize(self, state: TriangleState) -> TriangleState:
        """Merge PR and create follow-up issues for unaddressed comments."""
        pr_number = state.get("pr_number")
        repo_name = state["repo_name"]
        comment_results = state.get("comment_results", {})

        if not pr_number:
            return {
                **state,
                "current_step": "completed",
                "error": "No PR number - cannot merge",
            }

        github = self.get_github_client(repo_name)

        # Mark PR as ready for review (removes draft status)
        console.print(f"[blue]Marking PR #{pr_number} as ready...[/blue]")
        ready_result = await github.mark_ready_for_review(pr_number=pr_number)
        if not ready_result.success:
            # If already ready, this might fail - continue anyway
            console.print(
                f"[yellow]Note: Could not mark PR ready: {ready_result.error}[/yellow]"
            )

        # Merge the PR
        console.print(f"[blue]Merging PR #{pr_number}...[/blue]")
        merge_result = await github.merge_pr(
            pr_number=pr_number,
            merge_method="squash",
        )

        if not merge_result.success:
            return {
                **state,
                "current_step": "finalize",
                "error": f"Failed to merge PR: {merge_result.error}",
            }

        console.print(f"[green]PR #{pr_number} merged![/green]")

        # Create follow-up issues for unaddressed comments
        unaddressed = comment_results.get("skipped", []) + comment_results.get(
            "failed", []
        )

        follow_up_issues = []
        for comment in unaddressed:
            if comment.get("reason") == "processor_integration_pending":
                # Skip placeholder entries
                continue

            issue = await self._create_follow_up_issue(
                comment=comment,
                original_pr=pr_number,
                repo=repo_name,
            )
            if issue:
                follow_up_issues.append(issue)
                console.print(f"[yellow]Created follow-up issue #{issue}[/yellow]")

        return {
            **state,
            "current_step": "completed",
            "follow_up_issues": follow_up_issues,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _create_follow_up_issue(
        self,
        comment: dict[str, Any],
        original_pr: int,
        repo: str,
    ) -> int | None:
        """Create a follow-up issue from an unaddressed comment."""
        comment_body = comment.get("body", "")
        comment_id = comment.get("id", "unknown")
        reason = comment.get("reason", "unaddressed")

        # Summarize the comment for title
        title_text = comment_body[:50].replace("\n", " ")
        if len(comment_body) > 50:
            title_text += "..."

        body = f"""## Context
This issue was auto-generated from an unaddressed review comment on PR #{original_pr}.

## Original Comment
> {comment_body}

**Comment ID:** {comment_id}
**Reason:** {reason}
**PR:** #{original_pr}

## Acceptance Criteria
- [ ] Address the reviewer's feedback
- [ ] Verify the fix doesn't introduce regressions

---

<details>
<summary>Auto-Implementation Metadata</summary>

```json
{{
  "auto_implement": true,
  "source": "pr_comment",
  "original_pr": {original_pr},
  "original_comment_id": "{comment_id}",
  "reason": "{reason}"
}}
```

</details>
"""

        github = self.get_github_client(repo)
        result = await github.create_issue(
            title=f"Follow-up: {title_text}",
            body=body,
            labels=["follow-up", "automated", "from-pr-review"],
        )

        if result.success:
            return result.data.number
        return None
