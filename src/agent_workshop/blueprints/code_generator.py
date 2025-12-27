"""
Code generation from blueprints using Jinja2 templates.

This module handles rendering agent code from blueprint specifications
using the templates in blueprints/code_templates/.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .schema import AgentBlueprint
from .validators import validate_python_syntax, ValidationResult


# Default template directory (relative to repo root)
DEFAULT_TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "blueprints" / "code_templates"


class CodeGenerator:
    """
    Generates Python code from blueprint specifications.

    Uses Jinja2 templates to render agent implementations
    that follow agent-workshop patterns.

    Example:
        generator = CodeGenerator()
        code = generator.generate(blueprint)

        # Or with custom template directory
        generator = CodeGenerator(template_dir="my_templates/")
        code = generator.generate(blueprint)
    """

    def __init__(self, template_dir: Optional[str | Path] = None):
        """
        Initialize the code generator.

        Args:
            template_dir: Directory containing Jinja2 templates.
                         Defaults to blueprints/code_templates/
        """
        self.template_dir = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR

        # Lazy load Jinja2
        self._env = None

    @property
    def env(self):
        """Lazy-load Jinja2 environment."""
        if self._env is None:
            try:
                from jinja2 import Environment, FileSystemLoader, select_autoescape
            except ImportError:
                raise ImportError(
                    "Jinja2 is required for code generation. "
                    "Install with: pip install jinja2"
                )

            self._env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=select_autoescape(default=False),
                trim_blocks=True,
                lstrip_blocks=True,
            )

            # Add custom filters
            self._env.filters["upper"] = str.upper
            self._env.filters["lower"] = str.lower
            self._env.filters["title"] = str.title

        return self._env

    def generate(self, blueprint: AgentBlueprint) -> str:
        """
        Generate Python code from a blueprint.

        Args:
            blueprint: Validated AgentBlueprint instance

        Returns:
            Generated Python source code

        Raises:
            ValueError: If blueprint type is unsupported
            FileNotFoundError: If template not found
        """
        if blueprint.is_simple:
            return self._generate_simple_agent(blueprint)
        elif blueprint.is_langgraph:
            return self._generate_langgraph_agent(blueprint)
        else:
            raise ValueError(f"Unsupported blueprint type: {blueprint.blueprint.type}")

    def _generate_simple_agent(self, blueprint: AgentBlueprint) -> str:
        """Generate code for a simple agent."""
        template = self.env.get_template("simple_agent.py.jinja2")

        context = {
            "blueprint": blueprint.blueprint,
            "agent": blueprint.agent,
            "tests": blueprint.tests,
            "documentation": blueprint.documentation,
            "timestamp": datetime.now().isoformat(),
        }

        return template.render(**context)

    def _generate_langgraph_agent(self, blueprint: AgentBlueprint) -> str:
        """Generate code for a LangGraph agent."""
        template = self.env.get_template("langgraph_agent.py.jinja2")

        # Generate class name from blueprint name if not specified
        class_name = "".join(
            w.capitalize() for w in blueprint.blueprint.name.split("_")
        )

        context = {
            "blueprint": blueprint.blueprint,
            "workflow": blueprint.workflow,
            "class_name": class_name,
            "tests": blueprint.tests,
            "documentation": blueprint.documentation,
            "timestamp": datetime.now().isoformat(),
        }

        return template.render(**context)

    def generate_to_file(
        self,
        blueprint: AgentBlueprint,
        output_path: str | Path,
        overwrite: bool = False,
    ) -> Path:
        """
        Generate code and write to a file.

        Args:
            blueprint: Blueprint to generate from
            output_path: Path to write generated code
            overwrite: Whether to overwrite existing file

        Returns:
            Path to the generated file

        Raises:
            FileExistsError: If file exists and overwrite=False
        """
        output_path = Path(output_path)

        if output_path.exists() and not overwrite:
            raise FileExistsError(
                f"Output file already exists: {output_path}. "
                "Use overwrite=True to replace."
            )

        # Generate code
        code = self.generate(blueprint)

        # Create parent directories if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        output_path.write_text(code)

        return output_path


class InlineCodeGenerator:
    """
    Generates agent code without external templates.

    Uses string templates embedded in the code for simpler deployment
    when Jinja2 templates aren't available.
    """

    def generate(self, blueprint: AgentBlueprint) -> str:
        """
        Generate Python code from a blueprint using inline templates.

        Args:
            blueprint: Validated AgentBlueprint instance

        Returns:
            Generated Python source code
        """
        if blueprint.is_simple:
            return self._generate_simple_agent(blueprint)
        elif blueprint.is_langgraph:
            return self._generate_langgraph_agent(blueprint)
        else:
            raise ValueError(f"Unsupported blueprint type: {blueprint.blueprint.type}")

    # Mapping from blueprint types to Python types
    TYPE_MAPPING = {
        "string": "str",
        "dict": "Dict[str, Any]",
        "list": "List[Any]",
        "bool": "bool",
        "int": "int",
        "float": "float",
    }

    def _map_type(self, blueprint_type: str) -> str:
        """Map blueprint type to Python type hint."""
        return self.TYPE_MAPPING.get(blueprint_type, blueprint_type)

    def _generate_simple_agent(self, blueprint: AgentBlueprint) -> str:
        """Generate simple agent code inline."""
        agent = blueprint.agent
        bp = blueprint.blueprint

        # Map input type to Python type
        input_type = self._map_type(agent.input.type)

        # Format validation criteria
        criteria_list = ",\n        ".join(
            f'"{c}"' for c in agent.validation_criteria
        )

        # Escape prompts for Python strings
        system_prompt = agent.prompts.system_prompt.replace('"""', '\\"\\"\\"')
        user_prompt = agent.prompts.user_prompt_template.replace('"""', '\\"\\"\\"')

        # Format output schema
        schema_items = "\n".join(
            f"#     {k}: {v}"
            for k, v in (agent.output.output_schema or {}).items()
        )

        code = f'''"""
{bp.description}

Generated from blueprint: {bp.domain}_{bp.name}
Generated at: {datetime.now().isoformat()}
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_workshop import Agent, Config


class {agent.class_name}(Agent):
    """
    {bp.description}

    Output schema:
{schema_items}
    """

    DEFAULT_SYSTEM_PROMPT = """{system_prompt}"""

    DEFAULT_CRITERIA = [
        {criteria_list}
    ]

    DEFAULT_USER_PROMPT_TEMPLATE = """{user_prompt}"""

    def __init__(
        self,
        config: Config = None,
        system_prompt: Optional[str] = None,
        validation_criteria: Optional[List[str]] = None,
        user_prompt_template: Optional[str] = None,
    ):
        super().__init__(config)

        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.validation_criteria = validation_criteria or self.DEFAULT_CRITERIA
        self.user_prompt_template = user_prompt_template or self.DEFAULT_USER_PROMPT_TEMPLATE

    async def run(self, content: {input_type}) -> Dict[str, Any]:
        """
        {agent.input.description}

        Args:
            content: {agent.input.description}

        Returns:
            dict with analysis results
        """
        if not content:
            return {{"error": "Empty input", "timestamp": datetime.now().isoformat()}}

        criteria_text = "\\n".join(
            [f"{{i+1}}. {{c}}" for i, c in enumerate(self.validation_criteria)]
        )

        user_prompt = self.user_prompt_template.format(
            criteria=criteria_text,
            content=content,
        )

        messages = [
            {{"role": "system", "content": self.system_prompt}},
            {{"role": "user", "content": user_prompt}},
        ]

        result = await self.complete(messages, temperature={agent.llm_config.temperature})

        return self._parse_response(result)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        text = response.strip()

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            parsed = json.loads(text)
            parsed["timestamp"] = datetime.now().isoformat()
            return parsed
        except json.JSONDecodeError:
            return {{"error": "Parse failed", "raw": text[:500], "timestamp": datetime.now().isoformat()}}
'''
        return code

    def _generate_langgraph_agent(self, blueprint: AgentBlueprint) -> str:
        """Generate LangGraph agent code inline."""
        workflow = blueprint.workflow
        bp = blueprint.blueprint

        # Check if workflow has action steps
        has_action_steps = any(step.is_action_step for step in workflow.steps)

        # Generate class name
        class_name = "".join(w.capitalize() for w in bp.name.split("_"))

        # Generate state fields
        state_fields = "\n    ".join(
            f"{name}: {type_hint}"
            for name, type_hint in workflow.state.items()
        )

        # Generate step methods
        step_methods = []
        for step in workflow.steps:
            if step.is_prompt_step:
                method = self._generate_prompt_step(step, class_name)
            else:
                method = self._generate_action_step(step, class_name)
            step_methods.append(method)

        # Generate node additions
        node_additions = "\n        ".join(
            f'workflow.add_node("{step.name}", self.{step.name})'
            for step in workflow.steps
        )

        # Generate edge additions
        edge_additions = []
        for edge in workflow.edges:
            if edge.to_step == "END":
                edge_additions.append(f'workflow.add_edge("{edge.from_step}", END)')
            else:
                edge_additions.append(f'workflow.add_edge("{edge.from_step}", "{edge.to_step}")')
        edge_str = "\n        ".join(edge_additions)

        # Generate additional imports for action steps
        action_imports = ""
        action_init = ""
        if has_action_steps:
            action_imports = """
import asyncio
import os
"""
            action_init = """
        self._working_dir = os.getcwd()"""

        code = f'''"""
{bp.description}

Generated from blueprint: {bp.domain}_{bp.name}
Generated at: {datetime.now().isoformat()}
"""

import json
from datetime import datetime
from typing import TypedDict, Dict, Any, List, Optional
{action_imports}
from langgraph.graph import StateGraph, END

from agent_workshop.workflows import LangGraphAgent
from agent_workshop import Config


class {class_name}State(TypedDict):
    """{class_name} pipeline state."""
    {state_fields}


class {class_name}(LangGraphAgent):
    """
    {bp.description}
    """

    def __init__(self, config: Config = None):
        super().__init__(config){action_init}

    def build_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph({class_name}State)

        # Add nodes
        {node_additions}

        # Add edges
        {edge_str}

        # Set entry point
        workflow.set_entry_point("{workflow.entry_point}")

        return workflow.compile()
{"".join(step_methods)}
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        text = response.strip()

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {{"error": "Parse failed", "raw": text[:500]}}

    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the pipeline."""
        result = await super().run(input)
        return result.get("final_result", result)
'''
        # Add action execution helper if needed
        if has_action_steps:
            code += self._generate_shell_executor_method()

        return code

    def _generate_prompt_step(self, step, class_name: str) -> str:
        """Generate code for an LLM prompt step."""
        prompt = step.prompt.replace('"""', '\\"\\"\\"')
        return f'''
    async def {step.name}(self, state: {class_name}State) -> {class_name}State:
        """{step.description or f"Execute {step.name} step"}"""
        prompt = """{prompt}""".format(
            **{{k: (json.dumps(v, indent=2) if isinstance(v, dict) else (v or "N/A"))
               for k, v in state.items() if v is not None}}
        )

        result = await self.provider.complete(
            [{{"role": "user", "content": prompt}}],
            temperature=0.3
        )

        parsed = self._parse_json_response(result)
        return {{**state, "{step.output_to_state}": parsed}}
'''

    def _generate_action_step(self, step, class_name: str) -> str:
        """Generate code for a shell or Python action step."""
        action = step.action

        if action.type == "shell":
            return self._generate_shell_step(step, class_name)
        else:
            # Python actions - generate a placeholder for now
            return self._generate_python_step_placeholder(step, class_name)

    def _generate_shell_step(self, step, class_name: str) -> str:
        """Generate code for a shell command step."""
        shell = step.action.shell
        output = step.action_output

        # Use repr() to safely escape the command string
        command_repr = repr(shell.command)

        # Build output assignments
        output_lines = []
        if output.stdout:
            output_lines.append(f'"{output.stdout}": stdout')
        if output.stderr:
            output_lines.append(f'"{output.stderr}": stderr')
        if output.exit_code:
            output_lines.append(f'"{output.exit_code}": exit_code')
        if output.success:
            output_lines.append(f'"{output.success}": exit_code in {shell.allowed_exit_codes}')

        output_dict = ", ".join(output_lines)

        return f'''
    async def {step.name}(self, state: {class_name}State) -> {class_name}State:
        """{step.description or f"Execute shell command: {step.name}"}"""
        # Format command with state values
        command_template = {command_repr}
        command = command_template.format(
            **{{k: (str(v) if v is not None else "")
               for k, v in state.items()}}
        )

        stdout, stderr, exit_code = await self._run_shell(
            command,
            timeout={shell.timeout_seconds},
            working_dir={repr(shell.working_dir) if shell.working_dir else "None"}
        )

        return {{**state, {output_dict}}}
'''

    def _generate_python_step_placeholder(self, step, class_name: str) -> str:
        """Generate placeholder for Python action step."""
        output = step.action_output
        output_lines = []
        if output.result:
            output_lines.append(f'"{output.result}": {{"status": "python_action_not_implemented"}}')
        if output.success:
            output_lines.append(f'"{output.success}": False')
        output_dict = ", ".join(output_lines) if output_lines else '"_result": {}'

        return f'''
    async def {step.name}(self, state: {class_name}State) -> {class_name}State:
        """{step.description or f"Python action: {step.name}"}"""
        # TODO: Python action execution requires manual implementation
        return {{**state, {output_dict}}}
'''

    def _generate_shell_executor_method(self) -> str:
        """Generate the shell execution helper method."""
        return '''
    async def _run_shell(
        self,
        command: str,
        timeout: int = 300,
        working_dir: Optional[str] = None,
    ) -> tuple:
        """Run a shell command and return (stdout, stderr, exit_code)."""
        cwd = working_dir or self._working_dir

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            return (
                stdout_bytes.decode("utf-8", errors="replace").strip(),
                stderr_bytes.decode("utf-8", errors="replace").strip(),
                proc.returncode,
            )

        except asyncio.TimeoutError:
            return ("", f"Command timed out after {timeout}s", -1)
        except Exception as e:
            return ("", str(e), -1)
'''
