"""GitHub-related type definitions for Compound Engineering workflows.

Types for tracking issues, PRs, comments, and human feedback.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreatedIssue(BaseModel):
    """Record of a created GitHub issue.

    Output from PlanToIssues workflow.
    """

    task_title: str = Field(description="Issue title")
    issue_number: int = Field(description="GitHub issue number")
    issue_url: str = Field(description="Full URL to the issue")
    branch_name: str = Field(description="Target branch from metadata")
    complexity: str = Field(
        default="medium",
        description="Estimated complexity",
    )
    priority: str = Field(
        default="medium",
        description="Issue priority",
    )
    epic_id: str | None = Field(
        default=None,
        description="Parent epic identifier",
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="Issue numbers this depends on",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When the issue was created",
    )


class PRInfo(BaseModel):
    """Pull request metadata.

    Tracks PR state through the triangle workflow.
    """

    pr_number: int = Field(description="GitHub PR number")
    pr_url: str = Field(description="Full URL to the PR")
    title: str = Field(description="PR title")
    branch_name: str = Field(description="Source branch")
    base_branch: str = Field(
        default="main",
        description="Target branch for merge",
    )
    state: Literal["open", "closed", "merged", "draft"] = Field(
        default="draft",
        description="PR state",
    )
    issue_number: int | None = Field(
        default=None,
        description="Linked issue number",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When the PR was created",
    )
    files_changed: int = Field(
        default=0,
        description="Number of files changed",
    )
    additions: int = Field(
        default=0,
        description="Lines added",
    )
    deletions: int = Field(
        default=0,
        description="Lines deleted",
    )


class CommentFix(BaseModel):
    """Per-comment fix tracking for PRCommentProcessor.

    Records the outcome of attempting to apply a fix for a review comment.
    """

    comment_id: str = Field(description="GitHub comment ID")
    file_path: str = Field(description="File the comment references")
    line_number: int | None = Field(
        default=None,
        description="Line number if inline comment",
    )
    comment_body: str = Field(description="The review comment text")
    outcome: Literal["applied", "skipped", "failed"] = Field(
        description="Fix attempt outcome",
    )
    attempts: int = Field(
        default=1,
        description="Number of fix attempts",
    )
    fix_description: str | None = Field(
        default=None,
        description="Description of the fix applied",
    )
    tests_passed_after: bool | None = Field(
        default=None,
        description="Whether tests passed after fix",
    )
    human_approved: bool | None = Field(
        default=None,
        description="Human approval status (from reactions)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if failed",
    )


class ReviewComment(BaseModel):
    """A PR review comment to be processed.

    Input to PRCommentProcessor workflow.
    """

    comment_id: str = Field(description="GitHub comment ID")
    author: str = Field(description="Comment author username")
    body: str = Field(description="Comment text")
    file_path: str | None = Field(
        default=None,
        description="File path for inline comments",
    )
    line_number: int | None = Field(
        default=None,
        description="Line number for inline comments",
    )
    is_resolved: bool = Field(
        default=False,
        description="Whether comment is marked resolved",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When comment was created",
    )
    source_type: Literal["greptile", "human", "bot"] = Field(
        default="human",
        description="Source of the comment",
    )


class FeedbackSummary(BaseModel):
    """Aggregated human feedback from GitHub reactions.

    Used to calculate review quality metrics.
    """

    # Review feedback
    true_positives: int = Field(
        default=0,
        description="Issues confirmed valid (thumbs up on review)",
    )
    false_positives: int = Field(
        default=0,
        description="Issues marked incorrect (thumbs down on review)",
    )

    # Fix feedback
    fixes_approved: int = Field(
        default=0,
        description="Fixes accepted (rocket reaction)",
    )
    fixes_rejected: int = Field(
        default=0,
        description="Fixes rejected (thumbs down on fix)",
    )

    # Comment resolution
    comments_resolved: int = Field(
        default=0,
        description="Comments marked as resolved",
    )
    comments_unresolved: int = Field(
        default=0,
        description="Comments still open",
    )

    @property
    def total_review_feedback(self) -> int:
        """Total review reactions received."""
        return self.true_positives + self.false_positives

    @property
    def total_fix_feedback(self) -> int:
        """Total fix reactions received."""
        return self.fixes_approved + self.fixes_rejected

    @property
    def review_accuracy(self) -> float:
        """Percentage of reviews marked as valid."""
        total = self.total_review_feedback
        if total == 0:
            return 1.0
        return self.true_positives / total

    @property
    def fix_acceptance_rate(self) -> float:
        """Percentage of fixes accepted."""
        total = self.total_fix_feedback
        if total == 0:
            return 1.0
        return self.fixes_approved / total
