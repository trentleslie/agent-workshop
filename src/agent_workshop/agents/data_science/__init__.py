"""
Data Science agents for agent-workshop.

This module provides agents specialized for data science workflows:
- NotebookValidator: Validates Jupyter notebooks for reproducibility and quality

Usage:
    from agent_workshop import Config
    from agent_workshop.agents.data_science import NotebookValidator

    validator = NotebookValidator(Config())
    result = await validator.run(notebook_json)
"""

from .notebook_validator_generated import NotebookValidator

__all__ = [
    "NotebookValidator",
]
