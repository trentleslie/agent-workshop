"""State type definitions for Compound Engineering Triangle workflows.

This module defines TypedDict-based state types required for LangGraph compatibility.
TypedDict is used instead of Pydantic to ensure proper state checkpointing and restoration.
"""

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class TriangleState(TypedDict, total=False):
    """Unified state for Triangle Orchestrator workflow.

    This state flows through the IssueToPR → PRPipeline → PRCommentProcessor triangle.
    Uses total=False to allow optional fields during partial state updates.
    """

    # Issue context
    issue_number: int
    repo_name: str
    branch_name: str
    working_dir: str

    # Workflow results (populated as triangle progresses)
    issue_to_pr_result: dict[str, Any] | None
    pr_pipeline_result: dict[str, Any] | None
    comment_processor_result: dict[str, Any] | None

    # PR metadata (populated after IssueToPR completes)
    pr_number: int | None
    pr_url: str | None

    # Flow control
    current_step: str
    approved_steps: list[str]
    requires_human_approval: bool

    # Metrics collection
    metrics: dict[str, Any]

    # Error handling
    error: str | None
    retry_count: int


class IssueSpecification(BaseModel):
    """Parsed GitHub issue specification.

    Extracted from issue body with structured sections for implementation.
    """

    title: str = Field(description="Issue title")
    body: str = Field(description="Raw issue body markdown")
    requirements: list[str] = Field(
        default_factory=list,
        description="Extracted requirements from issue body",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Extracted acceptance criteria",
    )
    files_to_create: list[str] = Field(
        default_factory=list,
        description="Files to be created",
    )
    files_to_modify: list[str] = Field(
        default_factory=list,
        description="Files to be modified",
    )
    branch_name: str = Field(description="Target branch name from metadata")
    complexity: str = Field(
        default="medium",
        description="Estimated complexity: simple, medium, complex",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Issue dependencies (e.g., ['#3', '#5'])",
    )


class VerificationResult(TypedDict, total=False):
    """Tiered verification output from self-verification node.

    Each tier is evaluated in order: SCHEMA → SYNTAX → LINT → TYPE → TEST.
    Verification stops at first failure tier.
    """

    # Overall result
    level: str  # "schema", "syntax", "lint", "type", "test"
    passed: bool
    highest_passing_level: str | None

    # Per-tier results
    schema_valid: bool | None
    syntax_valid: bool | None
    lint_valid: bool | None
    types_valid: bool | None
    tests_pass: bool | None

    # Error details
    errors: list[str]
    warnings: list[str]

    # Tier-specific output
    lint_output: str | None
    type_output: str | None
    test_output: str | None

    # Timing
    duration_seconds: float
