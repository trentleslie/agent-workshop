"""
Simple Deliverable Validator Agent with Custom Prompt Support

This represents the 80% use case for agent-workshop:
- Single-message automation (input → output)
- No complex workflows
- Perfect for batch processing, scheduled jobs, CI/CD pipelines

Prompt Customization:
- Environment variables (.env file)
- YAML configuration file (prompts.yaml)
- Programmatic (constructor parameters)
- Presets (built-in templates)
"""

from agent_workshop import Agent, Config
from typing import Optional, List, Dict
from datetime import datetime
import os
from pathlib import Path


class DeliverableValidator(Agent):
    """
    Validates deliverable content for completeness and quality.

    This is a simple agent that takes content and provides validation feedback
    with fully customizable prompts and criteria.

    Configuration Priority (highest to lowest):
    1. Constructor parameters
    2. YAML config file
    3. Environment variables
    4. Preset
    5. Defaults

    Example:
        # Using preset
        from agent_workshop.agents.validators import DeliverableValidator
        from agent_workshop.agents.validators.presets import get_preset
        from agent_workshop import Config

        preset = get_preset("financial_report")
        validator = Deliver ableValidator(Config(), **preset)
        result = await validator.run(content)

        # Using YAML config
        validator = DeliverableValidator(Config(), config_file="prompts.yaml")

        # Programmatic
        validator = DeliverableValidator(
            config=Config(),
            system_prompt="Custom system prompt...",
            validation_criteria=["Criterion 1", "Criterion 2"],
            output_format="json"
        )
    """

    DEFAULT_SYSTEM_PROMPT = """You are an expert deliverable validator.
Your role is to assess documents for completeness, clarity, and quality.
Provide constructive, actionable feedback."""

    DEFAULT_CRITERIA = [
        "Clarity and structure",
        "Completeness of information",
        "Grammar and formatting",
    ]

    DEFAULT_USER_PROMPT_TEMPLATE = """Validate this deliverable based on these criteria:
{criteria}

Deliverable Content:
{content}

Provide feedback including:
- Overall assessment (approved/needs_revision)
- Specific strengths
- Improvement recommendations
- Priority actions

Output format: {output_format}"""

    def __init__(
        self,
        config: Config = None,
        system_prompt: Optional[str] = None,
        validation_criteria: Optional[List[str]] = None,
        user_prompt_template: Optional[str] = None,
        output_format: str = "detailed",
        config_file: Optional[str] = None,
        preset: Optional[str] = None
    ):
        """
        Initialize the DeliverableValidator.

        Args:
            config: Agent-workshop Config (reads .env for provider settings)
            system_prompt: Custom system prompt for the validator
            validation_criteria: List of validation criteria
            user_prompt_template: Template for user prompt with {criteria}, {content}, {output_format}
            output_format: Output format (json, detailed, or summary)
            config_file: Path to YAML configuration file
            preset: Name of built-in preset to use
        """
        super().__init__(config)

        # Load configuration from file or preset
        prompt_config = self._load_prompt_config(
            config_file=config_file,
            preset=preset
        )

        # Apply configuration with priority order
        self.system_prompt = (
            system_prompt or
            prompt_config.get("system_prompt") or
            os.getenv("VALIDATOR_SYSTEM_PROMPT") or
            self.DEFAULT_SYSTEM_PROMPT
        )

        self.validation_criteria = (
            validation_criteria or
            prompt_config.get("validation_criteria") or
            self._parse_env_criteria() or
            self.DEFAULT_CRITERIA
        )

        self.user_prompt_template = (
            user_prompt_template or
            prompt_config.get("user_prompt_template") or
            self.DEFAULT_USER_PROMPT_TEMPLATE
        )

        self.output_format = (
            output_format if output_format != "detailed" else
            prompt_config.get("output_format") or
            os.getenv("VALIDATOR_OUTPUT_FORMAT") or
            "detailed"
        )

    def _load_prompt_config(
        self,
        config_file: Optional[str] = None,
        preset: Optional[str] = None
    ) -> Dict:
        """
        Load prompt configuration from file or preset.

        Args:
            config_file: Path to YAML configuration file
            preset: Name of built-in preset

        Returns:
            Dictionary with configuration values
        """
        config = {}

        # Load from preset first
        if preset:
            try:
                from .presets import get_preset
                config = get_preset(preset)
            except ImportError:
                # Presets module not available yet
                pass

        # Load from config file (overrides preset)
        if config_file and Path(config_file).exists():
            try:
                import yaml
                with open(config_file) as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("deliverable_validator", {}))
            except ImportError:
                # PyYAML not installed
                pass

        # Try default config file location
        elif Path("prompts.yaml").exists():
            try:
                import yaml
                with open("prompts.yaml") as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("deliverable_validator", {}))
            except ImportError:
                pass

        return config

    def _parse_env_criteria(self) -> Optional[List[str]]:
        """
        Parse validation criteria from environment variable.

        Expects: VALIDATOR_CRITERIA="Criterion 1,Criterion 2,Criterion 3"

        Returns:
            List of criteria strings or None
        """
        env_criteria = os.getenv("VALIDATOR_CRITERIA")
        if env_criteria:
            return [c.strip() for c in env_criteria.split(",")]
        return None

    async def run(self, content: str) -> dict:
        """
        Validate the provided deliverable content.

        Args:
            content: The deliverable content to validate

        Returns:
            dict with validation results including:
                - validation: The validation feedback
                - timestamp: ISO format timestamp
        """
        # Format criteria as numbered list
        criteria_text = "\n".join([
            f"{i+1}. {c}" for i, c in enumerate(self.validation_criteria)
        ])

        # Build user prompt from template
        user_prompt = self.user_prompt_template.format(
            criteria=criteria_text,
            content=content,
            output_format=self.output_format
        )

        # Build messages with system and user prompts
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Run completion
        result = await self.complete(messages)

        return {
            "validation": result,
            "timestamp": self._get_timestamp()
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp for tracking."""
        return datetime.now().isoformat()


# Example usage:
# config = Config()  # Auto-detects dev/prod environment
# validator = DeliverableValidator(config)
# result = await validator.run(report_content)
