"""
PR Review Pipeline Agent for Software Development.

A multi-step LangGraph workflow that performs thorough PR review:
1. Security Scan - Identify vulnerabilities and secrets
2. Quality Review - Analyze code quality and maintainability
3. Summary Generation - Consolidate into PR-ready feedback

Blueprint: blueprints/specs/software_dev_pr_pipeline.yaml
Brainstorm: blueprints/brainstorms/software_dev_pr_pipeline.md

Usage:
    from agent_workshop import Config
    from agent_workshop.agents.software_dev import PRPipeline

    pipeline = PRPipeline(Config())
    result = await pipeline.run({
        "content": code_diff,
        "title": "Add feature",
        "description": "Implements new functionality"
    })
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Optional, Dict, Any, List

from langgraph.graph import StateGraph, END

from agent_workshop.workflows import LangGraphAgent
from agent_workshop import Config


class PRReviewState(TypedDict):
    """State object for the PR review pipeline."""

    # Input fields
    content: str
    title: str | None
    description: str | None
    files_changed: List[str] | None

    # Step outputs
    security_result: Dict[str, Any] | None
    quality_result: Dict[str, Any] | None

    # Final output
    final_result: Dict[str, Any] | None


class PRPipeline(LangGraphAgent):
    """
    Multi-step PR review pipeline with security scan, quality review, and summary.

    This pipeline performs comprehensive PR analysis in three stages:
    1. Security Scan - Identify security vulnerabilities first
    2. Quality Review - Review quality in context of security findings
    3. Summary Generation - Consolidate into actionable PR feedback

    Each step has access to previous step results, enabling contextual analysis.

    Configuration Priority (highest to lowest):
    1. Constructor parameters
    2. YAML config file (prompts.yaml)
    3. Environment variables
    4. Built-in defaults

    Example:
        # Default configuration
        pipeline = PRPipeline(Config())
        result = await pipeline.run({
            "content": code_diff,
            "title": "Add authentication"
        })

        # Custom prompts
        pipeline = PRPipeline(
            config=Config(),
            security_prompt="Custom security scan...",
            quality_prompt="Custom quality review...",
        )
    """

    DEFAULT_SECURITY_PROMPT = """You are a security-focused code reviewer. Analyze this code for security vulnerabilities.

PR Title: {title}
PR Description: {description}

Code to Review:
```
{content}
```

Focus on:
1. Hardcoded credentials (API keys, passwords, tokens)
2. Injection vulnerabilities (SQL, command, XSS)
3. Authentication/authorization issues
4. Sensitive data exposure
5. Insecure configurations

Return JSON:
{{
  "issues": [
    {{
      "severity": "critical|high|medium|low",
      "category": "credentials|injection|auth|exposure|config",
      "message": "description",
      "line": number or null,
      "suggestion": "how to fix"
    }}
  ],
  "critical_count": number,
  "high_count": number,
  "summary": "brief security assessment"
}}"""

    DEFAULT_QUALITY_PROMPT = """You are a code quality reviewer. Analyze this code for quality issues.

Security findings from previous step:
{security_result}

Code to Review:
```
{content}
```

Focus on (excluding security issues already identified):
1. Error handling and edge cases
2. Code clarity and readability
3. Resource management
4. Performance concerns
5. Code organization

Return JSON:
{{
  "issues": [
    {{
      "severity": "high|medium|low",
      "category": "error_handling|clarity|resources|performance|organization",
      "message": "description",
      "line": number or null,
      "suggestion": "how to fix"
    }}
  ],
  "summary": "brief quality assessment"
}}"""

    DEFAULT_SUMMARY_PROMPT = """You are generating a PR review summary. Consolidate the findings into actionable feedback.

PR Title: {title}

Security Findings:
{security_result}

Quality Findings:
{quality_result}

Generate a comprehensive PR review.

Return JSON:
{{
  "approved": boolean (false if any critical or high severity issues),
  "recommendation": "approve|request_changes|comment",
  "blocking_issues": number (count of critical + high),
  "summary": "2-3 paragraph PR review comment suitable for GitHub"
}}"""

    def __init__(
        self,
        config: Config = None,
        security_prompt: Optional[str] = None,
        quality_prompt: Optional[str] = None,
        summary_prompt: Optional[str] = None,
        config_file: Optional[str] = None,
    ):
        """
        Initialize the PRPipeline.

        Args:
            config: Agent-workshop Config
            security_prompt: Custom prompt for security scan step
            quality_prompt: Custom prompt for quality review step
            summary_prompt: Custom prompt for summary generation step
            config_file: Path to YAML configuration file
        """
        # Load configuration before super().__init__() which calls build_graph()
        prompt_config = self._load_prompt_config(config_file=config_file)

        # Apply configuration with priority order
        self.security_prompt = (
            security_prompt
            or prompt_config.get("security_prompt")
            or os.getenv("PR_PIPELINE_SECURITY_PROMPT")
            or self.DEFAULT_SECURITY_PROMPT
        )

        self.quality_prompt = (
            quality_prompt
            or prompt_config.get("quality_prompt")
            or os.getenv("PR_PIPELINE_QUALITY_PROMPT")
            or self.DEFAULT_QUALITY_PROMPT
        )

        self.summary_prompt = (
            summary_prompt
            or prompt_config.get("summary_prompt")
            or os.getenv("PR_PIPELINE_SUMMARY_PROMPT")
            or self.DEFAULT_SUMMARY_PROMPT
        )

        super().__init__(config)

    def _load_prompt_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Load prompt configuration from YAML file.

        Args:
            config_file: Path to YAML configuration file

        Returns:
            Dictionary with configuration values
        """
        config: Dict[str, Any] = {}

        # Load from specified config file
        if config_file and Path(config_file).exists():
            try:
                import yaml

                with open(config_file) as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("pr_pipeline", {}))
            except ImportError:
                pass

        # Try default config file location
        elif Path("prompts.yaml").exists():
            try:
                import yaml

                with open("prompts.yaml") as f:
                    yaml_config = yaml.safe_load(f)
                    config.update(yaml_config.get("pr_pipeline", {}))
            except ImportError:
                pass

        return config

    def build_graph(self):
        """Build the LangGraph workflow for PR review."""
        workflow = StateGraph(PRReviewState)

        # Add nodes for each step
        workflow.add_node("security_scan", self.security_scan)
        workflow.add_node("quality_review", self.quality_review)
        workflow.add_node("generate_summary", self.generate_summary)

        # Define linear flow
        workflow.add_edge("security_scan", "quality_review")
        workflow.add_edge("quality_review", "generate_summary")
        workflow.add_edge("generate_summary", END)

        # Set entry point
        workflow.set_entry_point("security_scan")

        return workflow.compile()

    async def security_scan(self, state: PRReviewState) -> PRReviewState:
        """
        Step 1: Security-focused code scan.

        Identifies security vulnerabilities before quality review.
        Results inform the quality review step.

        Args:
            state: Current pipeline state

        Returns:
            Updated state with security_result
        """
        # Format prompt with state values
        prompt = self.security_prompt.format(
            title=state.get("title") or "Untitled PR",
            description=state.get("description") or "No description provided",
            content=state["content"],
        )

        messages = [{"role": "user", "content": prompt}]

        result = await self.provider.complete(messages, temperature=0.3)

        # Parse JSON response
        parsed = self._parse_json_response(result)

        return {
            **state,
            "security_result": parsed,
        }

    async def quality_review(self, state: PRReviewState) -> PRReviewState:
        """
        Step 2: Code quality review.

        Reviews quality in context of security findings.
        Avoids duplicating security issues already identified.

        Args:
            state: Current pipeline state with security_result

        Returns:
            Updated state with quality_result
        """
        # Format security result for prompt
        security_summary = json.dumps(state.get("security_result", {}), indent=2)

        prompt = self.quality_prompt.format(
            security_result=security_summary,
            content=state["content"],
        )

        messages = [{"role": "user", "content": prompt}]

        result = await self.provider.complete(messages, temperature=0.3)

        # Parse JSON response
        parsed = self._parse_json_response(result)

        return {
            **state,
            "quality_result": parsed,
        }

    async def generate_summary(self, state: PRReviewState) -> PRReviewState:
        """
        Step 3: Generate consolidated PR review summary.

        Combines security and quality findings into actionable feedback
        suitable for a GitHub PR comment.

        Args:
            state: Current pipeline state with security_result and quality_result

        Returns:
            Updated state with final_result
        """
        # Format findings for prompt
        security_summary = json.dumps(state.get("security_result", {}), indent=2)
        quality_summary = json.dumps(state.get("quality_result", {}), indent=2)

        prompt = self.summary_prompt.format(
            title=state.get("title") or "Untitled PR",
            security_result=security_summary,
            quality_result=quality_summary,
        )

        messages = [{"role": "user", "content": prompt}]

        result = await self.provider.complete(messages, temperature=0.3)

        # Parse JSON response
        summary_result = self._parse_json_response(result)

        # Build final result combining all findings
        security_issues = state.get("security_result", {}).get("issues", [])
        quality_issues = state.get("quality_result", {}).get("issues", [])

        final_result = {
            "approved": summary_result.get("approved", False),
            "recommendation": summary_result.get("recommendation", "request_changes"),
            "blocking_issues": summary_result.get("blocking_issues", 0),
            "summary": summary_result.get("summary", "Review completed"),
            "security_issues": security_issues,
            "quality_issues": quality_issues,
            "timestamp": datetime.now().isoformat(),
        }

        return {
            **state,
            "final_result": final_result,
        }

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response.

        Handles markdown code blocks and other formatting.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary
        """
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
            return json.loads(text)
        except json.JSONDecodeError:
            # Return a fallback structure
            return {
                "issues": [],
                "summary": text[:500] if text else "Unable to parse response",
                "parse_error": True,
            }

    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the PR review pipeline.

        Args:
            input: Dictionary with:
                - content (str, required): Code to review
                - title (str, optional): PR title
                - description (str, optional): PR description
                - files_changed (list, optional): Changed file paths

        Returns:
            Dictionary with:
                - approved (bool): Overall approval status
                - recommendation (str): approve/request_changes/comment
                - blocking_issues (int): Count of critical/high issues
                - summary (str): PR-ready review comment
                - security_issues (list): Security findings
                - quality_issues (list): Quality findings
                - timestamp (str): ISO timestamp
        """
        # Ensure required fields
        if "content" not in input:
            return {
                "approved": False,
                "recommendation": "request_changes",
                "blocking_issues": 1,
                "summary": "No code content provided for review",
                "security_issues": [],
                "quality_issues": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Initialize optional fields
        state: PRReviewState = {
            "content": input["content"],
            "title": input.get("title"),
            "description": input.get("description"),
            "files_changed": input.get("files_changed"),
            "security_result": None,
            "quality_result": None,
            "final_result": None,
        }

        # Run the workflow
        result = await super().run(state)

        # Return final_result or the full state
        return result.get("final_result", result)


# Example usage (not executed on import):
# async def main():
#     from agent_workshop import Config
#
#     config = Config()
#     pipeline = PRPipeline(config)
#
#     code = '''
#     def get_user(user_id):
#         API_KEY = "sk-secret123"
#         return db.query(f"SELECT * FROM users WHERE id = {user_id}")
#     '''
#
#     result = await pipeline.run({
#         "content": code,
#         "title": "Add user retrieval",
#         "description": "Implements user lookup by ID"
#     })
#
#     print(f"Approved: {result['approved']}")
#     print(f"Recommendation: {result['recommendation']}")
#     print(f"Blocking Issues: {result['blocking_issues']}")
#     print(f"\nSummary:\n{result['summary']}")
#
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
