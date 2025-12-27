"""
Code Reviewer Agent for Software Development.

This agent reviews code for quality, security, and best practices,
producing structured JSON reports with issues and suggestions.

Blueprint: blueprints/specs/software_dev_code_reviewer.yaml
Brainstorm: blueprints/brainstorms/software_dev_code_reviewer.md

Usage:
    from agent_workshop import Config
    from agent_workshop.agents.software_dev import CodeReviewer

    reviewer = CodeReviewer(Config())
    result = await reviewer.run(code_content)

    # With preset
    from agent_workshop.agents.software_dev import get_preset
    preset = get_preset("security_focused")
    reviewer = CodeReviewer(Config(), **preset)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_workshop import Agent, Config


class CodeReviewer(Agent):
    """
    Reviews code for quality, security, and best practices.

    This is a simple agent (single-message pattern) that:
    1. Takes code as input
    2. Analyzes for security, quality, style, and performance issues
    3. Returns structured JSON report

    Configuration Priority (highest to lowest):
    1. Constructor parameters
    2. YAML config file (prompts.yaml)
    3. Environment variables
    4. Preset configuration
    5. Built-in defaults

    Example:
        # Default configuration
        reviewer = CodeReviewer(Config())
        result = await reviewer.run(code)

        # Using preset
        from agent_workshop.agents.software_dev import get_preset
        preset = get_preset("security_focused")
        reviewer = CodeReviewer(Config(), **preset)

        # Custom configuration
        reviewer = CodeReviewer(
            config=Config(),
            system_prompt="Custom prompt...",
            validation_criteria=["Custom criterion"],
        )
    """

    DEFAULT_SYSTEM_PROMPT = """You are an expert code reviewer with deep knowledge of software security, clean code principles, and industry best practices.

Your role is to review code and identify:
1. SECURITY issues (credentials, injection vulnerabilities, unsafe operations)
2. QUALITY issues (error handling, edge cases, code clarity)
3. STYLE issues (naming, formatting, consistency)
4. PERFORMANCE issues (inefficiencies, potential bottlenecks)

Prioritize issues by severity:
- CRITICAL: Security vulnerabilities, data exposure, crashes
- HIGH: Major bugs, significant quality issues
- MEDIUM: Code quality, maintainability concerns
- LOW: Style, minor improvements

Be constructive and specific. Always explain WHY something is an issue and HOW to fix it.

Output your review as valid JSON matching the expected schema."""

    DEFAULT_CRITERIA = [
        "No hardcoded secrets - API keys, passwords, tokens must not be in code",
        "No SQL injection vulnerabilities - Parameterized queries required",
        "No command injection - User input must not be passed to shell commands",
        "Proper error handling - Exceptions should be caught and handled appropriately",
        "No obvious XSS vulnerabilities - User input must be sanitized before rendering",
        "Resource cleanup - Files, connections, etc. should be properly closed",
        "Input validation - User/external input should be validated",
        "Reasonable complexity - Functions should not be excessively long or complex",
    ]

    DEFAULT_USER_PROMPT_TEMPLATE = """Review the following code for quality, security, and best practices.

Validation Criteria:
{criteria}

Code to Review:
```
{content}
```

Provide your review as JSON with this structure:
{{
  "approved": boolean (false if any critical or high severity issues),
  "issues": [
    {{
      "severity": "critical|high|medium|low",
      "line": number or null,
      "category": "security|quality|style|performance",
      "message": "description of issue",
      "suggestion": "how to fix"
    }}
  ],
  "suggestions": ["general improvement suggestion"],
  "summary": "brief overall assessment"
}}"""

    def __init__(
        self,
        config: Config = None,
        system_prompt: Optional[str] = None,
        validation_criteria: Optional[List[str]] = None,
        user_prompt_template: Optional[str] = None,
        output_format: str = "json",
        config_file: Optional[str] = None,
        preset: Optional[str] = None,
    ):
        """
        Initialize the CodeReviewer.

        Args:
            config: Agent-workshop Config (reads .env for provider settings)
            system_prompt: Custom system prompt for the reviewer
            validation_criteria: List of validation criteria
            user_prompt_template: Template with {criteria}, {content} placeholders
            output_format: Output format (json recommended)
            config_file: Path to YAML configuration file
            preset: Name of built-in preset (general, security_focused, etc.)
        """
        super().__init__(config)

        # Load configuration from file or preset
        prompt_config = self._load_prompt_config(
            config_file=config_file,
            preset=preset,
        )

        # Apply configuration with priority order
        self.system_prompt = (
            system_prompt
            or prompt_config.get("system_prompt")
            or os.getenv("CODE_REVIEWER_SYSTEM_PROMPT")
            or self.DEFAULT_SYSTEM_PROMPT
        )

        self.validation_criteria = (
            validation_criteria
            or prompt_config.get("validation_criteria")
            or self._parse_env_criteria()
            or self.DEFAULT_CRITERIA
        )

        self.user_prompt_template = (
            user_prompt_template
            or prompt_config.get("user_prompt_template")
            or self.DEFAULT_USER_PROMPT_TEMPLATE
        )

        self.output_format = (
            output_format
            if output_format != "json"
            else prompt_config.get("output_format", "json")
        )

    def _load_prompt_config(
        self,
        config_file: Optional[str] = None,
        preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Load prompt configuration from file or preset.

        Args:
            config_file: Path to YAML configuration file
            preset: Name of built-in preset

        Returns:
            Dictionary with configuration values
        """
        config: Dict[str, Any] = {}

        # Load from preset first
        if preset:
            try:
                from .presets import get_preset

                config = get_preset(preset)
            except (ImportError, ValueError):
                pass

        # Load from config file (overrides preset)
        if config_file and Path(config_file).exists():
            try:
                import yaml

                with open(config_file) as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("code_reviewer", {}))
            except ImportError:
                # PyYAML not installed
                pass

        # Try default config file location
        elif Path("prompts.yaml").exists():
            try:
                import yaml

                with open("prompts.yaml") as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("code_reviewer", {}))
            except ImportError:
                pass

        return config

    def _parse_env_criteria(self) -> Optional[List[str]]:
        """
        Parse validation criteria from environment variable.

        Expects: CODE_REVIEWER_CRITERIA="Criterion 1,Criterion 2"

        Returns:
            List of criteria strings or None
        """
        env_criteria = os.getenv("CODE_REVIEWER_CRITERIA")
        if env_criteria:
            return [c.strip() for c in env_criteria.split(",")]
        return None

    async def run(self, content: str) -> Dict[str, Any]:
        """
        Review the provided code content.

        Args:
            content: Code to review (snippet, diff, or file)

        Returns:
            dict with review results:
                - approved: bool (false if critical/high issues)
                - issues: list of issue dicts
                - suggestions: list of improvement suggestions
                - summary: brief assessment
                - timestamp: ISO format timestamp
                - raw_response: original LLM response (for debugging)
        """
        if not content or not content.strip():
            return {
                "approved": False,
                "issues": [
                    {
                        "severity": "high",
                        "line": None,
                        "category": "quality",
                        "message": "Empty or whitespace-only input",
                        "suggestion": "Provide code content to review",
                    }
                ],
                "suggestions": [],
                "summary": "No code provided for review",
                "timestamp": self._get_timestamp(),
            }

        # Format criteria as numbered list
        criteria_text = "\n".join(
            [f"{i+1}. {c}" for i, c in enumerate(self.validation_criteria)]
        )

        # Build user prompt from template
        user_prompt = self.user_prompt_template.format(
            criteria=criteria_text,
            content=content,
        )

        # Build messages with system and user prompts
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Run completion
        result = await self.complete(messages, temperature=0.3)

        # Parse JSON response
        parsed = self._parse_response(result)
        parsed["timestamp"] = self._get_timestamp()
        parsed["raw_response"] = result

        return parsed

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into structured format.

        Attempts to extract JSON from the response, handling
        markdown code blocks and other formatting.

        Args:
            response: Raw LLM response

        Returns:
            Parsed review dict
        """
        # Try to extract JSON from response
        text = response.strip()

        # Handle markdown code blocks
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

            # Ensure required fields exist
            return {
                "approved": parsed.get("approved", False),
                "issues": parsed.get("issues", []),
                "suggestions": parsed.get("suggestions", []),
                "summary": parsed.get("summary", "Review completed"),
            }
        except json.JSONDecodeError:
            # If JSON parsing fails, return a fallback response
            return {
                "approved": False,
                "issues": [
                    {
                        "severity": "medium",
                        "line": None,
                        "category": "quality",
                        "message": "Unable to parse structured response",
                        "suggestion": "Review raw_response for details",
                    }
                ],
                "suggestions": [],
                "summary": text[:200] if text else "Review completed (unstructured)",
            }

    def _get_timestamp(self) -> str:
        """Get current timestamp for tracking."""
        return datetime.now().isoformat()


# Example usage (not executed on import):
# async def main():
#     from agent_workshop import Config
#     config = Config()
#     reviewer = CodeReviewer(config)
#
#     code = '''
#     def get_user(user_id):
#         API_KEY = "sk-secret123"
#         return db.query(f"SELECT * FROM users WHERE id = {user_id}")
#     '''
#
#     result = await reviewer.run(code)
#     print(f"Approved: {result['approved']}")
#     for issue in result['issues']:
#         print(f"  [{issue['severity']}] {issue['category']}: {issue['message']}")
#
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
