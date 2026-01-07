"""CLI module for triangle workflow control.

Provides command-line interface for:
- Starting triangle workflows
- Approving human checkpoints
- Checking workflow status
- Listing pending approvals
"""

from agent_workshop.cli.main import cli

__all__ = ["cli"]
