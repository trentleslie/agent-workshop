"""Main CLI entry point for triangle workflow control.

Usage:
    triangle --help
    triangle start --issue 42 --repo owner/repo
    triangle status
    triangle approve issue-42 --step pr_review
"""

import click

from agent_workshop.cli.triangle import approve, cancel, list_workflows, start, status


@click.group()
@click.version_option(package_name="agent-workshop")
def cli() -> None:
    """Triangle workflow control for human-gated automation.

    The triangle workflow automates software development tasks with
    human approval checkpoints at key decision points.

    Commands:
        start    - Start a new triangle workflow for an issue
        status   - Show workflow status (all or specific)
        approve  - Approve a human checkpoint to resume workflow
        list     - List all active/pending workflows
        cancel   - Cancel a running workflow
    """


# Register commands directly (not as subgroup)
cli.add_command(start)
cli.add_command(status)
cli.add_command(approve)
cli.add_command(list_workflows, name="list")
cli.add_command(cancel)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
