"""Metrics type definitions for Compound Engineering observability.

Three layers of metrics:
1. Operational: Duration, tokens, cost per node/workflow
2. Quality: Precision, recall, F1 for PR reviews; pass rates for verification
3. Compound: V × FQ × IF score combining all dimensions
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


@dataclass
class NodeExecution:
    """Per-node operational metrics.

    Captures LLM usage and timing for a single workflow node.
    """

    node_name: str
    started_at: datetime
    ended_at: datetime | None = None
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    status: Literal["pending", "running", "success", "failure", "skipped"] = "pending"
    error_message: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate duration if ended."""
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def total_tokens(self) -> int:
        """Total tokens used in this node."""
        return self.prompt_tokens + self.completion_tokens


@dataclass
class WorkflowExecution:
    """Per-workflow operational metrics.

    Aggregates node executions for a complete workflow run.
    """

    workflow_name: str
    run_id: str
    thread_id: str
    started_at: datetime
    ended_at: datetime | None = None
    node_executions: list[NodeExecution] = field(default_factory=list)
    status: Literal["pending", "running", "success", "failure", "partial"] = "pending"
    error_message: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate total workflow duration."""
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def total_llm_calls(self) -> int:
        """Sum of LLM calls across all nodes."""
        return sum(n.llm_calls for n in self.node_executions)

    @property
    def total_tokens(self) -> int:
        """Sum of tokens across all nodes."""
        return sum(n.total_tokens for n in self.node_executions)

    @property
    def total_cost_usd(self) -> float:
        """Sum of costs across all nodes."""
        return sum(n.cost_usd for n in self.node_executions)


class PRReviewQuality(BaseModel):
    """Quality metrics for PR review feedback.

    Tracks true/false positives to calculate precision and recall.
    """

    # Issue counts by severity
    security_issues: dict[str, int] = Field(
        default_factory=dict,
        description="Security issues by severity (critical, high, medium, low)",
    )
    quality_issues: dict[str, int] = Field(
        default_factory=dict,
        description="Quality issues by category",
    )

    # Review outcome
    recommendation: Literal["approve", "request_changes", "comment"] = Field(
        description="Final review recommendation",
    )
    blocking_issues: int = Field(
        default=0,
        description="Number of issues blocking approval",
    )

    # Feedback accuracy (populated from human reactions)
    true_positives: int = Field(
        default=0,
        description="Issues confirmed as valid by human feedback",
    )
    false_positives: int = Field(
        default=0,
        description="Issues marked as incorrect by human feedback",
    )
    total_issues_raised: int = Field(
        default=0,
        description="Total number of issues raised in review",
    )

    @computed_field
    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP). How many raised issues were valid."""
        total = self.true_positives + self.false_positives
        if total == 0:
            return 1.0  # No issues means perfect precision
        return self.true_positives / total


class CommentProcessorQuality(BaseModel):
    """Quality metrics for comment processing iteration.

    Tracks fix application success rate.
    """

    total_comments: int = Field(
        default=0,
        description="Total comments processed",
    )
    applied: int = Field(
        default=0,
        description="Fixes successfully applied",
    )
    skipped: int = Field(
        default=0,
        description="Comments skipped (not auto-fixable)",
    )
    failed: int = Field(
        default=0,
        description="Fix attempts that failed",
    )
    fixes: list[dict] = Field(
        default_factory=list,
        description="Detailed fix records",
    )

    @computed_field
    @property
    def application_rate(self) -> float:
        """Percentage of comments that resulted in applied fixes."""
        if self.total_comments == 0:
            return 1.0
        return self.applied / self.total_comments

    @computed_field
    @property
    def success_rate(self) -> float:
        """Percentage of attempted fixes that succeeded."""
        attempted = self.applied + self.failed
        if attempted == 0:
            return 1.0
        return self.applied / attempted


@dataclass
class CompoundMetrics:
    """V × FQ × IF compound engineering score.

    Combines three dimensions into a single productivity metric:
    - V (Velocity): Speed and self-verification success
    - FQ (Feedback Quality): Precision and usefulness of reviews
    - IF (Iteration Frequency): Fix application and autonomy
    """

    # Velocity components (V)
    lines_changed: int = 0
    duration_seconds: float = 0.0
    self_verification_attempts: int = 0
    self_verification_passes: int = 0

    # Feedback Quality components (FQ)
    review_true_positives: int = 0
    review_false_positives: int = 0
    review_total_issues: int = 0

    # Iteration Frequency components (IF)
    total_fixes_attempted: int = 0
    fixes_applied_first_try: int = 0
    human_interventions: int = 0
    total_iterations: int = 0

    @property
    def lines_per_second(self) -> float:
        """Code velocity: lines changed per second."""
        if self.duration_seconds == 0:
            return 0.0
        return self.lines_changed / self.duration_seconds

    @property
    def self_verification_pass_rate(self) -> float:
        """Percentage of verification attempts that passed."""
        if self.self_verification_attempts == 0:
            return 1.0
        return self.self_verification_passes / self.self_verification_attempts

    @property
    def velocity_score(self) -> float:
        """V score: weighted combination of speed and verification success."""
        # Normalize lines/second (assume 10 l/s is excellent = 100)
        speed_component = min(self.lines_per_second * 10, 100)
        verification_component = self.self_verification_pass_rate * 100
        # Weight: 40% speed, 60% verification quality
        return (speed_component * 0.4) + (verification_component * 0.6)

    @property
    def review_precision(self) -> float:
        """Precision of review feedback."""
        total = self.review_true_positives + self.review_false_positives
        if total == 0:
            return 1.0
        return self.review_true_positives / total

    @property
    def review_recall(self) -> float:
        """Recall - currently estimated as TP / total issues raised."""
        if self.review_total_issues == 0:
            return 1.0
        return min(self.review_true_positives / self.review_total_issues, 1.0)

    @property
    def review_f1(self) -> float:
        """F1 score combining precision and recall."""
        p, r = self.review_precision, self.review_recall
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    @property
    def feedback_quality_score(self) -> float:
        """FQ score: F1 score scaled to 0-100."""
        return self.review_f1 * 100

    @property
    def fix_application_rate(self) -> float:
        """Percentage of fixes applied on first attempt."""
        if self.total_fixes_attempted == 0:
            return 1.0
        return self.fixes_applied_first_try / self.total_fixes_attempted

    @property
    def autonomy_rate(self) -> float:
        """Percentage of iterations without human intervention."""
        if self.total_iterations == 0:
            return 1.0
        autonomous = self.total_iterations - self.human_interventions
        return autonomous / self.total_iterations

    @property
    def iteration_frequency_score(self) -> float:
        """IF score: weighted combination of fix rate and autonomy."""
        # Weight: 50% fix application, 50% autonomy
        fix_component = self.fix_application_rate * 100
        autonomy_component = self.autonomy_rate * 100
        return (fix_component * 0.5) + (autonomy_component * 0.5)

    @property
    def compound_score(self) -> float:
        """Final V × FQ × IF compound score.

        Uses geometric mean to normalize across dimensions.
        Result is 0-100 scale.
        """
        v = self.velocity_score / 100
        fq = self.feedback_quality_score / 100
        if_score = self.iteration_frequency_score / 100

        # Avoid zero in geometric mean
        v = max(v, 0.01)
        fq = max(fq, 0.01)
        if_score = max(if_score, 0.01)

        # Geometric mean normalized to 100
        return ((v * fq * if_score) ** (1 / 3)) * 100
