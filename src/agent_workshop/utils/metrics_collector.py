"""3-layer metrics collection framework for triangle workflow observability.

Tracks operational, quality, and compound engineering metrics with
context managers for hierarchical nesting (cycle > workflow > node).

Usage:
    from agent_workshop.utils.metrics_collector import MetricsCollector

    collector = MetricsCollector()

    # Track a complete triangle cycle
    async with collector.track_cycle(issue_number=42) as cycle:
        # Track individual workflow
        async with collector.track_workflow("issue_to_pr") as workflow:
            # Track node execution
            async with collector.track_node("generate_code") as node:
                # Record LLM call within node
                collector.record_llm_call(
                    prompt_tokens=1000,
                    completion_tokens=500,
                    model="claude-sonnet-4-20250514",
                )

    # Get compound metrics
    print(f"Compound score: {cycle.compound_score}")
"""

from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

# Default metrics directory
DEFAULT_METRICS_DIR = ".triangle/metrics"
PENDING_FILE = "pending.jsonl"


# Cost per 1M tokens (approximate, update as needed)
MODEL_COSTS = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o": {"input": 5.0, "output": 15.0},
}
DEFAULT_COST = {"input": 3.0, "output": 15.0}


def _estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
) -> float:
    """Estimate cost in USD for an LLM call."""
    costs = MODEL_COSTS.get(model, DEFAULT_COST)
    input_cost = (prompt_tokens / 1_000_000) * costs["input"]
    output_cost = (completion_tokens / 1_000_000) * costs["output"]
    return input_cost + output_cost


@dataclass
class NodeMetrics:
    """Metrics for a single node execution."""

    node_name: str
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None

    # LLM usage
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    # Status
    status: str = "pending"  # pending, running, success, failure, skipped
    error_message: str | None = None
    retries: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds()
        return 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "node_name": self.node_name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
            "status": self.status,
            "error_message": self.error_message,
            "retries": self.retries,
        }


@dataclass
class WorkflowMetrics:
    """Metrics for a workflow execution."""

    workflow_name: str
    run_id: str
    thread_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None

    # Node metrics
    nodes: list[NodeMetrics] = field(default_factory=list)

    # Status
    status: str = "pending"  # pending, running, success, failure, partial
    error_message: str | None = None

    # Quality metrics (populated after completion)
    verification_passed: bool | None = None
    verification_level: str | None = None  # highest level passed

    # For PR review quality
    issues_raised: int = 0
    true_positives: int = 0
    false_positives: int = 0

    # For comment processor quality
    comments_processed: int = 0
    fixes_applied: int = 0
    fixes_failed: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration."""
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds()
        return sum(n.duration_seconds for n in self.nodes)

    @property
    def total_llm_calls(self) -> int:
        """Total LLM calls across all nodes."""
        return sum(n.llm_calls for n in self.nodes)

    @property
    def total_tokens(self) -> int:
        """Total tokens across all nodes."""
        return sum(n.total_tokens for n in self.nodes)

    @property
    def total_cost_usd(self) -> float:
        """Total cost across all nodes."""
        return sum(n.cost_usd for n in self.nodes)

    @property
    def precision(self) -> float:
        """Review precision: TP / (TP + FP)."""
        total = self.true_positives + self.false_positives
        return self.true_positives / total if total > 0 else 1.0

    @property
    def fix_rate(self) -> float:
        """Fix application rate."""
        total = self.fixes_applied + self.fixes_failed
        return self.fixes_applied / total if total > 0 else 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_name": self.workflow_name,
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "error_message": self.error_message,
            "nodes": [n.to_dict() for n in self.nodes],
            "total_llm_calls": self.total_llm_calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "verification_passed": self.verification_passed,
            "precision": self.precision,
            "fix_rate": self.fix_rate,
        }


@dataclass
class CycleMetrics:
    """Metrics for a complete triangle cycle."""

    issue_number: int
    cycle_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None

    # Workflow metrics
    workflows: list[WorkflowMetrics] = field(default_factory=list)

    # Status
    status: str = "pending"  # pending, running, success, failure
    error_message: str | None = None

    # Lines changed (for velocity)
    lines_added: int = 0
    lines_deleted: int = 0

    # Human interventions
    human_interventions: int = 0
    total_iterations: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate total cycle duration."""
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds()
        return sum(w.duration_seconds for w in self.workflows)

    @property
    def total_cost_usd(self) -> float:
        """Total cost across all workflows."""
        return sum(w.total_cost_usd for w in self.workflows)

    @property
    def total_tokens(self) -> int:
        """Total tokens across all workflows."""
        return sum(w.total_tokens for w in self.workflows)

    @property
    def lines_changed(self) -> int:
        """Total lines changed."""
        return self.lines_added + self.lines_deleted

    # Compound metrics

    @property
    def velocity_score(self) -> float:
        """V score: lines per second + verification success rate."""
        if self.duration_seconds == 0:
            return 0.0

        # Lines per second (normalize: 10 l/s = 100)
        lps = self.lines_changed / self.duration_seconds
        speed_component = min(lps * 10, 100)

        # Verification pass rate
        passed = sum(1 for w in self.workflows if w.verification_passed)
        total = len([w for w in self.workflows if w.verification_passed is not None])
        verify_rate = passed / total if total > 0 else 1.0
        verify_component = verify_rate * 100

        return (speed_component * 0.4) + (verify_component * 0.6)

    @property
    def feedback_quality_score(self) -> float:
        """FQ score: review precision (F1 approximation)."""
        # Aggregate precision across review workflows
        precisions = [w.precision for w in self.workflows if w.issues_raised > 0]
        if not precisions:
            return 100.0
        return (sum(precisions) / len(precisions)) * 100

    @property
    def iteration_frequency_score(self) -> float:
        """IF score: fix rate + autonomy rate."""
        # Fix application rate
        fix_rates = [w.fix_rate for w in self.workflows if w.comments_processed > 0]
        fix_component = (sum(fix_rates) / len(fix_rates) * 100) if fix_rates else 100.0

        # Autonomy rate
        if self.total_iterations > 0:
            autonomous = self.total_iterations - self.human_interventions
            autonomy = autonomous / self.total_iterations
        else:
            autonomy = 1.0
        autonomy_component = autonomy * 100

        return (fix_component * 0.5) + (autonomy_component * 0.5)

    @property
    def compound_score(self) -> float:
        """V × FQ × IF compound score (0-100)."""
        v = max(self.velocity_score / 100, 0.01)
        fq = max(self.feedback_quality_score / 100, 0.01)
        if_score = max(self.iteration_frequency_score / 100, 0.01)

        # Geometric mean normalized to 100
        return ((v * fq * if_score) ** (1 / 3)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issue_number": self.issue_number,
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "error_message": self.error_message,
            "workflows": [w.to_dict() for w in self.workflows],
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "human_interventions": self.human_interventions,
            "velocity_score": self.velocity_score,
            "feedback_quality_score": self.feedback_quality_score,
            "iteration_frequency_score": self.iteration_frequency_score,
            "compound_score": self.compound_score,
        }


class MetricsCollector:
    """Thread-safe metrics collector with context managers.

    Collects 3 layers of metrics:
    1. Operational: duration, tokens, cost per node
    2. Quality: precision, recall, pass rates per workflow
    3. Compound: V × FQ × IF score per cycle

    Metrics are buffered locally to .triangle/metrics/pending.jsonl
    when Langfuse is unavailable.

    Example:
        collector = MetricsCollector()

        async with collector.track_cycle(issue_number=42) as cycle:
            async with collector.track_workflow("issue_to_pr") as workflow:
                async with collector.track_node("generate_code") as node:
                    collector.record_llm_call(
                        prompt_tokens=1000,
                        completion_tokens=500,
                    )
                    node.status = "success"
                workflow.verification_passed = True

        # Metrics are automatically saved on context exit
    """

    def __init__(
        self,
        metrics_dir: str | Path | None = None,
        buffer_to_file: bool = True,
        langfuse_enabled: bool = True,
    ):
        """Initialize metrics collector.

        Args:
            metrics_dir: Directory for metrics storage.
            buffer_to_file: Whether to buffer metrics to file.
            langfuse_enabled: Whether to send metrics to Langfuse.
        """
        self.metrics_dir = Path(metrics_dir) if metrics_dir else Path(DEFAULT_METRICS_DIR)
        self.buffer_to_file = buffer_to_file
        self.langfuse_enabled = langfuse_enabled

        # Thread-safe state
        self._lock = threading.Lock()
        self._current_cycle: CycleMetrics | None = None
        self._current_workflow: WorkflowMetrics | None = None
        self._current_node: NodeMetrics | None = None

        # Completed metrics
        self._completed_cycles: list[CycleMetrics] = []

    def _ensure_dir(self) -> None:
        """Ensure metrics directory exists."""
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def _buffer_metrics(self, metrics: dict[str, Any]) -> None:
        """Buffer metrics to local file."""
        if not self.buffer_to_file:
            return

        self._ensure_dir()
        pending_file = self.metrics_dir / PENDING_FILE

        with self._lock:
            with open(pending_file, "a") as f:
                f.write(json.dumps(metrics) + "\n")

    def _generate_id(self, prefix: str = "run") -> str:
        """Generate a unique ID."""
        import uuid
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    @asynccontextmanager
    async def track_cycle(
        self,
        issue_number: int,
        cycle_id: str | None = None,
    ) -> AsyncIterator[CycleMetrics]:
        """Track a complete triangle cycle.

        Args:
            issue_number: GitHub issue number.
            cycle_id: Optional cycle ID (auto-generated if None).

        Yields:
            CycleMetrics instance for the cycle.
        """
        if cycle_id is None:
            cycle_id = self._generate_id("cycle")

        cycle = CycleMetrics(
            issue_number=issue_number,
            cycle_id=cycle_id,
            started_at=datetime.now(),
            status="running",
        )

        with self._lock:
            self._current_cycle = cycle

        try:
            yield cycle
            cycle.status = "success"
        except Exception as e:
            cycle.status = "failure"
            cycle.error_message = str(e)
            raise
        finally:
            cycle.ended_at = datetime.now()

            with self._lock:
                self._current_cycle = None
                self._completed_cycles.append(cycle)

            # Buffer to file
            self._buffer_metrics({
                "type": "cycle",
                "data": cycle.to_dict(),
            })

    @asynccontextmanager
    async def track_workflow(
        self,
        workflow_name: str,
        run_id: str | None = None,
        thread_id: str = "",
    ) -> AsyncIterator[WorkflowMetrics]:
        """Track a workflow execution.

        Must be called within a track_cycle context.

        Args:
            workflow_name: Name of the workflow (e.g., "issue_to_pr").
            run_id: Optional run ID (auto-generated if None).
            thread_id: Thread ID for persistence.

        Yields:
            WorkflowMetrics instance for the workflow.
        """
        if run_id is None:
            run_id = self._generate_id("run")

        workflow = WorkflowMetrics(
            workflow_name=workflow_name,
            run_id=run_id,
            thread_id=thread_id,
            started_at=datetime.now(),
            status="running",
        )

        with self._lock:
            if self._current_cycle:
                self._current_cycle.workflows.append(workflow)
            self._current_workflow = workflow

        try:
            yield workflow
            if workflow.status == "running":
                workflow.status = "success"
        except Exception as e:
            workflow.status = "failure"
            workflow.error_message = str(e)
            raise
        finally:
            workflow.ended_at = datetime.now()

            with self._lock:
                self._current_workflow = None

    @asynccontextmanager
    async def track_node(
        self,
        node_name: str,
    ) -> AsyncIterator[NodeMetrics]:
        """Track a node execution.

        Must be called within a track_workflow context.

        Args:
            node_name: Name of the node.

        Yields:
            NodeMetrics instance for the node.
        """
        node = NodeMetrics(
            node_name=node_name,
            started_at=datetime.now(),
            status="running",
        )

        with self._lock:
            if self._current_workflow:
                self._current_workflow.nodes.append(node)
            self._current_node = node

        try:
            yield node
            if node.status == "running":
                node.status = "success"
        except Exception as e:
            node.status = "failure"
            node.error_message = str(e)
            raise
        finally:
            node.ended_at = datetime.now()

            with self._lock:
                self._current_node = None

    def record_llm_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "claude-sonnet-4-20250514",
        cost_usd: float | None = None,
    ) -> None:
        """Record an LLM call within the current node.

        Args:
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.
            model: Model name for cost estimation.
            cost_usd: Explicit cost (estimated if None).
        """
        if cost_usd is None:
            cost_usd = _estimate_cost(prompt_tokens, completion_tokens, model)

        with self._lock:
            if self._current_node:
                self._current_node.llm_calls += 1
                self._current_node.prompt_tokens += prompt_tokens
                self._current_node.completion_tokens += completion_tokens
                self._current_node.cost_usd += cost_usd

    def record_lines_changed(
        self,
        lines_added: int,
        lines_deleted: int,
    ) -> None:
        """Record lines changed in the current cycle.

        Args:
            lines_added: Lines added.
            lines_deleted: Lines deleted.
        """
        with self._lock:
            if self._current_cycle:
                self._current_cycle.lines_added += lines_added
                self._current_cycle.lines_deleted += lines_deleted

    def record_human_intervention(self) -> None:
        """Record a human intervention in the current cycle."""
        with self._lock:
            if self._current_cycle:
                self._current_cycle.human_interventions += 1
                self._current_cycle.total_iterations += 1

    def record_autonomous_iteration(self) -> None:
        """Record an autonomous iteration in the current cycle."""
        with self._lock:
            if self._current_cycle:
                self._current_cycle.total_iterations += 1

    def get_completed_cycles(self) -> list[CycleMetrics]:
        """Get all completed cycles."""
        with self._lock:
            return list(self._completed_cycles)

    def get_pending_metrics(self) -> list[dict[str, Any]]:
        """Read pending metrics from buffer file."""
        pending_file = self.metrics_dir / PENDING_FILE

        if not pending_file.exists():
            return []

        metrics = []
        with open(pending_file) as f:
            for line in f:
                if line.strip():
                    metrics.append(json.loads(line))
        return metrics

    def clear_pending_metrics(self) -> None:
        """Clear the pending metrics buffer."""
        pending_file = self.metrics_dir / PENDING_FILE
        if pending_file.exists():
            pending_file.unlink()
