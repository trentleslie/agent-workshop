"""
Blueprint validation utilities.

Provides functions for validating blueprints beyond Pydantic schema validation,
including semantic validation and generated code verification.
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

import yaml

from .schema import (
    AgentBlueprint,
    WorkflowStep,
    ShellActionSpec,
    PythonActionSpec,
)


class ValidationError(Exception):
    """Raised when blueprint validation fails."""

    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class ValidationResult:
    """Result of blueprint validation."""

    def __init__(self):
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, error: str):
        """Add an error and mark as invalid."""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str):
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(warning)

    def __bool__(self):
        return self.valid

    def __repr__(self):
        return f"ValidationResult(valid={self.valid}, errors={len(self.errors)}, warnings={len(self.warnings)})"


def load_blueprint(path: str | Path) -> AgentBlueprint:
    """
    Load and validate a blueprint from a YAML file.

    Args:
        path: Path to the blueprint YAML file

    Returns:
        Validated AgentBlueprint instance

    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If blueprint is invalid
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Blueprint file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    try:
        return AgentBlueprint(**data)
    except Exception as e:
        raise ValidationError(f"Invalid blueprint: {e}")


def validate_blueprint(blueprint: AgentBlueprint) -> ValidationResult:
    """
    Perform comprehensive validation on a blueprint.

    Checks:
    - Schema validation (already done by Pydantic)
    - Semantic validation (prompts, criteria, etc.)
    - Naming conventions
    - Workflow structure (for LangGraph)
    - Action step security (for hybrid workflows)

    Args:
        blueprint: Blueprint to validate

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    # Validate naming conventions
    _validate_naming(blueprint, result)

    # Validate prompts
    _validate_prompts(blueprint, result)

    # Validate workflow (if LangGraph)
    if blueprint.is_langgraph and blueprint.workflow:
        _validate_workflow(blueprint, result)
        # Validate action steps for security
        _validate_action_steps(blueprint, result)

    # Validate tests
    _validate_tests(blueprint, result)

    return result


def _validate_naming(blueprint: AgentBlueprint, result: ValidationResult):
    """Validate naming conventions."""
    name = blueprint.blueprint.name

    # Check name format
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        result.add_error(
            f"Blueprint name '{name}' must be lowercase with underscores"
        )

    # Check class name derives from blueprint name (for simple agents)
    if blueprint.is_simple and blueprint.agent:
        expected_class = "".join(w.capitalize() for w in name.split("_"))
        if blueprint.agent.class_name != expected_class:
            result.add_warning(
                f"Class name '{blueprint.agent.class_name}' doesn't match "
                f"expected '{expected_class}' (derived from blueprint name)"
            )


def _validate_prompts(blueprint: AgentBlueprint, result: ValidationResult):
    """Validate prompt quality and structure."""
    if blueprint.is_simple and blueprint.agent:
        prompts = blueprint.agent.prompts

        # Check system prompt length
        if len(prompts.system_prompt) < 50:
            result.add_warning(
                "System prompt is very short (<50 chars). "
                "Consider adding more context."
            )

        # Check user prompt has placeholders
        if "{content}" not in prompts.user_prompt_template:
            result.add_warning(
                "User prompt template missing {content} placeholder"
            )

        # Check for JSON output instruction if output is dict
        if blueprint.agent.output.type == "dict":
            prompt_lower = prompts.user_prompt_template.lower()
            if "json" not in prompt_lower:
                result.add_warning(
                    "Output type is 'dict' but prompt doesn't mention JSON. "
                    "Consider adding JSON output instructions."
                )

    elif blueprint.is_langgraph and blueprint.workflow:
        for step in blueprint.workflow.steps:
            # Only validate prompt steps (action steps don't have prompts)
            if step.is_prompt_step and step.prompt and len(step.prompt) < 20:
                result.add_warning(
                    f"Step '{step.name}' has very short prompt (<20 chars)"
                )


def _validate_workflow(blueprint: AgentBlueprint, result: ValidationResult):
    """Validate LangGraph workflow structure."""
    workflow = blueprint.workflow

    step_names = {s.name for s in workflow.steps}

    # Check entry point
    if workflow.entry_point not in step_names:
        result.add_error(
            f"Entry point '{workflow.entry_point}' not in steps"
        )

    # Check all steps are reachable
    reachable = {workflow.entry_point}
    edge_sources = {e.from_step for e in workflow.edges}
    edge_targets = {e.to_step for e in workflow.edges if e.to_step != "END"}

    for edge in workflow.edges:
        if edge.from_step in reachable:
            if edge.to_step != "END":
                reachable.add(edge.to_step)

    unreachable = step_names - reachable
    if unreachable:
        result.add_warning(
            f"Steps may be unreachable: {unreachable}"
        )

    # Check for END edge
    has_end = any(e.to_step == "END" for e in workflow.edges)
    if not has_end:
        result.add_error("Workflow has no edge to END")

    # Check state fields match step outputs
    state_fields = set(workflow.state.keys())
    for step in workflow.steps:
        if step.is_prompt_step:
            # Prompt steps output to a single state field
            if step.output_to_state not in state_fields:
                result.add_error(
                    f"Step '{step.name}' outputs to '{step.output_to_state}' "
                    f"which is not in state definition"
                )
        elif step.is_action_step:
            # Action steps can output to multiple state fields via action_output
            _validate_action_output_mapping(step, state_fields, result)


def _validate_tests(blueprint: AgentBlueprint, result: ValidationResult):
    """Validate test specification."""
    tests = blueprint.tests

    if not tests.test_cases:
        result.add_warning("No test cases defined")
        return

    # Check fixtures are used
    fixture_names = {f.name for f in tests.fixtures}
    for test in tests.test_cases:
        # Find fixture references like {{fixture_name}}
        refs = re.findall(r"\{\{(\w+)\}\}", test.input)
        for ref in refs:
            if ref not in fixture_names:
                result.add_error(
                    f"Test '{test.name}' references undefined fixture '{ref}'"
                )


def validate_python_syntax(code: str) -> Tuple[bool, str]:
    """
    Validate Python code syntax.

    Args:
        code: Python source code

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def validate_generated_code(code: str, blueprint: AgentBlueprint) -> ValidationResult:
    """
    Validate generated Python code.

    Checks:
    - Syntax validity
    - Required imports present
    - Class name matches blueprint
    - Required methods present

    Args:
        code: Generated Python code
        blueprint: Source blueprint

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    # Check syntax
    is_valid, error = validate_python_syntax(code)
    if not is_valid:
        result.add_error(f"Generated code has syntax error: {error}")
        return result  # Can't check further if syntax is invalid

    # Parse AST
    tree = ast.parse(code)

    # Find class definition
    class_name = blueprint.class_name
    class_def = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_def = node
            break

    if not class_def:
        result.add_error(f"Generated code missing class '{class_name}'")
        return result

    # Check base class
    expected_base = "Agent" if blueprint.is_simple else "LangGraphAgent"
    bases = [b.id for b in class_def.bases if isinstance(b, ast.Name)]
    if expected_base not in bases:
        result.add_warning(
            f"Class doesn't explicitly inherit from {expected_base}"
        )

    # Check required methods
    methods = {
        node.name for node in class_def.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    if blueprint.is_simple:
        if "run" not in methods:
            result.add_error("Simple agent missing 'run' method")
    else:
        if "build_graph" not in methods:
            result.add_error("LangGraph agent missing 'build_graph' method")

        # Check workflow step methods
        if blueprint.workflow:
            for step in blueprint.workflow.steps:
                if step.name not in methods:
                    result.add_error(
                        f"LangGraph agent missing step method '{step.name}'"
                    )

    return result


# =============================================================================
# Action Step Validation
# =============================================================================


def _validate_action_output_mapping(
    step: WorkflowStep,
    state_fields: set,
    result: ValidationResult,
):
    """Validate action output fields exist in state definition."""
    if not step.action_output:
        return

    output = step.action_output
    mapped_fields = [
        output.stdout,
        output.stderr,
        output.exit_code,
        output.result,
        output.success,
    ]

    for field in mapped_fields:
        if field and field not in state_fields:
            result.add_error(
                f"Step '{step.name}' maps output to '{field}' "
                f"which is not in state definition"
            )


def _validate_action_steps(blueprint: AgentBlueprint, result: ValidationResult):
    """Validate action step security and correctness."""
    if not blueprint.is_langgraph or not blueprint.workflow:
        return

    for step in blueprint.workflow.steps:
        if not step.is_action_step:
            continue

        action = step.action

        if action.type == "shell":
            _validate_shell_action(step, action.shell, result)
        elif action.type == "python":
            _validate_python_action(step, action.python, result)


def _validate_shell_action(
    step: WorkflowStep,
    shell: ShellActionSpec,
    result: ValidationResult,
):
    """Validate shell command safety."""
    command = shell.command.lower()

    # Check for destructive filesystem commands
    if "rm -rf /" in command or "rm -rf /*" in command:
        result.add_error(
            f"Step '{step.name}' contains dangerous recursive delete command"
        )

    # Warn about sudo/root commands
    if "sudo" in command:
        result.add_warning(
            f"Step '{step.name}' uses sudo. Ensure this is intentional."
        )

    # Warn about unescaped variable interpolation in shell
    if "${" in shell.command or "$(" in shell.command:
        result.add_warning(
            f"Step '{step.name}' uses shell variable expansion. "
            "Use {{state_field}} interpolation instead for safety."
        )


def _validate_python_action(
    step: WorkflowStep,
    python: PythonActionSpec,
    result: ValidationResult,
):
    """Validate Python code safety and syntax."""
    code = python.code

    # Check syntax
    try:
        tree = ast.parse(code)

        # Check that the required function exists
        function_names = [
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        if python.function_name not in function_names:
            result.add_error(
                f"Step '{step.name}' Python code must define function '{python.function_name}'"
            )

    except SyntaxError as e:
        result.add_error(
            f"Step '{step.name}' Python code has syntax error: {e.msg} (line {e.lineno})"
        )
