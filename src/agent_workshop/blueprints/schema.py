"""
Pydantic models for blueprint validation.

These models define the schema for agent blueprints, ensuring
structured specifications are valid before code generation or
manual implementation.

See blueprints/schema/blueprint_schema.yaml for documentation.
"""

from typing import Literal, Any
from pydantic import BaseModel, Field, model_validator


class BlueprintMetadata(BaseModel):
    """Metadata section of a blueprint."""

    version: str = Field(
        default="1.0",
        description="Blueprint schema version",
    )
    name: str = Field(
        ...,
        description="Agent identifier (lowercase, underscores)",
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    domain: str = Field(
        ...,
        description="Domain grouping (e.g., software_dev, data_science)",
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    description: str = Field(
        ...,
        description="What this agent does",
        min_length=10,
    )
    type: Literal["simple", "langgraph"] = Field(
        ...,
        description="Agent type: simple or langgraph",
    )


class InputSpec(BaseModel):
    """Input specification for an agent."""

    type: Literal["string", "dict", "list"] = Field(
        ...,
        description="Input data type",
    )
    description: str = Field(
        ...,
        description="What the agent receives",
    )
    validation: list[str] = Field(
        default_factory=list,
        description="Input validation rules",
    )


class OutputSpec(BaseModel):
    """Output specification for an agent."""

    type: Literal["string", "dict", "list"] = Field(
        ...,
        description="Output data type",
    )
    description: str | None = Field(
        default=None,
        description="Output description",
    )
    output_schema: dict[str, str] | None = Field(
        default=None,
        alias="schema",
        description="Output structure (field_name: type_hint)",
    )

    class Config:
        populate_by_name = True


class PromptSpec(BaseModel):
    """Prompt configuration for an agent."""

    system_prompt: str = Field(
        ...,
        description="System prompt for the LLM",
        min_length=20,
    )
    user_prompt_template: str = Field(
        ...,
        description="User prompt template with {placeholders}",
        min_length=10,
    )


class LLMConfig(BaseModel):
    """LLM configuration parameters."""

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=100000,
        description="Maximum tokens in response",
    )
    model_preference: Literal["opus", "sonnet", "haiku"] = Field(
        default="sonnet",
        description="Preferred model tier",
    )


# =============================================================================
# Action Step Models (for hybrid LLM + shell/python workflows)
# =============================================================================


class ShellActionSpec(BaseModel):
    """Specification for a shell command action."""

    command: str = Field(
        ...,
        description="Shell command to execute (supports {state_field} interpolation)",
        min_length=1,
    )
    working_dir: str | None = Field(
        default=None,
        description="Working directory (relative to workflow cwd or absolute)",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Command timeout in seconds",
    )
    allowed_exit_codes: list[int] = Field(
        default_factory=lambda: [0],
        description="Exit codes considered successful",
    )
    capture_stderr: bool = Field(
        default=True,
        description="Whether to capture stderr in output",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables",
    )


class PythonActionSpec(BaseModel):
    """Specification for inline Python code execution."""

    code: str = Field(
        ...,
        description="Python code to execute (must define the specified function)",
        min_length=1,
    )
    function_name: str = Field(
        default="execute",
        description="Function name to call (receives state dict, returns result dict)",
        pattern=r"^[a-z_][a-z0-9_]*$",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Execution timeout in seconds",
    )


class ActionSpec(BaseModel):
    """
    Unified action specification for non-LLM workflow steps.

    Exactly one of shell or python must be specified.
    """

    type: Literal["shell", "python"] = Field(
        ...,
        description="Action type",
    )
    shell: ShellActionSpec | None = Field(
        default=None,
        description="Shell command specification",
    )
    python: PythonActionSpec | None = Field(
        default=None,
        description="Python code specification",
    )

    @model_validator(mode="after")
    def validate_action_type_matches(self):
        """Ensure action type matches provided specification."""
        if self.type == "shell":
            if self.shell is None:
                raise ValueError(
                    "Action type is 'shell' but no 'shell' specification provided"
                )
            if self.python is not None:
                raise ValueError(
                    "Action type is 'shell' but 'python' specification also provided"
                )
        elif self.type == "python":
            if self.python is None:
                raise ValueError(
                    "Action type is 'python' but no 'python' specification provided"
                )
            if self.shell is not None:
                raise ValueError(
                    "Action type is 'python' but 'shell' specification also provided"
                )
        return self


class ActionOutputMapping(BaseModel):
    """Mapping of action output to state fields."""

    stdout: str | None = Field(
        default=None,
        description="State field to write stdout to",
    )
    stderr: str | None = Field(
        default=None,
        description="State field to write stderr to",
    )
    exit_code: str | None = Field(
        default=None,
        description="State field to write exit code to",
    )
    result: str | None = Field(
        default=None,
        description="State field to write parsed result (for Python actions)",
    )
    success: str | None = Field(
        default=None,
        description="State field to write boolean success status",
    )

    @model_validator(mode="after")
    def validate_has_at_least_one_mapping(self):
        """Ensure at least one output is mapped."""
        mappings = [self.stdout, self.stderr, self.exit_code, self.result, self.success]
        if not any(m is not None for m in mappings):
            raise ValueError(
                "ActionOutputMapping must map at least one output field"
            )
        return self


class SimpleAgentSpec(BaseModel):
    """Specification for a simple (single-message) agent."""

    class_name: str = Field(
        ...,
        description="PascalCase class name",
        pattern=r"^[A-Z][a-zA-Z0-9]*$",
    )
    input: InputSpec = Field(
        ...,
        description="Input specification",
    )
    output: OutputSpec = Field(
        ...,
        description="Output specification",
    )
    prompts: PromptSpec = Field(
        ...,
        description="Prompt configuration",
    )
    validation_criteria: list[str] = Field(
        default_factory=list,
        description="Validation criteria",
    )
    llm_config: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM parameters",
    )


class WorkflowStep(BaseModel):
    """
    A step in a LangGraph workflow.

    Each step is either:
    - A prompt step (LLM-based): requires 'prompt' and 'output_to_state'
    - An action step (shell/python): requires 'action' and 'action_output'

    Exactly one of 'prompt' or 'action' must be specified.
    """

    name: str = Field(
        ...,
        description="Step identifier",
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    description: str | None = Field(
        default=None,
        description="Step description",
    )

    # For prompt steps (LLM-based) - existing behavior
    prompt: str | None = Field(
        default=None,
        description="Prompt for LLM step (mutually exclusive with action)",
    )
    output_to_state: str | None = Field(
        default=None,
        description="State field to write LLM result (required for prompt steps)",
    )

    # For action steps (shell/python) - NEW capability
    action: ActionSpec | None = Field(
        default=None,
        description="Action specification (mutually exclusive with prompt)",
    )
    action_output: ActionOutputMapping | None = Field(
        default=None,
        description="Output mapping for action steps",
    )

    @model_validator(mode="after")
    def validate_step_type(self):
        """Ensure step has exactly one type and required fields."""
        has_prompt = self.prompt is not None
        has_action = self.action is not None

        if has_prompt and has_action:
            raise ValueError(
                f"Step '{self.name}' has both 'prompt' and 'action'. "
                "Each step must be either prompt-based OR action-based."
            )

        if not has_prompt and not has_action:
            raise ValueError(
                f"Step '{self.name}' has neither 'prompt' nor 'action'. "
                "Each step must have exactly one."
            )

        # Validate prompt steps have output_to_state
        if has_prompt and self.output_to_state is None:
            raise ValueError(
                f"Prompt step '{self.name}' requires 'output_to_state'"
            )

        # Validate action steps have action_output mapping
        if has_action and self.action_output is None:
            raise ValueError(
                f"Action step '{self.name}' requires 'action_output' mapping"
            )

        return self

    @property
    def is_prompt_step(self) -> bool:
        """Check if this is a prompt (LLM) step."""
        return self.prompt is not None

    @property
    def is_action_step(self) -> bool:
        """Check if this is an action (shell/python) step."""
        return self.action is not None


class WorkflowEdge(BaseModel):
    """An edge in a LangGraph workflow."""

    from_step: str = Field(
        ...,
        alias="from",
        description="Source step name",
    )
    to_step: str = Field(
        ...,
        alias="to",
        description="Target step name (or 'END')",
    )
    condition: str | None = Field(
        default=None,
        description="Condition for routing",
    )

    class Config:
        populate_by_name = True


class LangGraphWorkflowSpec(BaseModel):
    """Specification for a LangGraph workflow agent."""

    state: dict[str, str] = Field(
        ...,
        description="TypedDict state fields",
    )
    steps: list[WorkflowStep] = Field(
        ...,
        description="Workflow steps",
        min_length=1,
    )
    edges: list[WorkflowEdge] = Field(
        ...,
        description="Workflow edges",
        min_length=1,
    )
    entry_point: str = Field(
        ...,
        description="First step name",
    )

    @model_validator(mode="after")
    def validate_workflow_structure(self):
        """Validate workflow has valid structure."""
        step_names = {step.name for step in self.steps}

        # Validate entry point exists
        if self.entry_point not in step_names:
            raise ValueError(
                f"Entry point '{self.entry_point}' not in steps: {step_names}"
            )

        # Validate edges reference valid steps
        for edge in self.edges:
            if edge.from_step not in step_names:
                raise ValueError(
                    f"Edge 'from' step '{edge.from_step}' not in steps: {step_names}"
                )
            if edge.to_step != "END" and edge.to_step not in step_names:
                raise ValueError(
                    f"Edge 'to' step '{edge.to_step}' not in steps or 'END': {step_names}"
                )

        return self


class TestFixture(BaseModel):
    """A test fixture definition."""

    name: str = Field(
        ...,
        description="Fixture identifier",
    )
    value: str = Field(
        ...,
        description="Fixture value",
    )


class TestCase(BaseModel):
    """A test case definition."""

    name: str = Field(
        ...,
        description="Test name (test_* convention)",
        pattern=r"^test_[a-z][a-z0-9_]*$",
    )
    input: str = Field(
        ...,
        description="Input (can use {{fixture_name}})",
    )
    expected_output: dict[str, Any] | None = Field(
        default=None,
        description="Expected result (partial match)",
    )
    should_raise: bool = Field(
        default=False,
        description="Whether test expects exception",
    )


class TestSpec(BaseModel):
    """Test specification for an agent."""

    fixtures: list[TestFixture] = Field(
        default_factory=list,
        description="Test fixtures",
    )
    test_cases: list[TestCase] = Field(
        default_factory=list,
        description="Test cases",
    )


class AgentBlueprint(BaseModel):
    """
    Complete agent blueprint specification.

    This is the top-level model that validates an entire blueprint YAML file.

    Example:
        import yaml
        from agent_workshop.blueprints import AgentBlueprint

        with open("blueprints/specs/my_agent.yaml") as f:
            data = yaml.safe_load(f)
            blueprint = AgentBlueprint(**data)
    """

    blueprint: BlueprintMetadata = Field(
        ...,
        description="Blueprint metadata",
    )
    agent: SimpleAgentSpec | None = Field(
        default=None,
        description="Simple agent specification",
    )
    workflow: LangGraphWorkflowSpec | None = Field(
        default=None,
        description="LangGraph workflow specification",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="pip package dependencies",
    )
    tests: TestSpec = Field(
        default_factory=TestSpec,
        description="Test specification",
    )
    documentation: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional documentation",
    )

    @model_validator(mode="after")
    def validate_type_matches_spec(self):
        """Ensure blueprint type matches provided specification."""
        if self.blueprint.type == "simple":
            if self.agent is None:
                raise ValueError(
                    "Blueprint type is 'simple' but no 'agent' specification provided"
                )
            if self.workflow is not None:
                raise ValueError(
                    "Blueprint type is 'simple' but 'workflow' specification provided"
                )
        elif self.blueprint.type == "langgraph":
            if self.workflow is None:
                raise ValueError(
                    "Blueprint type is 'langgraph' but no 'workflow' specification provided"
                )
        return self

    @property
    def is_simple(self) -> bool:
        """Check if this is a simple agent blueprint."""
        return self.blueprint.type == "simple"

    @property
    def is_langgraph(self) -> bool:
        """Check if this is a LangGraph workflow blueprint."""
        return self.blueprint.type == "langgraph"

    @property
    def class_name(self) -> str:
        """Get the class name for the agent."""
        if self.is_simple and self.agent:
            return self.agent.class_name
        elif self.is_langgraph:
            # Generate class name from blueprint name
            parts = self.blueprint.name.split("_")
            return "".join(p.capitalize() for p in parts)
        return ""
