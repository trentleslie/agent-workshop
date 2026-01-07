"""GitHub client wrapper with Greptile MCP primary and gh CLI fallback.

Provides a unified interface for GitHub operations, using Greptile MCP
when available for enhanced features (like unaddressed comment filtering).

Usage:
    from agent_workshop.agents.software_dev.utils.github_client import GitHubClient

    client = GitHubClient(repo="owner/repo")

    # Create issue
    issue = await client.create_issue(
        title="Fix bug",
        body="Description here",
        labels=["bug"],
    )

    # Create PR
    pr = await client.create_draft_pr(
        title="feat: add feature",
        body="Description",
        branch="feature-branch",
    )
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GitHubClientConfig(BaseModel):
    """Configuration for GitHub client."""

    # Repository
    repo: str = Field(description="Repository in owner/repo format")
    default_branch: str = Field(default="main", description="Default branch name")

    # Greptile settings
    greptile_enabled: bool = Field(
        default=True,
        description="Whether to try Greptile MCP first",
    )
    greptile_timeout: int = Field(
        default=30,
        description="Timeout for Greptile MCP calls in seconds",
    )

    # gh CLI settings
    gh_timeout: int = Field(
        default=60,
        description="Timeout for gh CLI calls in seconds",
    )


@dataclass
class Issue:
    """GitHub issue data."""

    number: int
    title: str
    body: str
    state: str  # "open" or "closed"
    labels: list[str] = field(default_factory=list)
    url: str = ""
    created_at: datetime | None = None
    author: str = ""


@dataclass
class PullRequest:
    """GitHub pull request data."""

    number: int
    title: str
    body: str
    state: str  # "open", "closed", "merged", "draft"
    branch: str
    base_branch: str = "main"
    url: str = ""
    labels: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    author: str = ""
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


@dataclass
class Comment:
    """GitHub comment data."""

    id: str
    body: str
    author: str
    file_path: str | None = None
    line_number: int | None = None
    created_at: datetime | None = None
    is_resolved: bool = False
    addressed: bool = False  # Greptile's addressed status
    source_type: str = "unknown"  # "greptile", "human", "bot"


@dataclass
class Reaction:
    """GitHub reaction data."""

    content: str  # "+1", "-1", "rocket", etc.
    user: str
    created_at: datetime | None = None


@dataclass
class GitHubResult:
    """Result of a GitHub operation."""

    success: bool
    data: Any = None
    error: str | None = None
    source: str = "unknown"  # "greptile" or "gh"


async def _run_gh(
    args: list[str],
    timeout: int = 60,
) -> tuple[int, str, str]:
    """Run gh CLI command asynchronously.

    Uses create_subprocess_exec for safe execution (no shell injection).
    """
    cmd = ["gh"] + args

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"gh command timed out after {timeout} seconds"
    except FileNotFoundError:
        return -1, "", "gh CLI not found - install from https://cli.github.com/"


class GitHubClient:
    """GitHub client with Greptile MCP primary and gh CLI fallback.

    Provides consistent data structures regardless of which backend is used.
    Greptile MCP offers enhanced features like filtering for unaddressed
    comments, but the client works fully with just gh CLI.

    Example:
        client = GitHubClient(repo="owner/repo")

        # Create an issue
        result = await client.create_issue(
            title="Bug: Something is broken",
            body="## Description\nDetails here...",
            labels=["bug", "priority-high"],
        )

        if result.success:
            print(f"Created issue #{result.data.number}")
    """

    def __init__(
        self,
        repo: str,
        config: GitHubClientConfig | None = None,
    ):
        """Initialize GitHub client.

        Args:
            repo: Repository in owner/repo format.
            config: Client configuration (uses defaults if None).
        """
        if config is None:
            config = GitHubClientConfig(repo=repo)
        else:
            config.repo = repo

        self.config = config
        self.repo = repo

        # Track if Greptile is available (set on first call)
        self._greptile_available: bool | None = None

    async def _check_greptile(self) -> bool:
        """Check if Greptile MCP is available.

        Returns:
            True if Greptile MCP is accessible.
        """
        if not self.config.greptile_enabled:
            return False

        if self._greptile_available is not None:
            return self._greptile_available

        # Try a simple Greptile operation
        # In a real implementation, this would call the MCP
        # For now, we assume it's not available and fall back to gh
        self._greptile_available = False
        return False

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> GitHubResult:
        """Create a GitHub issue.

        Args:
            title: Issue title.
            body: Issue body (markdown).
            labels: Labels to apply.
            assignees: Users to assign.

        Returns:
            GitHubResult with Issue data on success.
        """
        args = [
            "issue", "create",
            "--repo", self.repo,
            "--title", title,
            "--body", body,
        ]

        if labels:
            for label in labels:
                args.extend(["--label", label])

        if assignees:
            for assignee in assignees:
                args.extend(["--assignee", assignee])

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        # Parse issue URL to get number
        # stdout is like: https://github.com/owner/repo/issues/123
        try:
            issue_number = int(stdout.split("/")[-1])
            issue = Issue(
                number=issue_number,
                title=title,
                body=body,
                state="open",
                labels=labels or [],
                url=stdout,
            )
            return GitHubResult(success=True, data=issue, source="gh")
        except (ValueError, IndexError):
            return GitHubResult(
                success=False,
                error=f"Failed to parse issue URL: {stdout}",
                source="gh",
            )

    async def get_issue(self, issue_number: int) -> GitHubResult:
        """Fetch issue details.

        Args:
            issue_number: Issue number.

        Returns:
            GitHubResult with Issue data on success.
        """
        args = [
            "issue", "view", str(issue_number),
            "--repo", self.repo,
            "--json", "number,title,body,state,labels,url,createdAt,author",
        ]

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        try:
            data = json.loads(stdout)
            issue = Issue(
                number=data["number"],
                title=data["title"],
                body=data.get("body", ""),
                state=data["state"],
                labels=[label["name"] for label in data.get("labels", [])],
                url=data.get("url", ""),
                author=data.get("author", {}).get("login", ""),
            )
            return GitHubResult(success=True, data=issue, source="gh")
        except (json.JSONDecodeError, KeyError) as e:
            return GitHubResult(
                success=False,
                error=f"Failed to parse issue: {e}",
                source="gh",
            )

    async def close_issue(
        self,
        issue_number: int,
        comment: str | None = None,
    ) -> GitHubResult:
        """Close an issue with optional comment.

        Args:
            issue_number: Issue number to close.
            comment: Optional closing comment.

        Returns:
            GitHubResult with success status.
        """
        # Add comment first if provided
        if comment:
            comment_args = [
                "issue", "comment", str(issue_number),
                "--repo", self.repo,
                "--body", comment,
            ]
            await _run_gh(comment_args, self.config.gh_timeout)

        # Close the issue
        args = [
            "issue", "close", str(issue_number),
            "--repo", self.repo,
        ]

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        return GitHubResult(
            success=True,
            data={"issue_number": issue_number, "state": "closed"},
            source="gh",
        )

    async def create_draft_pr(
        self,
        title: str,
        body: str,
        branch: str,
        base_branch: str | None = None,
        labels: list[str] | None = None,
    ) -> GitHubResult:
        """Create a draft pull request.

        Args:
            title: PR title.
            body: PR body (markdown).
            branch: Source branch.
            base_branch: Target branch (defaults to config default_branch).
            labels: Labels to apply.

        Returns:
            GitHubResult with PullRequest data on success.
        """
        if base_branch is None:
            base_branch = self.config.default_branch

        args = [
            "pr", "create",
            "--repo", self.repo,
            "--title", title,
            "--body", body,
            "--head", branch,
            "--base", base_branch,
            "--draft",
        ]

        if labels:
            for label in labels:
                args.extend(["--label", label])

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        # Parse PR URL to get number
        try:
            pr_number = int(stdout.split("/")[-1])
            pr = PullRequest(
                number=pr_number,
                title=title,
                body=body,
                state="draft",
                branch=branch,
                base_branch=base_branch,
                url=stdout,
                labels=labels or [],
            )
            return GitHubResult(success=True, data=pr, source="gh")
        except (ValueError, IndexError):
            return GitHubResult(
                success=False,
                error=f"Failed to parse PR URL: {stdout}",
                source="gh",
            )

    async def get_pr(self, pr_number: int) -> GitHubResult:
        """Fetch pull request details.

        Args:
            pr_number: PR number.

        Returns:
            GitHubResult with PullRequest data on success.
        """
        args = [
            "pr", "view", str(pr_number),
            "--repo", self.repo,
            "--json", "number,title,body,state,headRefName,baseRefName,url,labels,additions,deletions,changedFiles,author,createdAt",
        ]

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        try:
            data = json.loads(stdout)
            state = data.get("state", "OPEN").lower()
            if data.get("isDraft"):
                state = "draft"

            pr = PullRequest(
                number=data["number"],
                title=data["title"],
                body=data.get("body", ""),
                state=state,
                branch=data.get("headRefName", ""),
                base_branch=data.get("baseRefName", "main"),
                url=data.get("url", ""),
                labels=[label["name"] for label in data.get("labels", [])],
                additions=data.get("additions", 0),
                deletions=data.get("deletions", 0),
                changed_files=data.get("changedFiles", 0),
                author=data.get("author", {}).get("login", ""),
            )
            return GitHubResult(success=True, data=pr, source="gh")
        except (json.JSONDecodeError, KeyError) as e:
            return GitHubResult(
                success=False,
                error=f"Failed to parse PR: {e}",
                source="gh",
            )

    async def list_pr_comments(
        self,
        pr_number: int,
        unaddressed_only: bool = False,
    ) -> GitHubResult:
        """List comments on a pull request.

        Greptile MCP can filter for unaddressed comments, gh CLI returns all.

        Args:
            pr_number: PR number.
            unaddressed_only: Only return unaddressed comments (Greptile feature).

        Returns:
            GitHubResult with list of Comment objects.
        """
        # Try Greptile first if enabled and filtering is requested
        if unaddressed_only and await self._check_greptile():
            # Greptile would be called here with addressed=False filter
            # For now, fall through to gh
            pass

        # Use gh CLI to get comments
        args = [
            "api",
            f"repos/{self.repo}/pulls/{pr_number}/comments",
            "--paginate",
        ]

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        try:
            data = json.loads(stdout) if stdout else []
            comments = []

            for c in data:
                comment = Comment(
                    id=str(c.get("id", "")),
                    body=c.get("body", ""),
                    author=c.get("user", {}).get("login", ""),
                    file_path=c.get("path"),
                    line_number=c.get("line") or c.get("original_line"),
                    source_type=_detect_comment_source(c.get("user", {}).get("login", "")),
                )
                comments.append(comment)

            # Note: gh CLI doesn't provide addressed status
            # When Greptile is available, it enriches with addressed info

            return GitHubResult(success=True, data=comments, source="gh")
        except json.JSONDecodeError as e:
            return GitHubResult(
                success=False,
                error=f"Failed to parse comments: {e}",
                source="gh",
            )

    async def get_pr_reactions(
        self,
        pr_number: int,
        comment_id: str | None = None,
    ) -> GitHubResult:
        """Fetch reactions on PR or specific comment.

        Args:
            pr_number: PR number.
            comment_id: Specific comment ID (if None, gets PR-level reactions).

        Returns:
            GitHubResult with list of Reaction objects.
        """
        if comment_id:
            endpoint = f"repos/{self.repo}/pulls/comments/{comment_id}/reactions"
        else:
            endpoint = f"repos/{self.repo}/issues/{pr_number}/reactions"

        args = [
            "api", endpoint,
            "-H", "Accept: application/vnd.github+json",
        ]

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        try:
            data = json.loads(stdout) if stdout else []
            reactions = []

            for r in data:
                reaction = Reaction(
                    content=r.get("content", ""),
                    user=r.get("user", {}).get("login", ""),
                )
                reactions.append(reaction)

            return GitHubResult(success=True, data=reactions, source="gh")
        except json.JSONDecodeError as e:
            return GitHubResult(
                success=False,
                error=f"Failed to parse reactions: {e}",
                source="gh",
            )

    async def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "squash",
    ) -> GitHubResult:
        """Merge a pull request.

        Args:
            pr_number: PR number.
            merge_method: Merge method ("merge", "squash", "rebase").

        Returns:
            GitHubResult with success status.
        """
        args = [
            "pr", "merge", str(pr_number),
            "--repo", self.repo,
            f"--{merge_method}",
        ]

        exit_code, stdout, stderr = await _run_gh(args, self.config.gh_timeout)

        if exit_code != 0:
            return GitHubResult(
                success=False,
                error=stderr or stdout,
                source="gh",
            )

        return GitHubResult(
            success=True,
            data={"pr_number": pr_number, "merged": True},
            source="gh",
        )


def _detect_comment_source(username: str) -> str:
    """Detect the source type of a comment based on username.

    Args:
        username: GitHub username.

    Returns:
        "greptile", "bot", or "human".
    """
    username_lower = username.lower()

    if "greptile" in username_lower:
        return "greptile"
    if username_lower.endswith("[bot]") or username_lower.endswith("-bot"):
        return "bot"

    return "human"
