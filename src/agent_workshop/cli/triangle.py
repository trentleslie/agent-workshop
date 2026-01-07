"""Triangle workflow commands for CLI.

Commands for controlling human-gated triangle workflows:
- start: Start a new triangle workflow
- approve: Approve a human checkpoint
- status: Show workflow status
- list: List all workflows
- cancel: Cancel a running workflow
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

# Lazy import to avoid circular dependencies
# These will be imported when the commands are actually run


console = Console()


def _get_persistence():
    """Lazy import of TrianglePersistence."""
    from agent_workshop.utils.persistence import TrianglePersistence

    return TrianglePersistence()


def _get_async_checkpointer_context():
    """Lazy import of async checkpointer context manager."""
    from agent_workshop.utils.persistence import get_async_checkpointer_context

    return get_async_checkpointer_context()


def _run_async(coro):
    """Run async function in sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
def triangle() -> None:
    """Triangle workflow commands.

    Control human-gated automation workflows.
    """


@triangle.command()
@click.option(
    "--issue", "-i",
    required=True,
    type=int,
    help="GitHub issue number to process",
)
@click.option(
    "--repo", "-r",
    required=True,
    help="Repository in owner/repo format",
)
@click.option(
    "--branch", "-b",
    default=None,
    help="Branch name (auto-generated if not provided)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without executing",
)
def start(
    issue: int,
    repo: str,
    branch: str | None,
    dry_run: bool,
) -> None:
    """Start a new triangle workflow for an issue.

    This creates a new workflow that will:
    1. Parse the issue and generate code (IssueToPR)
    2. Review the PR for security and quality (PRPipeline)
    3. Apply fix suggestions from review (PRCommentProcessor)

    Each stage has a human approval checkpoint.

    Example:
        triangle start --issue 42 --repo owner/repo
    """
    from agent_workshop import Config
    from agent_workshop.agents.software_dev import IssueToPR, make_thread_id

    thread_id = make_thread_id(repo, issue)

    if branch is None:
        branch = f"auto/issue-{issue}"

    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] - Would start triangle workflow:")
        console.print(f"  Issue: #{issue}")
        console.print(f"  Repo: {repo}")
        console.print(f"  Branch: {branch}")
        console.print(f"  Thread ID: {thread_id}")
        return

    # Check if workflow already exists
    persistence = _get_persistence()
    existing = persistence.get_thread_state(thread_id)
    if existing:
        console.print(f"[yellow]Warning:[/yellow] Workflow {thread_id} already exists.")
        console.print(f"  Current step: {existing.get('current_step', 'unknown')}")
        if existing.get("requires_human_approval"):
            console.print("  Status: [yellow]Awaiting approval[/yellow]")
            console.print(f"\n  Use: triangle approve {thread_id}")
        return

    console.print("[bold green]Starting triangle workflow[/bold green]")
    console.print(f"  Issue: #{issue}")
    console.print(f"  Repo: {repo}")
    console.print(f"  Thread ID: {thread_id}")
    console.print()

    # Create and run IssueToPR workflow
    try:
        async def run_workflow():
            async with _get_async_checkpointer_context() as checkpointer:
                workflow = IssueToPR(
                    config=Config(),
                    checkpointer=checkpointer,
                )
                return await workflow.run(
                    {"issue_number": issue, "repo_name": repo},
                    thread_id=thread_id,
                )

        with console.status("[bold blue]Running IssueToPR workflow..."):
            result = _run_async(run_workflow())

        if result.get("error"):
            console.print(f"[red]Error:[/red] {result['error']}")
            return

        if result.get("requires_human_approval"):
            console.print()
            console.print("[yellow]Workflow paused - awaiting human review[/yellow]")
            if result.get("pr_url"):
                console.print(f"  PR: {result['pr_url']}")
            console.print()
            console.print(f"  After reviewing, run: triangle approve {thread_id}")
        else:
            console.print("[green]Workflow completed[/green]")

    except Exception as e:
        console.print(f"[red]Error starting workflow:[/red] {e}")


@triangle.command()
@click.argument("thread_id", required=False)
@click.option(
    "--step", "-s",
    default=None,
    help="Specific step to approve",
)
@click.option(
    "--all", "-a", "approve_all",
    is_flag=True,
    help="Approve all pending checkpoints",
)
def approve(
    thread_id: str | None,
    step: str | None,
    approve_all: bool,
) -> None:
    """Approve a human checkpoint to resume workflow.

    This resumes a paused workflow that is waiting for human approval.
    The workflow will continue from where it was paused.

    Examples:
        triangle approve owner-repo-issue-42
        triangle approve owner-repo-issue-42 --step awaiting_review
        triangle approve --all
    """
    persistence = _get_persistence()
    pending = persistence.list_pending_approvals()

    if not pending:
        console.print("[green]No workflows waiting for approval.[/green]")
        return

    if approve_all:
        console.print(f"[bold]Approving all {len(pending)} pending workflows...[/bold]")
        for p in pending:
            _approve_single_workflow(p.thread_id, persistence)
        return

    if thread_id is None:
        console.print("[red]Error:[/red] Please specify a thread_id or use --all")
        console.print()
        console.print("Pending workflows:")
        for p in pending:
            console.print(f"  • {p.thread_id} - {p.display_name} at {p.current_step}")
        return

    # Find the specific workflow
    workflow = next((p for p in pending if p.thread_id == thread_id), None)
    if workflow is None:
        # Check if it exists but isn't pending
        state = persistence.get_thread_state(thread_id)
        if state:
            if state.get("current_step") == "completed":
                console.print(f"[green]Workflow {thread_id} already completed.[/green]")
            else:
                console.print(
                    f"[yellow]Workflow {thread_id} not waiting for approval.[/yellow]"
                )
                console.print(f"  Current step: {state.get('current_step', 'unknown')}")
        else:
            console.print(f"[red]Error:[/red] No workflow found with ID: {thread_id}")
        return

    if step and step != workflow.current_step:
        console.print(
            f"[red]Error:[/red] Workflow is at step '{workflow.current_step}', "
            f"not '{step}'"
        )
        return

    _approve_single_workflow(thread_id, persistence)


def _approve_single_workflow(thread_id: str, persistence) -> None:
    """Approve and resume a single workflow with idempotency guards."""
    import subprocess

    from agent_workshop import Config
    from agent_workshop.agents.software_dev import TriangleOrchestrator

    state = persistence.get_thread_state(thread_id)

    # Guard: Already completed
    if state.get("current_step") == "completed":
        console.print(f"[green]✓ {thread_id} already completed[/green]")
        return

    # Guard: Not waiting for approval
    if not state.get("requires_human_approval"):
        console.print(f"[yellow]⚠ {thread_id} not waiting for approval[/yellow]")
        return

    # Guard: No PR (can't approve without PR)
    pr_number = state.get("pr_number")
    if not pr_number:
        console.print(f"[red]✗ {thread_id} has no PR to approve[/red]")
        return

    # Guard: Check if PR is already merged (idempotency)
    repo_name = state.get("repo_name", "")
    if repo_name and pr_number:
        try:
            result = subprocess.run(
                ["gh", "pr", "view", str(pr_number), "--repo", repo_name, "--json", "state"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                import json
                pr_state = json.loads(result.stdout).get("state", "")
                if pr_state == "MERGED":
                    console.print(f"[green]✓ {thread_id} already completed (PR #{pr_number} merged)[/green]")
                    return
                elif pr_state == "CLOSED":
                    console.print(f"[yellow]⚠ PR #{pr_number} is closed but not merged[/yellow]")
                    return
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            # If we can't check, proceed with caution
            pass

    # Calculate review duration
    checkpoint_at = state.get("checkpoint_at")
    review_duration = None
    if checkpoint_at:
        try:
            checkpoint_time = datetime.fromisoformat(checkpoint_at.replace("Z", "+00:00"))
            review_duration = (datetime.now(timezone.utc) - checkpoint_time).total_seconds()
        except (ValueError, TypeError):
            pass

    console.print(f"[bold green]Approving:[/bold green] {thread_id}")
    if review_duration:
        hours = int(review_duration // 3600)
        minutes = int((review_duration % 3600) // 60)
        if hours > 0:
            console.print(f"  Review time: {hours}h {minutes}m")
        else:
            console.print(f"  Review time: {minutes}m")

    # Record metrics
    state["metrics"] = state.get("metrics", {})
    state["metrics"]["review_duration_seconds"] = review_duration

    # Resume workflow with TriangleOrchestrator
    async def resume_workflow():
        orchestrator = TriangleOrchestrator(config=Config())
        return await orchestrator.resume_from_checkpoint(state)

    console.print()
    try:
        with console.status("[bold blue]Resuming workflow..."):
            result = _run_async(resume_workflow())

        if result.get("error"):
            console.print(f"[red]Error:[/red] {result['error']}")
            return

        if result.get("current_step") == "completed":
            console.print()
            console.print("[bold green]✅ Workflow completed![/bold green]")
            console.print(f"  PR #{result.get('pr_number')} merged")

            follow_up = result.get("follow_up_issues", [])
            if follow_up:
                console.print(f"  Follow-up issues created: {follow_up}")
        else:
            console.print(f"[yellow]Workflow paused at: {result.get('current_step')}[/yellow]")

    except Exception as e:
        console.print(f"[red]Resume failed:[/red] {e}")
        raise


@triangle.command()
@click.argument("thread_id", required=False)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed information",
)
def status(
    thread_id: str | None,
    verbose: bool,
) -> None:
    """Show workflow status.

    Without arguments, shows all active workflows.
    With a thread_id, shows details for that specific workflow.

    Examples:
        triangle status
        triangle status owner-repo-issue-42
        triangle status --verbose
    """
    persistence = _get_persistence()

    if thread_id:
        # Show specific workflow
        state = persistence.get_thread_state(thread_id)
        if state is None:
            console.print(f"[red]Error:[/red] No workflow found with ID: {thread_id}")
            return

        console.print(f"[bold]Workflow: {thread_id}[/bold]")
        console.print()

        # Status indicator
        if state.get("requires_human_approval"):
            console.print("  Status: [yellow]⏸️  PENDING APPROVAL[/yellow]")
        elif state.get("current_step") == "completed":
            console.print("  Status: [green]✅ COMPLETED[/green]")
        elif state.get("error"):
            console.print("  Status: [red]❌ ERROR[/red]")
        else:
            console.print("  Status: [blue]🔄 IN PROGRESS[/blue]")

        console.print(f"  Step: {state.get('current_step', 'unknown')}")

        if state.get("pr_url"):
            console.print(f"  PR: {state['pr_url']}")

        # Show wait time if checkpointed
        checkpoint_at = state.get("checkpoint_at")
        if checkpoint_at and state.get("requires_human_approval"):
            try:
                checkpoint_time = datetime.fromisoformat(
                    checkpoint_at.replace("Z", "+00:00")
                )
                wait_time = (datetime.now(timezone.utc) - checkpoint_time).total_seconds()
                hours = int(wait_time // 3600)
                minutes = int((wait_time % 3600) // 60)
                if hours > 0:
                    console.print(f"  Waiting: {hours}h {minutes}m")
                else:
                    console.print(f"  Waiting: {minutes}m")
            except (ValueError, TypeError):
                pass

        if state.get("error"):
            console.print(f"  [red]Error:[/red] {state['error']}")

        if verbose:
            console.print()
            console.print("[dim]Full state:[/dim]")
            for key, value in sorted(state.items()):
                if key not in ("current_step", "error", "pr_url", "requires_human_approval"):
                    console.print(f"  {key}: {value}")
        return

    # Show all workflows
    pending = persistence.list_pending_approvals()
    threads = persistence.list_threads()

    console.print("[bold]Triangle Workflow Status[/bold]")
    console.print()

    if pending:
        console.print(f"[yellow]⏸️  Pending Approval ({len(pending)}):[/yellow]")
        table = Table(show_header=True)
        table.add_column("Thread ID", style="cyan")
        table.add_column("Issue/Epic", style="green")
        table.add_column("Step", style="yellow")
        table.add_column("Waiting", style="dim")

        for p in pending:
            # Calculate wait time
            wait_str = ""
            if p.state_values:
                checkpoint_at = p.state_values.get("checkpoint_at")
                if checkpoint_at:
                    try:
                        checkpoint_time = datetime.fromisoformat(
                            checkpoint_at.replace("Z", "+00:00")
                        )
                        wait = (datetime.now(timezone.utc) - checkpoint_time).total_seconds()
                        hours = int(wait // 3600)
                        mins = int((wait % 3600) // 60)
                        wait_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                    except (ValueError, TypeError):
                        pass

            table.add_row(p.thread_id, p.display_name, p.current_step, wait_str)

        console.print(table)
        console.print()

    if threads:
        all_threads = set(threads)
        pending_ids = {p.thread_id for p in pending}
        active = all_threads - pending_ids

        if active:
            console.print(f"[green]🔄 Active ({len(active)}):[/green]")
            for t in sorted(active):
                console.print(f"  • {t}")
            console.print()

    if not pending and not threads:
        console.print("[dim]No workflows found.[/dim]")


@triangle.command("list")
@click.option(
    "--type", "-t", "workflow_type",
    type=click.Choice(["issue", "epic", "all"]),
    default="all",
    help="Filter by workflow type",
)
def list_workflows(workflow_type: str) -> None:
    """List all active and pending workflows.

    Examples:
        triangle list
        triangle list --type issue
        triangle list --type epic
    """
    persistence = _get_persistence()

    filter_type = None if workflow_type == "all" else workflow_type
    threads = persistence.list_threads(thread_type=filter_type)
    pending = persistence.list_pending_approvals()
    pending_ids = {p.thread_id for p in pending}

    if not threads:
        console.print("[dim]No workflows found.[/dim]")
        return

    table = Table(show_header=True, title="Triangle Workflows")
    table.add_column("Thread ID", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Status", style="green")

    for thread_id in sorted(threads):
        from agent_workshop.utils.persistence import parse_thread_id
        parsed = parse_thread_id(thread_id)

        if pending_ids and thread_id in pending_ids:
            status_str = "[yellow]Pending Approval[/yellow]"
        else:
            status_str = "[green]Active[/green]"

        table.add_row(thread_id, parsed["type"], status_str)

    console.print(table)


@triangle.command()
@click.argument("thread_id")
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Force cancel without confirmation",
)
def cancel(
    thread_id: str,
    force: bool,
) -> None:
    """Cancel a running workflow.

    This stops a workflow and cleans up associated resources.
    Use --force to skip confirmation.

    Examples:
        triangle cancel issue-42
        triangle cancel issue-42 --force
    """
    persistence = _get_persistence()

    state = persistence.get_thread_state(thread_id)
    if state is None:
        console.print(f"[red]Error:[/red] No workflow found with ID: {thread_id}")
        return

    if not force:
        confirm = click.confirm(
            f"Cancel workflow {thread_id}? This cannot be undone.",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    # TODO: Actually cancel the workflow when implemented
    console.print(f"[bold red]Cancelled:[/bold red] {thread_id}")
    console.print()
    console.print("[yellow]Note:[/yellow] Workflow cancellation not yet fully implemented.")
    console.print("The workflow state remains in the database for recovery.")
