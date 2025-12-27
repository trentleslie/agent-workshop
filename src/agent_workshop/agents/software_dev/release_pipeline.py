"""
Automated release pipeline with changelog validation, git operations, PR creation, and release notes generation

Generated from blueprint: software_dev_release_pipeline
Generated at: 2025-12-27T13:42:36.199661
"""

import asyncio
import json
import os
import shlex
from datetime import datetime
from typing import TypedDict, Dict, Any, List, Optional

from langgraph.graph import StateGraph, END

from agent_workshop.workflows import LangGraphAgent
from agent_workshop import Config


class ReleasePipelineState(TypedDict):
    """ReleasePipeline pipeline state."""
    version: str
    release_type: str
    changelog_content: str
    base_branch: str
    changelog_validation: dict | None
    commit_message: str | None
    pr_body: str | None
    release_notes: dict | None
    final_result: dict | None
    branch_output: str | None
    branch_success: bool | None
    stage_output: str | None
    stage_success: bool | None
    commit_output: str | None
    commit_success: bool | None
    push_output: str | None
    push_success: bool | None
    pr_output: str | None
    pr_success: bool | None


class ReleasePipeline(LangGraphAgent):
    """
    Automated release pipeline with changelog validation, git operations, PR creation, and release notes generation
    """

    def __init__(self, config: Config = None):
        super().__init__(config)
        self._working_dir = os.getcwd()

    def build_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(ReleasePipelineState)

        # Add nodes
        workflow.add_node("validate_changelog", self.validate_changelog)
        workflow.add_node("create_branch", self.create_branch)
        workflow.add_node("stage_changes", self.stage_changes)
        workflow.add_node("commit_changes", self.commit_changes)
        workflow.add_node("push_branch", self.push_branch)
        workflow.add_node("create_pr", self.create_pr)
        workflow.add_node("generate_release_notes", self.generate_release_notes)
        workflow.add_node("generate_summary", self.generate_summary)

        # Add edges
        workflow.add_edge("validate_changelog", "create_branch")
        workflow.add_edge("create_branch", "stage_changes")
        workflow.add_edge("stage_changes", "commit_changes")
        workflow.add_edge("commit_changes", "push_branch")
        workflow.add_edge("push_branch", "create_pr")
        workflow.add_edge("create_pr", "generate_release_notes")
        workflow.add_edge("generate_release_notes", "generate_summary")
        workflow.add_edge("generate_summary", END)

        # Set entry point
        workflow.set_entry_point("validate_changelog")

        return workflow.compile()

    async def validate_changelog(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Validate changelog and generate commit message"""
        prompt = """You are a release manager validating a changelog for version {version}.

Release type: {release_type}

Changelog content:
```
{changelog_content}
```

Validate the changelog and generate a commit message.

Validation criteria:
1. Has version header matching {version}
2. Has categorized changes (Added, Changed, Fixed, Removed, etc.)
3. Each change has clear description
4. Proper markdown formatting

Return JSON:
{{
  "valid": true/false,
  "issues": ["list of issues if any"],
  "commit_message": "feat(release): v{version} - brief summary",
  "pr_body": "## Release v{version}\\n\\n[formatted PR description with changelog summary]"
}}
""".format(
            **{k: (json.dumps(v, indent=2) if isinstance(v, dict) else (v or "N/A"))
               for k, v in state.items() if v is not None}
        )

        result = await self.provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3
        )

        parsed = self._parse_json_response(result)
        # Extract commit_message and pr_body to top-level state for shell commands
        return {
            **state,
            "changelog_validation": parsed,
            "commit_message": parsed.get("commit_message"),
            "pr_body": parsed.get("pr_body"),
        }

    async def create_branch(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Create release branch"""
        # Format command with state values - escape version for safety
        version = state.get("version") or ""
        command = f"git checkout -b {shlex.quote(f'release/v{version}')}"

        stdout, stderr, exit_code = await self._run_shell(
            command,
            timeout=30,
            working_dir=None
        )

        return {**state, "branch_output": stdout, "branch_success": exit_code in [0]}

    async def stage_changes(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Stage all changes for commit"""
        # Format command with state values
        command = """git add -A""".format(
            **{k: (str(v) if v is not None else "")
               for k, v in state.items()}
        )

        stdout, stderr, exit_code = await self._run_shell(
            command,
            timeout=30,
            working_dir=None
        )

        return {**state, "stage_output": stdout, "stage_success": exit_code in [0]}

    async def commit_changes(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Create release commit"""
        # Format command with state values - use shlex for safe quoting
        commit_msg = state.get("commit_message") or ""
        command = f"git commit -m {shlex.quote(commit_msg)}"

        stdout, stderr, exit_code = await self._run_shell(
            command,
            timeout=60,
            working_dir=None
        )

        return {**state, "commit_output": stdout, "commit_success": exit_code in [0]}

    async def push_branch(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Push release branch to remote"""
        # Format command with state values - escape version for safety
        version = state.get("version") or ""
        command = f"git push -u origin {shlex.quote(f'release/v{version}')}"

        stdout, stderr, exit_code = await self._run_shell(
            command,
            timeout=120,
            working_dir=None
        )

        return {**state, "push_output": stdout, "push_success": exit_code in [0]}

    async def create_pr(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Create pull request via GitHub CLI"""
        # Format command with state values - escape all values for safety
        version = state.get("version") or ""
        base_branch = state.get("base_branch") or "main"
        pr_body = state.get("pr_body") or ""
        command = f"gh pr create --base {shlex.quote(base_branch)} --title {shlex.quote(f'Release v{version}')} --body {shlex.quote(pr_body)}"

        stdout, stderr, exit_code = await self._run_shell(
            command,
            timeout=60,
            working_dir=None
        )

        return {**state, "pr_output": stdout, "pr_success": exit_code in [0]}

    async def generate_release_notes(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Generate formatted release notes"""
        prompt = """Generate release notes for version {version} based on this changelog:

```
{changelog_content}
```

PR was created: {pr_success}
PR URL: {pr_output}

Create professional release notes suitable for GitHub Releases.

Return JSON:
{{
  "title": "v{version}",
  "body": "Formatted markdown for GitHub Release",
  "highlights": ["key highlight 1", "key highlight 2"],
  "breaking_changes": ["any breaking changes"],
  "pr_url": "{pr_output}"
}}
""".format(
            **{k: (json.dumps(v, indent=2) if isinstance(v, dict) else (v or "N/A"))
               for k, v in state.items() if v is not None}
        )

        result = await self.provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3
        )

        parsed = self._parse_json_response(result)
        return {**state, "release_notes": parsed}

    async def generate_summary(self, state: ReleasePipelineState) -> ReleasePipelineState:
        """Generate final release summary"""
        prompt = """Summarize the release pipeline execution for version {version}.

Steps completed:
- Branch creation: {branch_success}
- Staging: {stage_success}
- Commit: {commit_success} ({commit_output})
- Push: {push_success}
- PR creation: {pr_success}

PR URL: {pr_output}
Release notes: {release_notes}

Return JSON:
{{
  "success": true/false (all steps passed),
  "version": "{version}",
  "pr_url": "extracted PR URL",
  "next_steps": [
    "Review and merge the PR",
    "Create GitHub Release with tag v{version}",
    "Run: uv build && twine upload dist/*"
  ],
  "summary": "Human-readable summary paragraph"
}}
""".format(
            **{k: (json.dumps(v, indent=2) if isinstance(v, dict) else (v or "N/A"))
               for k, v in state.items() if v is not None}
        )

        result = await self.provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3
        )

        parsed = self._parse_json_response(result)
        return {**state, "final_result": parsed}

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
            return {"error": "Parse failed", "raw": text[:500]}

    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the pipeline."""
        result = await super().run(input)
        return result.get("final_result", result)

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
