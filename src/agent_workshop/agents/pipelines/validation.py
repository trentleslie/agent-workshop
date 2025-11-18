"""
LangGraph Validation Pipeline Agent with Custom Prompt Support

This represents the 15% use case for agent-workshop:
- Multi-step workflows with state management
- Conditional routing and iterative refinement
- Perfect for complex validation pipelines, multi-agent collaboration

Workflow:
1. Quick Scan: Rapid initial assessment for obvious issues
2. Detailed Verify: In-depth validation of content quality

Prompt Customization:
- Environment variables (.env file)
- YAML configuration file (prompts.yaml)
- Programmatic (constructor parameters)
"""

from agent_workshop.workflows import LangGraphAgent
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict
from pathlib import Path
import os


class ValidationState(TypedDict):
    """State object for the validation pipeline."""
    content: str
    scan_result: str | None
    verify_result: str | None
    final_result: dict | None


class ValidationPipeline(LangGraphAgent):
    """
    Multi-step validation pipeline with quick scan and detailed verification.

    This pipeline performs validation in two stages:
    1. Quick Scan: Fast preliminary check for obvious issues
    2. Detailed Verify: Thorough validation with specific recommendations

    Prompts can be customized for each stage via:
    - Constructor parameters
    - YAML config file
    - Environment variables
    - Defaults

    Example:
        # Using defaults
        from agent_workshop.agents.pipelines import ValidationPipeline
        from agent_workshop import Config

        pipeline = ValidationPipeline(Config())
        result = await pipeline.run({"content": document})

        # Custom prompts
        pipeline = ValidationPipeline(
            config=Config(),
            quick_scan_prompt="Custom scan prompt for {content}",
            detailed_verify_prompt="Custom verify prompt"
        )

        # Using YAML config
        pipeline = ValidationPipeline(Config(), config_file="prompts.yaml")
    """

    DEFAULT_QUICK_SCAN_PROMPT = """Perform a QUICK SCAN of this content.

Look for:
1. Format/structure issues
2. Missing critical sections
3. Obvious errors or red flags

Content:
{content}

Provide a brief assessment (2-3 sentences) and flag any critical issues."""

    DEFAULT_DETAILED_VERIFY_PROMPT = """Based on the quick scan results, perform a DETAILED VERIFICATION.

Quick Scan Results:
{scan_result}

Original Content:
{content}

Provide:
1. Overall assessment (approved/needs_revision)
2. Specific strengths
3. Detailed improvement recommendations
4. Priority actions

Format as JSON with keys: status, strengths, recommendations, priority_actions"""

    def __init__(
        self,
        config=None,
        quick_scan_prompt: Optional[str] = None,
        detailed_verify_prompt: Optional[str] = None,
        config_file: Optional[str] = None
    ):
        """
        Initialize the ValidationPipeline.

        Args:
            config: Agent-workshop Config
            quick_scan_prompt: Custom prompt for quick scan step (supports {content})
            detailed_verify_prompt: Custom prompt for detailed verify step (supports {scan_result}, {content})
            config_file: Path to YAML configuration file
        """
        # Load configuration before calling super().__init__()
        # because super().__init__() calls build_graph() which needs the prompts
        prompt_config = self._load_prompt_config(config_file=config_file)

        # Apply configuration with priority order
        self.quick_scan_prompt = (
            quick_scan_prompt or
            prompt_config.get("quick_scan_prompt") or
            os.getenv("PIPELINE_QUICK_SCAN_PROMPT") or
            self.DEFAULT_QUICK_SCAN_PROMPT
        )

        self.detailed_verify_prompt = (
            detailed_verify_prompt or
            prompt_config.get("detailed_verify_prompt") or
            os.getenv("PIPELINE_DETAILED_VERIFY_PROMPT") or
            self.DEFAULT_DETAILED_VERIFY_PROMPT
        )

        super().__init__(config)

    def _load_prompt_config(self, config_file: Optional[str] = None) -> Dict:
        """
        Load prompt configuration from YAML file.

        Args:
            config_file: Path to YAML configuration file

        Returns:
            Dictionary with configuration values
        """
        config = {}

        # Load from specified config file
        if config_file and Path(config_file).exists():
            try:
                import yaml
                with open(config_file) as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("validation_pipeline", {}))
            except ImportError:
                # PyYAML not installed
                pass

        # Try default config file location
        elif Path("prompts.yaml").exists():
            try:
                import yaml
                with open("prompts.yaml") as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("validation_pipeline", {}))
            except ImportError:
                pass

        return config

    def build_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(ValidationState)

        # Add nodes for each step
        workflow.add_node("quick_scan", self.quick_scan)
        workflow.add_node("detailed_verify", self.detailed_verify)

        # Define edges (flow)
        workflow.add_edge("quick_scan", "detailed_verify")
        workflow.add_edge("detailed_verify", END)

        # Set entry point
        workflow.set_entry_point("quick_scan")

        return workflow.compile()

    async def quick_scan(self, state: ValidationState) -> ValidationState:
        """
        Step 1: Perform a quick scan for obvious issues.

        This is a fast preliminary check for:
        - Format issues
        - Missing critical sections
        - Obvious errors

        Args:
            state: Current pipeline state

        Returns:
            Updated state with scan_result
        """
        # Format prompt with content
        prompt = self.quick_scan_prompt.format(content=state['content'])

        messages = [{
            "role": "user",
            "content": prompt
        }]

        result = await self.provider.complete(messages)

        return {
            **state,
            "scan_result": result
        }

    async def detailed_verify(self, state: ValidationState) -> ValidationState:
        """
        Step 2: Perform detailed verification.

        This is a thorough validation that considers:
        - Content quality and completeness
        - Logical flow and coherence
        - Specific recommendations

        Args:
            state: Current pipeline state

        Returns:
            Updated state with verify_result and final_result
        """
        # Format prompt with scan result and content
        prompt = self.detailed_verify_prompt.format(
            scan_result=state['scan_result'],
            content=state['content']
        )

        messages = [{
            "role": "user",
            "content": prompt
        }]

        result = await self.provider.complete(messages)

        final_result = {
            "quick_scan": state['scan_result'],
            "detailed_verification": result,
            "workflow_complete": True
        }

        return {
            **state,
            "verify_result": result,
            "final_result": final_result
        }


# Example usage:
# config = Config()
# pipeline = ValidationPipeline(config)
# result = await pipeline.run({"content": report_content})
