"""Git operations utilities for managing worktrees, branches, and commits.

Enables isolated development environments for parallel issue processing
using git worktrees.

Usage:
    from agent_workshop.agents.software_dev.utils.git_operations import (
        setup_worktree,
        create_branch,
        commit_changes,
        push_branch,
        cleanup_worktree,
    )

    # Create isolated worktree for an issue
    worktree_path = await setup_worktree(
        repo_path="/path/to/repo",
        branch_name="auto/triangle-v1/issue-42",
    )

    # Make changes, then commit
    await commit_changes(
        worktree_path,
        message="feat: implement new feature",
        files=["src/module.py"],
    )

    # Push to remote
    await push_branch(worktree_path, "auto/triangle-v1/issue-42")
"""

from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

# Default directory for worktrees (relative to repo root)
DEFAULT_WORKTREE_DIR = ".triangle-worktrees"


@dataclass
class GitResult:
    """Result of a git operation."""

    success: bool
    stdout: str
    stderr: str
    returncode: int

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        return f"{self.stdout}\n{self.stderr}".strip()

    @property
    def error_message(self) -> str | None:
        """Extract error message if operation failed."""
        if self.success:
            return None
        return self.stderr or self.stdout or "Unknown error"


async def _run_git(
    args: list[str],
    cwd: str | Path | None = None,
    timeout: int = 60,
) -> GitResult:
    """Run a git command asynchronously.

    Uses create_subprocess_exec for safe execution (no shell injection).

    Args:
        args: Git command arguments (without 'git' prefix).
        cwd: Working directory for the command.
        timeout: Command timeout in seconds.

    Returns:
        GitResult with output and status.
    """
    cmd = ["git"] + args

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        return GitResult(
            success=proc.returncode == 0,
            stdout=stdout.decode("utf-8", errors="replace").strip(),
            stderr=stderr.decode("utf-8", errors="replace").strip(),
            returncode=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return GitResult(
            success=False,
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
            returncode=-1,
        )
    except FileNotFoundError:
        return GitResult(
            success=False,
            stdout="",
            stderr="git command not found",
            returncode=-1,
        )


def sanitize_branch_name(name: str) -> str:
    """Sanitize a string for use as a git branch name.

    Args:
        name: Raw branch name.

    Returns:
        Sanitized branch name safe for git.
    """
    # Replace invalid characters with hyphens
    sanitized = re.sub(r"[^a-zA-Z0-9/_.-]", "-", name)
    # Remove consecutive hyphens
    sanitized = re.sub(r"-+", "-", sanitized)
    # Remove leading/trailing hyphens and dots
    sanitized = sanitized.strip("-.")
    # Ensure it doesn't start with a slash
    sanitized = sanitized.lstrip("/")
    return sanitized


def get_worktree_path(
    repo_path: str | Path,
    branch_name: str,
    worktree_dir: str = DEFAULT_WORKTREE_DIR,
) -> Path:
    """Get the path where a worktree would be created.

    Args:
        repo_path: Path to the main repository.
        branch_name: Branch name (will be sanitized for directory name).
        worktree_dir: Parent directory for worktrees.

    Returns:
        Path to the worktree directory.
    """
    repo_path = Path(repo_path)
    # Use sanitized branch name as directory name
    dir_name = sanitize_branch_name(branch_name).replace("/", "_")
    return repo_path / worktree_dir / dir_name


async def get_default_branch(repo_path: str | Path) -> str:
    """Get the default branch name (main or master).

    Args:
        repo_path: Path to the repository.

    Returns:
        Default branch name.
    """
    # Try to get from remote HEAD
    result = await _run_git(
        ["symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
        cwd=repo_path,
    )

    if result.success:
        # Returns something like "origin/main"
        return result.stdout.replace("origin/", "")

    # Fallback to checking if main or master exists
    for branch in ["main", "master"]:
        result = await _run_git(
            ["rev-parse", "--verify", f"refs/heads/{branch}"],
            cwd=repo_path,
        )
        if result.success:
            return branch

    return "main"  # Default assumption


async def create_branch(
    repo_path: str | Path,
    branch_name: str,
    base_branch: str | None = None,
    checkout: bool = False,
) -> GitResult:
    """Create a new branch from the default branch.

    Args:
        repo_path: Path to the repository.
        branch_name: Name for the new branch.
        base_branch: Branch to create from (defaults to default branch).
        checkout: Whether to checkout the new branch.

    Returns:
        GitResult with operation status.
    """
    if base_branch is None:
        base_branch = await get_default_branch(repo_path)

    # Fetch latest from remote first
    await _run_git(["fetch", "origin", base_branch], cwd=repo_path)

    # Create branch
    if checkout:
        result = await _run_git(
            ["checkout", "-b", branch_name, f"origin/{base_branch}"],
            cwd=repo_path,
        )
    else:
        result = await _run_git(
            ["branch", branch_name, f"origin/{base_branch}"],
            cwd=repo_path,
        )

    return result


async def setup_worktree(
    repo_path: str | Path,
    branch_name: str,
    base_branch: str | None = None,
    worktree_dir: str = DEFAULT_WORKTREE_DIR,
    create_branch_if_missing: bool = True,
) -> Path:
    """Create an isolated git worktree for a branch.

    Args:
        repo_path: Path to the main repository.
        branch_name: Branch to checkout in the worktree.
        base_branch: Base branch for new branches.
        worktree_dir: Parent directory for worktrees.
        create_branch_if_missing: Create branch if it doesn't exist.

    Returns:
        Path to the created worktree.

    Raises:
        RuntimeError: If worktree creation fails.
    """
    repo_path = Path(repo_path).resolve()
    worktree_path = get_worktree_path(repo_path, branch_name, worktree_dir)

    # Check if worktree already exists
    if worktree_path.exists():
        # Verify it's a valid worktree
        result = await _run_git(["worktree", "list"], cwd=repo_path)
        if str(worktree_path) in result.stdout:
            return worktree_path
        # Directory exists but isn't a worktree - clean it up
        shutil.rmtree(worktree_path)

    # Ensure worktree parent directory exists
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if branch exists
    branch_exists = await _run_git(
        ["rev-parse", "--verify", f"refs/heads/{branch_name}"],
        cwd=repo_path,
    )

    if not branch_exists.success:
        # Check remote
        remote_exists = await _run_git(
            ["rev-parse", "--verify", f"refs/remotes/origin/{branch_name}"],
            cwd=repo_path,
        )

        if remote_exists.success:
            # Create tracking branch
            await _run_git(
                ["branch", branch_name, f"origin/{branch_name}"],
                cwd=repo_path,
            )
        elif create_branch_if_missing:
            # Create new branch
            result = await create_branch(repo_path, branch_name, base_branch)
            if not result.success:
                raise RuntimeError(f"Failed to create branch: {result.error_message}")
        else:
            raise RuntimeError(f"Branch {branch_name} does not exist")

    # Create worktree
    result = await _run_git(
        ["worktree", "add", str(worktree_path), branch_name],
        cwd=repo_path,
    )

    if not result.success:
        raise RuntimeError(f"Failed to create worktree: {result.error_message}")

    return worktree_path


async def cleanup_worktree(
    repo_path: str | Path,
    branch_name: str | None = None,
    worktree_path: str | Path | None = None,
    delete_branch: bool = False,
    worktree_dir: str = DEFAULT_WORKTREE_DIR,
) -> GitResult:
    """Remove a worktree after completion.

    Idempotent - safe to call multiple times.

    Args:
        repo_path: Path to the main repository.
        branch_name: Branch name (to derive worktree path).
        worktree_path: Explicit worktree path (overrides branch_name).
        delete_branch: Also delete the branch after removing worktree.
        worktree_dir: Parent directory for worktrees.

    Returns:
        GitResult with operation status.
    """
    repo_path = Path(repo_path).resolve()

    if worktree_path is None:
        if branch_name is None:
            return GitResult(
                success=False,
                stdout="",
                stderr="Either branch_name or worktree_path must be provided",
                returncode=1,
            )
        worktree_path = get_worktree_path(repo_path, branch_name, worktree_dir)
    else:
        worktree_path = Path(worktree_path).resolve()

    # Remove worktree
    result = await _run_git(
        ["worktree", "remove", str(worktree_path), "--force"],
        cwd=repo_path,
    )

    # If worktree doesn't exist, that's fine (idempotent)
    if not result.success and "is not a working tree" not in result.stderr:
        # Try manual cleanup if git command fails
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    # Prune worktree references
    await _run_git(["worktree", "prune"], cwd=repo_path)

    # Optionally delete the branch
    if delete_branch and branch_name:
        await _run_git(["branch", "-D", branch_name], cwd=repo_path)

    return GitResult(
        success=True,
        stdout="Worktree cleaned up",
        stderr="",
        returncode=0,
    )


async def get_changed_files(
    worktree_path: str | Path,
    include_staged: bool = True,
    include_unstaged: bool = True,
    include_untracked: bool = True,
) -> list[str]:
    """List files changed in a worktree.

    Args:
        worktree_path: Path to the worktree.
        include_staged: Include staged changes.
        include_unstaged: Include unstaged changes.
        include_untracked: Include untracked files.

    Returns:
        List of changed file paths (relative to worktree).
    """
    files: set[str] = set()

    if include_staged:
        result = await _run_git(
            ["diff", "--cached", "--name-only"],
            cwd=worktree_path,
        )
        if result.success and result.stdout:
            files.update(result.stdout.split("\n"))

    if include_unstaged:
        result = await _run_git(
            ["diff", "--name-only"],
            cwd=worktree_path,
        )
        if result.success and result.stdout:
            files.update(result.stdout.split("\n"))

    if include_untracked:
        result = await _run_git(
            ["ls-files", "--others", "--exclude-standard"],
            cwd=worktree_path,
        )
        if result.success and result.stdout:
            files.update(result.stdout.split("\n"))

    return sorted(f for f in files if f)


async def commit_changes(
    worktree_path: str | Path,
    message: str,
    files: list[str] | None = None,
    all_changes: bool = False,
    author: str | None = None,
) -> GitResult:
    """Stage and commit changes.

    Args:
        worktree_path: Path to the worktree.
        message: Commit message.
        files: Specific files to stage (None = stage nothing new).
        all_changes: Stage all changes (-a flag).
        author: Author string (format: "Name <email>").

    Returns:
        GitResult with operation status.
    """
    # Stage files if specified
    if files:
        for file in files:
            result = await _run_git(["add", file], cwd=worktree_path)
            if not result.success:
                return result

    # Build commit command
    cmd = ["commit"]

    if all_changes:
        cmd.append("-a")

    cmd.extend(["-m", message])

    if author:
        cmd.extend(["--author", author])

    return await _run_git(cmd, cwd=worktree_path)


async def push_branch(
    worktree_path: str | Path,
    branch_name: str,
    remote: str = "origin",
    force: bool = False,
    set_upstream: bool = True,
) -> GitResult:
    """Push branch to remote.

    Args:
        worktree_path: Path to the worktree.
        branch_name: Branch to push.
        remote: Remote name.
        force: Force push (use with caution).
        set_upstream: Set upstream tracking.

    Returns:
        GitResult with operation status.
    """
    cmd = ["push"]

    if set_upstream:
        cmd.extend(["-u", remote, branch_name])
    else:
        cmd.extend([remote, branch_name])

    if force:
        cmd.insert(1, "--force")

    return await _run_git(cmd, cwd=worktree_path, timeout=120)


async def get_current_branch(path: str | Path) -> str | None:
    """Get the current branch name.

    Args:
        path: Path to repository or worktree.

    Returns:
        Branch name, or None if detached HEAD or error.
    """
    result = await _run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"],
        cwd=path,
    )

    if result.success and result.stdout != "HEAD":
        return result.stdout
    return None


async def get_commit_hash(
    path: str | Path,
    ref: str = "HEAD",
    short: bool = True,
) -> str | None:
    """Get commit hash for a reference.

    Args:
        path: Path to repository or worktree.
        ref: Git reference (branch, tag, HEAD, etc.).
        short: Return short hash.

    Returns:
        Commit hash, or None on error.
    """
    cmd = ["rev-parse"]
    if short:
        cmd.append("--short")
    cmd.append(ref)

    result = await _run_git(cmd, cwd=path)
    return result.stdout if result.success else None


async def list_worktrees(repo_path: str | Path) -> list[dict[str, str]]:
    """List all worktrees for a repository.

    Args:
        repo_path: Path to the main repository.

    Returns:
        List of dicts with 'path', 'head', and 'branch' keys.
    """
    result = await _run_git(
        ["worktree", "list", "--porcelain"],
        cwd=repo_path,
    )

    if not result.success:
        return []

    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in result.stdout.split("\n"):
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[9:]
        elif line.startswith("HEAD "):
            current["head"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "detached":
            current["branch"] = "(detached)"

    if current:
        worktrees.append(current)

    return worktrees


async def has_uncommitted_changes(path: str | Path) -> bool:
    """Check if there are uncommitted changes.

    Args:
        path: Path to repository or worktree.

    Returns:
        True if there are uncommitted changes.
    """
    result = await _run_git(
        ["status", "--porcelain"],
        cwd=path,
    )
    return bool(result.stdout)
