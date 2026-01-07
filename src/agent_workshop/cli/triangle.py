"""Triangle workflow commands for CLI.

Commands for controlling human-gated triangle workflows:
- start: Start a new triangle workflow
- approve: Approve a human checkpoint
- status: Show workflow status
- list: List all workflows
- cancel: Cancel a running workflow
"""

from __future__ import annotations

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
    if branch is None:
        branch = f"auto/triangle-v1/issue-{issue}"

    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] - Would start triangle workflow:")
        console.print(f"  Issue: #{issue}")
        console.print(f"  Repo: {repo}")
        console.print(f"  Branch: {branch}")
        console.print(f"  Thread ID: issue-{issue}")
        return

    # TODO: Actually start the workflow when IssueToPR is implemented
    console.print("[bold green]Starting triangle workflow[/bold green]")
    console.print(f"  Issue: #{issue}")
    console.print(f"  Repo: {repo}")
    console.print(f"  Branch: {branch}")
    console.print(f"  Thread ID: issue-{issue}")
    console.print()
    console.print("[yellow]Note:[/yellow] IssueToPR workflow not yet implemented.")
    console.print("Workflow will be available in Phase 2.")


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
        triangle approve issue-42
        triangle approve issue-42 --step pr_review
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
            console.print(f"  ✓ Approved: {p.display_name} at {p.current_step}")
            # TODO: Actually resume workflows when implemented
        console.print()
        console.print("[yellow]Note:[/yellow] Actual workflow resumption not yet implemented.")
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
        console.print(f"[red]Error:[/red] No pending workflow found with ID: {thread_id}")
        return

    if step and step != workflow.current_step:
        console.print(
            f"[red]Error:[/red] Workflow is at step '{workflow.current_step}', "
            f"not '{step}'"
        )
        return

    console.print(f"[bold green]Approved:[/bold green] {workflow.display_name}")
    console.print(f"  Step: {workflow.current_step}")
    console.print()
    console.print("[yellow]Note:[/yellow] Actual workflow resumption not yet implemented.")


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
        triangle status issue-42
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

        if verbose:
            for key, value in state.items():
                console.print(f"  {key}: {value}")
        else:
            console.print(f"  Current step: {state.get('current_step', 'unknown')}")
            console.print(f"  Requires approval: {state.get('requires_human_approval', False)}")
            if state.get('error'):
                console.print(f"  Error: {state.get('error')}")
        return

    # Show all workflows
    pending = persistence.list_pending_approvals()
    threads = persistence.list_threads()

    console.print("[bold]Triangle Workflow Status[/bold]")
    console.print()

    if pending:
        console.print(f"[yellow]Pending Approval ({len(pending)}):[/yellow]")
        table = Table(show_header=True)
        table.add_column("Thread ID", style="cyan")
        table.add_column("Issue/Epic", style="green")
        table.add_column("Current Step", style="yellow")

        for p in pending:
            table.add_row(p.thread_id, p.display_name, p.current_step)

        console.print(table)
        console.print()

    if threads:
        all_threads = set(threads)
        pending_ids = {p.thread_id for p in pending}
        active = all_threads - pending_ids

        if active:
            console.print(f"[green]Active ({len(active)}):[/green]")
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
