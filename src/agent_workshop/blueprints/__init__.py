"""
Blueprint system for agent-workshop.

This module provides tools for defining, validating, and generating agents
from structured YAML specifications (blueprints).

Usage:
    # Load and validate blueprints
    from agent_workshop.blueprints import AgentBlueprint, load_blueprint

    blueprint = load_blueprint("blueprints/specs/my_agent.yaml")

    # Generate agent code from blueprints
    from agent_workshop.blueprints import AgentBuilder, generate_agent_from_blueprint
    from agent_workshop import Config

    # Using AgentBuilder class
    builder = AgentBuilder(Config())
    result = await builder.run({"blueprint_path": "path/to/spec.yaml"})

    # Using convenience function
    result = await generate_agent_from_blueprint(
        "blueprints/specs/my_agent.yaml",
        output_path="src/agents/my_agent.py",
    )
"""

# Schema models
from .schema import (
    AgentBlueprint,
    BlueprintMetadata,
    InputSpec,
    OutputSpec,
    PromptSpec,
    SimpleAgentSpec,
    LLMConfig,
    # Action step models (for hybrid workflows)
    ShellActionSpec,
    PythonActionSpec,
    ActionSpec,
    ActionOutputMapping,
    # Workflow models
    WorkflowStep,
    WorkflowEdge,
    LangGraphWorkflowSpec,
    TestFixture,
    TestCase,
    TestSpec,
)

# Validators
from .validators import (
    ValidationError,
    ValidationResult,
    load_blueprint,
    validate_blueprint,
    validate_generated_code,
    validate_python_syntax,
)

# Code generators
from .code_generator import (
    CodeGenerator,
    InlineCodeGenerator,
)

# Meta-agent
from .agent_builder import (
    AgentBuilder,
    AgentBuilderState,
    generate_agent_from_blueprint,
)

__all__ = [
    # Schema models
    "AgentBlueprint",
    "BlueprintMetadata",
    "InputSpec",
    "OutputSpec",
    "PromptSpec",
    "SimpleAgentSpec",
    "LLMConfig",
    # Action step models
    "ShellActionSpec",
    "PythonActionSpec",
    "ActionSpec",
    "ActionOutputMapping",
    # Workflow models
    "WorkflowStep",
    "WorkflowEdge",
    "LangGraphWorkflowSpec",
    "TestFixture",
    "TestCase",
    "TestSpec",
    # Validators
    "ValidationError",
    "ValidationResult",
    "load_blueprint",
    "validate_blueprint",
    "validate_generated_code",
    "validate_python_syntax",
    # Code generators
    "CodeGenerator",
    "InlineCodeGenerator",
    # Meta-agent
    "AgentBuilder",
    "AgentBuilderState",
    "generate_agent_from_blueprint",
]
