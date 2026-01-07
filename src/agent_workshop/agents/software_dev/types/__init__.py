"""Types submodule for Compound Engineering Triangle workflows.

This module provides shared type definitions used across the triangle:
- IssueToPR → PRPipeline → PRCommentProcessor

Types are organized into three categories:
1. State types (TypedDict for LangGraph compatibility)
2. Metrics types (dataclasses and Pydantic for observability)
3. GitHub types (Pydantic models for external integration)

Usage:
    from agent_workshop.agents.software_dev.types import (
        TriangleState,
        IssueSpecification,
        CompoundMetrics,
    )
"""

from agent_workshop.agents.software_dev.types.github import (
    CommentFix,
    CreatedIssue,
    FeedbackSummary,
    PRInfo,
    ReviewComment,
)
from agent_workshop.agents.software_dev.types.metrics import (
    CommentProcessorQuality,
    CompoundMetrics,
    NodeExecution,
    PRReviewQuality,
    WorkflowExecution,
)
from agent_workshop.agents.software_dev.types.state import (
    CommentProcessorResults,
    IssueSpecification,
    IssueToPRState,
    TriangleState,
    VerificationResult,
)

__all__ = [
    # State types (LangGraph compatible)
    "TriangleState",
    "IssueToPRState",
    "CommentProcessorResults",
    "IssueSpecification",
    "VerificationResult",
    # Metrics types (operational, quality, compound)
    "NodeExecution",
    "WorkflowExecution",
    "PRReviewQuality",
    "CommentProcessorQuality",
    "CompoundMetrics",
    # GitHub types (external integration)
    "CreatedIssue",
    "PRInfo",
    "ReviewComment",
    "CommentFix",
    "FeedbackSummary",
]
