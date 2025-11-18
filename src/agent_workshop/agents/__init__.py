"""
Pre-built agent systems for agent-workshop.

This module provides production-ready agent systems that can be used immediately
or customized for specific use cases.

Available Agents:
    - DeliverableValidator: Validates documents for completeness and quality
    - ValidationPipeline: Multi-step validation workflow with LangGraph

Example:
    from agent_workshop.agents.validators import DeliverableValidator
    from agent_workshop import Config

    validator = DeliverableValidator(Config())
    result = await validator.run(content)
"""

from . import validators
from . import pipelines

__all__ = ["validators", "pipelines"]
