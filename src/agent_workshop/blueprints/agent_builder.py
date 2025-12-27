"""
AgentBuilder meta-agent for generating agents from blueprints.

This LangGraph workflow orchestrates the full agent generation pipeline:
1. Load blueprint from YAML
2. Validate blueprint structure and semantics
3. Generate Python code from blueprint
4. Validate generated code syntax
5. (Optional) Write to output file

Usage:
    from agent_workshop.blueprints import AgentBuilder
    from agent_workshop import Config

    builder = AgentBuilder(Config())
    result = await builder.run({
        "blueprint_path": "blueprints/specs/my_agent.yaml",
        "output_path": "src/my_agents/my_agent.py",  # optional
        "overwrite": False,  # optional
    })

    # Result includes:
    # - blueprint: Parsed AgentBlueprint object
    # - validation: ValidationResult from blueprint validation
    # - code: Generated Python source code
    # - code_validation: ValidationResult from code validation
    # - output_path: Path where code was written (if requested)
    # - success: Overall success status
"""

from datetime import datetime
from pathlib import Path
from typing import TypedDict, Any

from langgraph.graph import StateGraph, END

from ..workflows import LangGraphAgent
from ..config import Config
from .schema import AgentBlueprint
from .validators import (
    load_blueprint,
    validate_blueprint,
    validate_generated_code,
    validate_python_syntax,
    ValidationResult,
    ValidationError,
)
from .code_generator import CodeGenerator, InlineCodeGenerator


class AgentBuilderState(TypedDict):
    """State object for the AgentBuilder pipeline."""
    # Input fields
    blueprint_path: str | None
    blueprint_dict: dict | None
    output_path: str | None
    overwrite: bool
    use_inline_generator: bool

    # Intermediate results
    blueprint: AgentBlueprint | None
    validation: ValidationResult | None
    code: str | None
    code_validation: ValidationResult | None

    # Output
    written_path: str | None
    success: bool
    error: str | None
    timestamp: str | None


class AgentBuilder(LangGraphAgent):
    """
    Meta-agent that generates agent code from blueprint specifications.

    This is a LangGraph workflow with 4 steps:
    1. load_blueprint - Load and parse YAML blueprint
    2. validate_blueprint - Run semantic validation
    3. generate_code - Generate Python source code
    4. validate_and_write - Validate code and optionally write to file

    The AgentBuilder supports two generation modes:
    - Jinja2 templates (default): Requires templates in blueprints/code_templates/
    - Inline generation: Embedded templates, no external dependencies

    Example:
        ```python
        from agent_workshop.blueprints import AgentBuilder
        from agent_workshop import Config

        # Generate from blueprint file
        builder = AgentBuilder(Config())
        result = await builder.run({
            "blueprint_path": "blueprints/specs/my_agent.yaml",
        })

        if result["success"]:
            print(result["code"])  # Generated Python code

        # Generate and write to file
        result = await builder.run({
            "blueprint_path": "blueprints/specs/my_agent.yaml",
            "output_path": "src/agents/my_agent.py",
            "overwrite": True,
        })

        # Use inline generator (no template dependencies)
        result = await builder.run({
            "blueprint_path": "blueprints/specs/my_agent.yaml",
            "use_inline_generator": True,
        })
        ```
    """

    def __init__(
        self,
        config: Config | None = None,
        template_dir: str | Path | None = None,
    ):
        """
        Initialize the AgentBuilder.

        Args:
            config: Agent-workshop configuration
            template_dir: Custom Jinja2 template directory (optional)
        """
        self.template_dir = template_dir
        self._jinja_generator = None
        self._inline_generator = None
        super().__init__(config)

    @property
    def jinja_generator(self) -> CodeGenerator:
        """Lazy-load Jinja2 code generator."""
        if self._jinja_generator is None:
            self._jinja_generator = CodeGenerator(template_dir=self.template_dir)
        return self._jinja_generator

    @property
    def inline_generator(self) -> InlineCodeGenerator:
        """Lazy-load inline code generator."""
        if self._inline_generator is None:
            self._inline_generator = InlineCodeGenerator()
        return self._inline_generator

    def build_graph(self):
        """Build the AgentBuilder LangGraph workflow."""
        workflow = StateGraph(AgentBuilderState)

        # Add nodes
        workflow.add_node("load_blueprint", self.load_blueprint)
        workflow.add_node("validate_blueprint", self.validate_blueprint_step)
        workflow.add_node("generate_code", self.generate_code)
        workflow.add_node("validate_and_write", self.validate_and_write)

        # Define edges
        workflow.add_edge("load_blueprint", "validate_blueprint")
        workflow.add_edge("validate_blueprint", "generate_code")
        workflow.add_edge("generate_code", "validate_and_write")
        workflow.add_edge("validate_and_write", END)

        # Set entry point
        workflow.set_entry_point("load_blueprint")

        return workflow.compile()

    async def load_blueprint(self, state: AgentBuilderState) -> AgentBuilderState:
        """
        Step 1: Load blueprint from YAML file or dict.

        Supports loading from:
        - blueprint_path: Path to YAML file
        - blueprint_dict: Pre-loaded dictionary

        Args:
            state: Current pipeline state

        Returns:
            Updated state with loaded blueprint or error
        """
        try:
            if state.get("blueprint_path"):
                blueprint = load_blueprint(state["blueprint_path"])
            elif state.get("blueprint_dict"):
                blueprint = AgentBlueprint(**state["blueprint_dict"])
            else:
                return {
                    **state,
                    "success": False,
                    "error": "Must provide either blueprint_path or blueprint_dict",
                    "timestamp": datetime.now().isoformat(),
                }

            return {
                **state,
                "blueprint": blueprint,
            }

        except FileNotFoundError as e:
            return {
                **state,
                "success": False,
                "error": f"Blueprint file not found: {e}",
                "timestamp": datetime.now().isoformat(),
            }
        except ValidationError as e:
            return {
                **state,
                "success": False,
                "error": f"Blueprint validation failed: {e.message}",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                **state,
                "success": False,
                "error": f"Failed to load blueprint: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def validate_blueprint_step(self, state: AgentBuilderState) -> AgentBuilderState:
        """
        Step 2: Validate blueprint semantics.

        Checks beyond schema validation:
        - Naming conventions
        - Prompt quality
        - Workflow structure (for LangGraph)
        - Test coverage

        Args:
            state: Current pipeline state

        Returns:
            Updated state with validation results
        """
        # Skip if already failed
        if state.get("error"):
            return state

        blueprint = state.get("blueprint")
        if not blueprint:
            return {
                **state,
                "success": False,
                "error": "No blueprint loaded",
                "timestamp": datetime.now().isoformat(),
            }

        validation = validate_blueprint(blueprint)

        # Validation errors are blocking
        if not validation.valid:
            return {
                **state,
                "validation": validation,
                "success": False,
                "error": f"Blueprint validation failed: {'; '.join(validation.errors)}",
                "timestamp": datetime.now().isoformat(),
            }

        return {
            **state,
            "validation": validation,
        }

    async def generate_code(self, state: AgentBuilderState) -> AgentBuilderState:
        """
        Step 3: Generate Python code from blueprint.

        Uses either:
        - Jinja2 templates (default): More customizable
        - Inline generator: No external dependencies

        Args:
            state: Current pipeline state

        Returns:
            Updated state with generated code
        """
        # Skip if already failed
        if state.get("error"):
            return state

        blueprint = state.get("blueprint")
        if not blueprint:
            return {
                **state,
                "success": False,
                "error": "No blueprint available for code generation",
                "timestamp": datetime.now().isoformat(),
            }

        try:
            # Choose generator
            if state.get("use_inline_generator", False):
                generator = self.inline_generator
            else:
                generator = self.jinja_generator

            code = generator.generate(blueprint)

            return {
                **state,
                "code": code,
            }

        except FileNotFoundError as e:
            # Template not found - fall back to inline
            try:
                code = self.inline_generator.generate(blueprint)
                return {
                    **state,
                    "code": code,
                }
            except Exception as inner_e:
                return {
                    **state,
                    "success": False,
                    "error": f"Code generation failed: {str(inner_e)}",
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            return {
                **state,
                "success": False,
                "error": f"Code generation failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def validate_and_write(self, state: AgentBuilderState) -> AgentBuilderState:
        """
        Step 4: Validate generated code and optionally write to file.

        Validates:
        - Python syntax
        - Required imports
        - Class structure
        - Method presence

        Args:
            state: Current pipeline state

        Returns:
            Final state with validation results and written path
        """
        # Skip if already failed
        if state.get("error"):
            return state

        code = state.get("code")
        blueprint = state.get("blueprint")

        if not code:
            return {
                **state,
                "success": False,
                "error": "No code generated",
                "timestamp": datetime.now().isoformat(),
            }

        # Validate generated code
        code_validation = validate_generated_code(code, blueprint)

        if not code_validation.valid:
            return {
                **state,
                "code_validation": code_validation,
                "success": False,
                "error": f"Generated code validation failed: {'; '.join(code_validation.errors)}",
                "timestamp": datetime.now().isoformat(),
            }

        # Write to file if output_path provided
        written_path = None
        output_path = state.get("output_path")

        if output_path:
            output_path = Path(output_path)
            overwrite = state.get("overwrite", False)

            if output_path.exists() and not overwrite:
                return {
                    **state,
                    "code_validation": code_validation,
                    "success": False,
                    "error": f"Output file exists: {output_path}. Use overwrite=True to replace.",
                    "timestamp": datetime.now().isoformat(),
                }

            try:
                # Create parent directories
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Write code
                output_path.write_text(code)
                written_path = str(output_path)

            except Exception as e:
                return {
                    **state,
                    "code_validation": code_validation,
                    "success": False,
                    "error": f"Failed to write file: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }

        return {
            **state,
            "code_validation": code_validation,
            "written_path": written_path,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    async def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the AgentBuilder pipeline.

        Args:
            input: Dictionary with:
                - blueprint_path: Path to YAML blueprint file
                - blueprint_dict: Pre-loaded blueprint dictionary (alternative to path)
                - output_path: Optional path to write generated code
                - overwrite: Whether to overwrite existing files (default: False)
                - use_inline_generator: Use inline templates instead of Jinja2 (default: False)

        Returns:
            Dictionary with:
                - blueprint: Parsed AgentBlueprint (or None on error)
                - validation: Blueprint ValidationResult
                - code: Generated Python source code
                - code_validation: Code ValidationResult
                - written_path: Path where code was written (if requested)
                - success: Overall success status
                - error: Error message (if failed)
                - timestamp: Completion timestamp
        """
        # Initialize state with defaults
        state: AgentBuilderState = {
            "blueprint_path": input.get("blueprint_path"),
            "blueprint_dict": input.get("blueprint_dict"),
            "output_path": input.get("output_path"),
            "overwrite": input.get("overwrite", False),
            "use_inline_generator": input.get("use_inline_generator", False),
            "blueprint": None,
            "validation": None,
            "code": None,
            "code_validation": None,
            "written_path": None,
            "success": False,
            "error": None,
            "timestamp": None,
        }

        # Run the workflow
        result = await self.graph.ainvoke(state)

        # Convert non-serializable objects for output
        output = {
            "blueprint": result.get("blueprint"),
            "validation": result.get("validation"),
            "code": result.get("code"),
            "code_validation": result.get("code_validation"),
            "written_path": result.get("written_path"),
            "success": result.get("success", False),
            "error": result.get("error"),
            "timestamp": result.get("timestamp"),
        }

        return output


# Convenience function for simple usage
async def generate_agent_from_blueprint(
    blueprint_path: str | Path,
    output_path: str | Path | None = None,
    overwrite: bool = False,
    config: Config | None = None,
) -> dict[str, Any]:
    """
    Generate agent code from a blueprint file.

    Convenience function that creates an AgentBuilder and runs it.

    Args:
        blueprint_path: Path to YAML blueprint file
        output_path: Optional path to write generated code
        overwrite: Whether to overwrite existing files
        config: Optional configuration

    Returns:
        Dictionary with generation results

    Example:
        ```python
        from agent_workshop.blueprints import generate_agent_from_blueprint

        # Generate code (returns code string)
        result = await generate_agent_from_blueprint(
            "blueprints/specs/my_agent.yaml"
        )
        print(result["code"])

        # Generate and write to file
        result = await generate_agent_from_blueprint(
            "blueprints/specs/my_agent.yaml",
            output_path="src/agents/my_agent.py",
            overwrite=True,
        )
        ```
    """
    builder = AgentBuilder(config)
    return await builder.run({
        "blueprint_path": str(blueprint_path),
        "output_path": str(output_path) if output_path else None,
        "overwrite": overwrite,
    })
