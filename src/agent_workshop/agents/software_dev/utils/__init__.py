"""Utility modules for software development agents.

This package provides shared utilities:
- git_operations: Git worktree and branch management
- verification: Tiered verification system (SCHEMA → SYNTAX → LINT → TYPE → TEST)
"""

from agent_workshop.agents.software_dev.utils.git_operations import (
    GitResult,
    cleanup_worktree,
    commit_changes,
    create_branch,
    get_changed_files,
    get_current_branch,
    get_worktree_path,
    list_worktrees,
    push_branch,
    sanitize_branch_name,
    setup_worktree,
)
from agent_workshop.agents.software_dev.utils.verification import (
    VerificationConfig,
    VerificationLevel,
    VerificationResult,
    verify,
)

__all__ = [
    # Git operations
    "GitResult",
    "cleanup_worktree",
    "commit_changes",
    "create_branch",
    "get_changed_files",
    "get_current_branch",
    "get_worktree_path",
    "list_worktrees",
    "push_branch",
    "sanitize_branch_name",
    "setup_worktree",
    # Verification
    "VerificationConfig",
    "VerificationLevel",
    "VerificationResult",
    "verify",
]
