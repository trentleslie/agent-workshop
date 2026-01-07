"""Persistence layer for human-gated triangle workflows.

Wraps LangGraph's SqliteSaver for workflow state persistence, enabling
workflows to survive process restarts between human approval checkpoints.

Usage:
    from agent_workshop.utils.persistence import (
        get_checkpointer,
        TrianglePersistence,
    )

    # Get checkpointer for graph compilation
    checkpointer = get_checkpointer()
    graph = workflow.compile(checkpointer=checkpointer)

    # Query workflow states
    persistence = TrianglePersistence()
    pending = persistence.list_pending_approvals()
    state = persistence.get_thread_state("issue-42")
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.sqlite import SqliteSaver

if TYPE_CHECKING:
    from langgraph.checkpoint.base import CheckpointTuple

# Default state directory relative to working directory
DEFAULT_STATE_DIR = ".triangle"
DEFAULT_DB_NAME = "state.db"


def get_state_dir(base_dir: str | Path | None = None) -> Path:
    """Get or create the state directory.

    Args:
        base_dir: Base directory for state storage. Defaults to current directory.

    Returns:
        Path to the state directory (created if missing).
    """
    if base_dir is None:
        base_dir = Path.cwd()
    else:
        base_dir = Path(base_dir)

    state_dir = base_dir / DEFAULT_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_db_path(base_dir: str | Path | None = None) -> Path:
    """Get the path to the state database.

    Args:
        base_dir: Base directory for state storage.

    Returns:
        Path to the SQLite database file.
    """
    return get_state_dir(base_dir) / DEFAULT_DB_NAME


def get_checkpointer(
    db_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> SqliteSaver:
    """Factory function returning SqliteSaver configured for triangle workflows.

    Args:
        db_path: Explicit path to database file. If None, uses default location.
        base_dir: Base directory for state storage (ignored if db_path provided).

    Returns:
        Configured SqliteSaver instance.

    Example:
        checkpointer = get_checkpointer()
        graph = workflow.compile(checkpointer=checkpointer)
    """
    if db_path is None:
        db_path = get_db_path(base_dir)
    else:
        db_path = Path(db_path)
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

    return SqliteSaver.from_conn_string(str(db_path))


def make_thread_id(issue_number: int | None = None, epic_id: str | None = None) -> str:
    """Generate a thread ID following triangle conventions.

    Args:
        issue_number: GitHub issue number for issue-level workflows.
        epic_id: Epic identifier for epic-level orchestration.

    Returns:
        Thread ID string in format "issue-{number}" or "epic-{id}".

    Raises:
        ValueError: If neither issue_number nor epic_id is provided.
    """
    if issue_number is not None:
        return f"issue-{issue_number}"
    elif epic_id is not None:
        return f"epic-{epic_id}"
    else:
        raise ValueError("Either issue_number or epic_id must be provided")


def parse_thread_id(thread_id: str) -> dict[str, Any]:
    """Parse a thread ID into its components.

    Args:
        thread_id: Thread ID string.

    Returns:
        Dict with 'type' ('issue' or 'epic') and 'id' (number or string).
    """
    if thread_id.startswith("issue-"):
        return {"type": "issue", "id": int(thread_id[6:])}
    elif thread_id.startswith("epic-"):
        return {"type": "epic", "id": thread_id[5:]}
    else:
        return {"type": "unknown", "id": thread_id}


@dataclass
class PendingApproval:
    """Represents a workflow waiting for human approval."""

    thread_id: str
    current_step: str
    issue_number: int | None
    epic_id: str | None
    created_at: datetime | None
    last_updated: datetime | None
    state_values: dict[str, Any]

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        parsed = parse_thread_id(self.thread_id)
        if parsed["type"] == "issue":
            return f"Issue #{parsed['id']}"
        elif parsed["type"] == "epic":
            return f"Epic: {parsed['id']}"
        return self.thread_id


class TrianglePersistence:
    """State management wrapper for triangle workflows.

    Provides high-level query methods for CLI and orchestration:
    - Get current state for a thread
    - List all workflows waiting for human approval
    - Get execution history for a thread

    Example:
        persistence = TrianglePersistence()

        # List pending approvals for CLI display
        pending = persistence.list_pending_approvals()
        for p in pending:
            print(f"{p.display_name}: waiting at {p.current_step}")

        # Get specific thread state
        state = persistence.get_thread_state("issue-42")
        if state:
            print(f"Current step: {state['current_step']}")
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        base_dir: str | Path | None = None,
    ):
        """Initialize persistence wrapper.

        Args:
            db_path: Explicit path to database file.
            base_dir: Base directory for state storage.
        """
        if db_path is None:
            self.db_path = get_db_path(base_dir)
        else:
            self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(str(self.db_path))

    def _get_checkpointer(self) -> SqliteSaver:
        """Get a checkpointer instance."""
        return SqliteSaver.from_conn_string(str(self.db_path))

    def get_thread_state(self, thread_id: str) -> dict[str, Any] | None:
        """Get current state for a thread.

        Args:
            thread_id: Thread ID (e.g., "issue-42", "epic-v1").

        Returns:
            Current state values dict, or None if thread not found.
        """
        config = {"configurable": {"thread_id": thread_id}}

        with self._get_checkpointer() as checkpointer:
            checkpoint_tuple = checkpointer.get_tuple(config)
            if checkpoint_tuple is None:
                return None

            checkpoint = checkpoint_tuple.checkpoint
            return checkpoint.get("channel_values", {})

    def get_thread_config(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Get config dict for invoking a graph with this thread.

        Args:
            thread_id: Thread ID.
            checkpoint_id: Optional specific checkpoint to resume from.

        Returns:
            Config dict for graph.invoke().
        """
        config: dict[str, Any] = {
            "configurable": {"thread_id": thread_id}
        }
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        return config

    def list_pending_approvals(self) -> list[PendingApproval]:
        """List all workflows waiting for human approval.

        Scans all threads and returns those with requires_human_approval=True
        or that are at an interrupt point.

        Returns:
            List of PendingApproval objects.
        """
        pending: list[PendingApproval] = []

        if not self.db_path.exists():
            return pending

        # Query distinct thread IDs from checkpoints table
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # SqliteSaver stores checkpoints in a table with thread_id
            cursor.execute("""
                SELECT DISTINCT thread_id
                FROM checkpoints
                ORDER BY thread_id
            """)
            thread_ids = [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return pending
        finally:
            conn.close()

        # Check each thread for pending approval status
        with self._get_checkpointer() as checkpointer:
            for thread_id in thread_ids:
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint_tuple = checkpointer.get_tuple(config)

                if checkpoint_tuple is None:
                    continue

                state = checkpoint_tuple.checkpoint.get("channel_values", {})

                # Check if workflow is waiting for approval
                requires_approval = state.get("requires_human_approval", False)
                current_step = state.get("current_step", "unknown")

                # Also check if there's a pending_sends (interrupt indicator)
                has_pending = bool(
                    checkpoint_tuple.checkpoint.get("pending_sends", [])
                )

                if requires_approval or has_pending:
                    parsed = parse_thread_id(thread_id)
                    pending.append(
                        PendingApproval(
                            thread_id=thread_id,
                            current_step=current_step,
                            issue_number=(
                                parsed["id"] if parsed["type"] == "issue" else None
                            ),
                            epic_id=(
                                parsed["id"] if parsed["type"] == "epic" else None
                            ),
                            created_at=None,  # Could parse from checkpoint metadata
                            last_updated=None,
                            state_values=state,
                        )
                    )

        return pending

    def get_workflow_history(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> list[CheckpointTuple]:
        """Get execution history for a thread.

        Args:
            thread_id: Thread ID.
            limit: Maximum number of checkpoints to return.

        Returns:
            List of CheckpointTuple objects, most recent first.
        """
        config = {"configurable": {"thread_id": thread_id}}
        history: list[CheckpointTuple] = []

        with self._get_checkpointer() as checkpointer:
            for i, checkpoint in enumerate(checkpointer.list(config)):
                if i >= limit:
                    break
                history.append(checkpoint)

        return history

    def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread exists in the database.

        Args:
            thread_id: Thread ID to check.

        Returns:
            True if thread has at least one checkpoint.
        """
        return self.get_thread_state(thread_id) is not None

    def list_threads(self, thread_type: str | None = None) -> list[str]:
        """List all thread IDs.

        Args:
            thread_type: Optional filter ('issue' or 'epic').

        Returns:
            List of thread ID strings.
        """
        if not self.db_path.exists():
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT thread_id
                FROM checkpoints
                ORDER BY thread_id
            """)
            thread_ids = [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

        if thread_type:
            thread_ids = [
                tid for tid in thread_ids
                if parse_thread_id(tid)["type"] == thread_type
            ]

        return thread_ids
