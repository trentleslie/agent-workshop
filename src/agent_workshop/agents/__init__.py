"""
Pre-built agent systems for agent-workshop.

This module provides production-ready agent systems that can be used immediately
or customized for specific use cases.

Available Agents:
    - DeliverableValidator: Validates documents for completeness and quality
    - ValidationPipeline: Multi-step validation workflow with LangGraph
    - CodeReviewer: Code review with customizable criteria
    - PRPipeline: Multi-step PR review workflow
    - ReleasePipeline: Automated release workflow with git/PR operations
    - NotebookValidator: Jupyter notebook quality validation

Example:
    from agent_workshop.agents.validators import DeliverableValidator
    from agent_workshop.agents.software_dev import ReleasePipeline
    from agent_workshop import Config

    validator = DeliverableValidator(Config())
    result = await validator.run(content)
"""

from . import validators
from . import pipelines
from . import software_dev
from . import data_science

__all__ = ["validators", "pipelines", "software_dev", "data_science"]
