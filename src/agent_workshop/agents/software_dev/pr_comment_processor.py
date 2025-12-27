"""
PR Comment Processor Agent for Software Development.

A LangGraph workflow that processes unaddressed PR comments and auto-applies fixes:
1. Fetch Comments - Load unaddressed comments (pre-fetched or via gh CLI)
2. Iterate - For each comment:
   a. Read the file referenced by the comment
   b. Analyze what change is requested
   c. Generate a code fix
   d. Apply the fix to the file
   e. Record the result
3. Generate Summary - Create final report of all changes made

Uses conditional edges to loop through comments one at a time.

Usage:
    from agent_workshop import Config
    from agent_workshop.agents.software_dev import PRCommentProcessor

    processor = PRCommentProcessor(Config())
    result = await processor.run({
        "repo_name": "owner/repo",
        "pr_number": 123,
        "remote": "github",
        "default_branch": "main",
        "all_comments": comments,  # Pre-fetched from Greptile MCP
        "working_dir": "/path/to/repo",
    })
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Dict, Any, List

from langgraph.graph import StateGraph, END

from agent_workshop.workflows import LangGraphAgent
from agent_workshop import Config


class PRCommentProcessorState(TypedDict):
    """State object for the PR comment processor workflow."""

    # Input fields
    repo_name: str
    pr_number: int
    remote: str
    default_branch: str
    working_dir: str | None

    # Comment queue
    all_comments: List[Dict[str, Any]] | None
    pending_comments: List[Dict[str, Any]]
    current_comment: Dict[str, Any] | None
    processed_comments: List[Dict[str, Any]]

    # Current iteration state
    current_file_path: str | None
    current_file_content: str | None
    analysis_result: Dict[str, Any] | None
    proposed_fix: Dict[str, Any] | None

    # Loop control
    has_more_comments: bool
    iteration_count: int
    max_iterations: int

    # Final output
    final_result: Dict[str, Any] | None


class PRCommentProcessor(LangGraphAgent):
    """
    Iterative PR comment processor that auto-applies code fixes.

    This workflow processes unaddressed PR comments by:
    1. Reading the file each comment references
    2. Analyzing what change the reviewer is requesting
    3. Generating a code fix based on the analysis
    4. Applying the fix directly to the file
    5. Recording the result (applied, skipped, or failed)

    Uses a loop pattern with conditional edges to process comments
    one at a time until the queue is empty.

    Example:
        # With pre-fetched comments from Greptile MCP
        processor = PRCommentProcessor(Config())
        result = await processor.run({
            "repo_name": "owner/repo",
            "pr_number": 42,
            "remote": "github",
            "default_branch": "main",
            "all_comments": fetched_comments,
            "working_dir": "/path/to/repo",
        })

        print(f"Applied: {result['applied']}/{result['total_comments']}")
    """

    DEFAULT_ANALYZE_PROMPT = """You are analyzing a PR review comment to understand what code change is needed.

Comment:
```
{comment_body}
```

File: {file_path}
Line: {line_number}

Current file content:
```
{file_content}
```

{suggestion_section}

Analyze what change the reviewer is requesting.

Return JSON:
{{
  "understood": true or false,
  "change_type": "refactor|bugfix|style|documentation|enhancement|removal",
  "description": "Clear description of what needs to change",
  "affected_lines": [list of line numbers or empty],
  "complexity": "trivial|simple|moderate|complex",
  "can_auto_fix": true or false,
  "skip_reason": null or "reason if can't auto-fix"
}}"""

    DEFAULT_GENERATE_FIX_PROMPT = """You are generating a code fix based on a PR review comment.

Comment:
```
{comment_body}
```

Analysis:
{analysis_result}

Current file content ({file_path}):
```
{file_content}
```

Generate the complete fixed file content that addresses the reviewer's feedback.

Return JSON:
{{
  "success": true or false,
  "full_file_content": "complete new file content with the fix applied",
  "changes_summary": "brief description of what was changed",
  "lines_changed": number of lines modified
}}

IMPORTANT: The full_file_content must be the COMPLETE file content, not just the changed portion."""

    DEFAULT_SUMMARY_PROMPT = """You are generating a summary of PR comment processing.

Processed Comments:
{processed_comments}

Repository: {repo_name}
PR Number: {pr_number}

Generate a summary suitable for a developer to review.

Return JSON:
{{
  "total_comments": number,
  "applied": number,
  "skipped": number,
  "failed": number,
  "summary": "2-3 paragraph summary of all changes made",
  "files_modified": ["list of files that were modified"],
  "next_steps": ["recommended actions like 'Run tests', 'Review changes', 'Commit if satisfied'"]
}}"""

    def __init__(
        self,
        config: Config = None,
        analyze_prompt: str | None = None,
        generate_fix_prompt: str | None = None,
        summary_prompt: str | None = None,
        max_iterations: int = 50,
        working_dir: str | None = None,
    ):
        """
        Initialize the PRCommentProcessor.

        Args:
            config: Agent-workshop Config
            analyze_prompt: Custom prompt for comment analysis step
            generate_fix_prompt: Custom prompt for fix generation step
            summary_prompt: Custom prompt for summary generation step
            max_iterations: Maximum comments to process (safety limit)
            working_dir: Default working directory for file operations
        """
        self.analyze_prompt = analyze_prompt or self.DEFAULT_ANALYZE_PROMPT
        self.generate_fix_prompt = generate_fix_prompt or self.DEFAULT_GENERATE_FIX_PROMPT
        self.summary_prompt = summary_prompt or self.DEFAULT_SUMMARY_PROMPT
        self.max_iterations = max_iterations
        self._working_dir = working_dir or os.getcwd()

        super().__init__(config)

    def build_graph(self):
        """Build the LangGraph workflow with loop for iterating through comments."""
        workflow = StateGraph(PRCommentProcessorState)

        # Add nodes for each step
        workflow.add_node("fetch_comments", self.fetch_comments)
        workflow.add_node("select_next_comment", self.select_next_comment)
        workflow.add_node("read_file", self.read_file)
        workflow.add_node("analyze_comment", self.analyze_comment)
        workflow.add_node("generate_fix", self.generate_fix)
        workflow.add_node("apply_fix", self.apply_fix)
        workflow.add_node("record_result", self.record_result)
        workflow.add_node("generate_summary", self.generate_summary)

        # Entry edge
        workflow.add_edge("fetch_comments", "select_next_comment")

        # Conditional edge: after selecting, check if we have a valid file to read
        def should_read_file(state: PRCommentProcessorState) -> str:
            comment = state.get("current_comment")
            if not comment:
                return "generate_summary"
            if not comment.get("path"):
                return "record_result"  # Skip comments without file path
            return "read_file"

        workflow.add_conditional_edges(
            "select_next_comment",
            should_read_file,
            {
                "read_file": "read_file",
                "record_result": "record_result",
                "generate_summary": "generate_summary",
            },
        )

        # Linear edges within the processing loop
        workflow.add_edge("read_file", "analyze_comment")
        workflow.add_edge("analyze_comment", "generate_fix")
        workflow.add_edge("generate_fix", "apply_fix")
        workflow.add_edge("apply_fix", "record_result")

        # Conditional edge: after recording, loop back or finish
        def should_continue(state: PRCommentProcessorState) -> str:
            # Safety limit check
            if state.get("iteration_count", 0) >= state.get("max_iterations", 50):
                return "generate_summary"
            # Check if more comments to process
            if state.get("has_more_comments", False):
                return "select_next_comment"
            return "generate_summary"

        workflow.add_conditional_edges(
            "record_result",
            should_continue,
            {
                "select_next_comment": "select_next_comment",
                "generate_summary": "generate_summary",
            },
        )

        # Exit edge
        workflow.add_edge("generate_summary", END)

        # Set entry point
        workflow.set_entry_point("fetch_comments")

        return workflow.compile()

    async def fetch_comments(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 1: Initialize comment queue from pre-fetched comments.

        Filters to unaddressed comments and initializes processing state.

        Args:
            state: Current workflow state with all_comments

        Returns:
            Updated state with pending_comments queue
        """
        all_comments = state.get("all_comments") or []

        # Filter to unaddressed comments (if not already filtered)
        unaddressed = [c for c in all_comments if not c.get("addressed", False)]

        return {
            **state,
            "pending_comments": unaddressed,
            "processed_comments": [],
            "has_more_comments": len(unaddressed) > 0,
            "iteration_count": 0,
            "max_iterations": state.get("max_iterations") or self.max_iterations,
        }

    async def select_next_comment(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 2: Pop next comment from queue and set as current.

        Manages the comment queue and loop control state.

        Args:
            state: Current workflow state

        Returns:
            Updated state with current_comment set
        """
        pending = list(state.get("pending_comments", []))

        if not pending:
            return {
                **state,
                "current_comment": None,
                "current_file_path": None,
                "has_more_comments": False,
            }

        # Pop first comment from queue
        current = pending.pop(0)

        return {
            **state,
            "current_comment": current,
            "current_file_path": current.get("path"),
            "pending_comments": pending,
            "has_more_comments": len(pending) > 0,
            "iteration_count": state.get("iteration_count", 0) + 1,
            # Reset per-iteration state
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
        }

    async def read_file(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 3: Read the file referenced by the current comment.

        Uses Python file I/O for safer file reading than shell commands.

        Args:
            state: Current workflow state with current_file_path

        Returns:
            Updated state with current_file_content
        """
        file_path = state.get("current_file_path")
        working_dir = state.get("working_dir") or self._working_dir

        if not file_path:
            return {
                **state,
                "current_file_content": None,
                "analysis_result": {"error": "No file path provided", "can_auto_fix": False},
            }

        # Resolve full path
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            full_path = os.path.join(working_dir, file_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                **state,
                "current_file_content": content,
            }
        except FileNotFoundError:
            return {
                **state,
                "current_file_content": None,
                "analysis_result": {
                    "error": f"File not found: {file_path}",
                    "can_auto_fix": False,
                    "skip_reason": "File not found",
                },
            }
        except Exception as e:
            return {
                **state,
                "current_file_content": None,
                "analysis_result": {
                    "error": str(e),
                    "can_auto_fix": False,
                    "skip_reason": f"Read error: {str(e)}",
                },
            }

    async def analyze_comment(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 4: Analyze the PR comment to understand what change is needed.

        Uses LLM to understand the reviewer's intent and determine if
        the change can be automatically applied.

        Args:
            state: Current workflow state with current_comment and current_file_content

        Returns:
            Updated state with analysis_result
        """
        # Check if already set due to error in read_file
        analysis_result = state.get("analysis_result")
        if analysis_result and analysis_result.get("error"):
            return state

        comment = state.get("current_comment", {})
        file_content = state.get("current_file_content", "")
        file_path = state.get("current_file_path", "unknown")

        # Handle code suggestion blocks
        suggestion_section = ""
        suggestion = comment.get("suggestion") or comment.get("body", "")
        if "```suggestion" in suggestion:
            suggestion_section = f"\nReviewer's suggested code:\n{suggestion}"

        prompt = self.analyze_prompt.format(
            comment_body=comment.get("body", ""),
            file_path=file_path,
            line_number=comment.get("line") or comment.get("position") or "N/A",
            file_content=file_content,
            suggestion_section=suggestion_section,
        )

        messages = [{"role": "user", "content": prompt}]
        result = await self.provider.complete(messages, temperature=0.3)
        parsed = self._parse_json_response(result)

        return {
            **state,
            "analysis_result": parsed,
        }

    async def generate_fix(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 5: Generate the code fix based on analysis.

        Uses LLM to generate the complete fixed file content.

        Args:
            state: Current workflow state with analysis_result

        Returns:
            Updated state with proposed_fix
        """
        analysis = state.get("analysis_result", {})

        # Skip if analysis says can't auto-fix
        if not analysis.get("can_auto_fix", True):
            return {
                **state,
                "proposed_fix": {
                    "success": False,
                    "skip_reason": analysis.get("skip_reason", "Cannot auto-fix"),
                },
            }

        comment = state.get("current_comment", {})
        file_content = state.get("current_file_content", "")
        file_path = state.get("current_file_path", "unknown")

        prompt = self.generate_fix_prompt.format(
            comment_body=comment.get("body", ""),
            analysis_result=json.dumps(analysis, indent=2),
            file_path=file_path,
            file_content=file_content,
        )

        messages = [{"role": "user", "content": prompt}]
        result = await self.provider.complete(messages, temperature=0.3)
        parsed = self._parse_json_response(result)

        return {
            **state,
            "proposed_fix": parsed,
        }

    async def apply_fix(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 6: Apply the generated fix to the file.

        Writes the fixed content directly to the file.

        Args:
            state: Current workflow state with proposed_fix

        Returns:
            Updated state with write status in proposed_fix
        """
        proposed_fix = state.get("proposed_fix", {})

        if not proposed_fix.get("success", False):
            return state  # Nothing to apply

        file_path = state.get("current_file_path")
        working_dir = state.get("working_dir") or self._working_dir
        new_content = proposed_fix.get("full_file_content", "")

        if not new_content:
            return {
                **state,
                "proposed_fix": {
                    **proposed_fix,
                    "applied": False,
                    "apply_error": "No file content generated",
                },
            }

        # Resolve full path
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            full_path = os.path.join(working_dir, file_path)

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {
                **state,
                "proposed_fix": {
                    **proposed_fix,
                    "applied": True,
                    "apply_error": None,
                },
            }
        except Exception as e:
            return {
                **state,
                "proposed_fix": {
                    **proposed_fix,
                    "applied": False,
                    "apply_error": str(e),
                },
            }

    async def record_result(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 7: Record the result of processing the current comment.

        Appends the result to processed_comments for the final summary.

        Args:
            state: Current workflow state

        Returns:
            Updated state with result appended to processed_comments
        """
        comment = state.get("current_comment", {})
        analysis = state.get("analysis_result", {})
        proposed_fix = state.get("proposed_fix", {})
        processed = list(state.get("processed_comments", []))

        # Determine status
        if analysis.get("error") or not analysis.get("can_auto_fix", True):
            status = "skipped"
            explanation = analysis.get("skip_reason") or analysis.get("error") or "Cannot auto-fix"
        elif proposed_fix.get("applied"):
            status = "applied"
            explanation = proposed_fix.get("changes_summary", "Fix applied")
        elif proposed_fix.get("apply_error"):
            status = "failed"
            explanation = proposed_fix.get("apply_error")
        else:
            status = "skipped"
            explanation = proposed_fix.get("skip_reason", "No fix generated")

        result = {
            "comment_id": comment.get("id", "unknown"),
            "path": comment.get("path", "unknown"),
            "line": comment.get("line") or comment.get("position"),
            "comment_body": comment.get("body", "")[:200],  # Truncate for summary
            "status": status,
            "explanation": explanation,
            "change_type": analysis.get("change_type"),
            "complexity": analysis.get("complexity"),
        }

        processed.append(result)

        return {
            **state,
            "processed_comments": processed,
        }

    async def generate_summary(self, state: PRCommentProcessorState) -> PRCommentProcessorState:
        """
        Step 8: Generate final summary of all processed comments.

        Creates a comprehensive report suitable for developer review.

        Args:
            state: Current workflow state with processed_comments

        Returns:
            Updated state with final_result
        """
        processed = state.get("processed_comments", [])

        # Count statuses
        applied = sum(1 for p in processed if p.get("status") == "applied")
        skipped = sum(1 for p in processed if p.get("status") == "skipped")
        failed = sum(1 for p in processed if p.get("status") == "failed")

        # Early exit if no comments were processed
        if not processed:
            return {
                **state,
                "final_result": {
                    "total_comments": 0,
                    "applied": 0,
                    "skipped": 0,
                    "failed": 0,
                    "summary": "No comments to process.",
                    "files_modified": [],
                    "next_steps": [],
                    "details": [],
                    "timestamp": datetime.now().isoformat(),
                },
            }

        prompt = self.summary_prompt.format(
            processed_comments=json.dumps(processed, indent=2),
            repo_name=state.get("repo_name", "unknown"),
            pr_number=state.get("pr_number", 0),
        )

        messages = [{"role": "user", "content": prompt}]
        result = await self.provider.complete(messages, temperature=0.3)
        parsed = self._parse_json_response(result)

        # Collect modified files
        files_modified = list(set(
            p.get("path") for p in processed
            if p.get("status") == "applied" and p.get("path")
        ))

        final_result = {
            "total_comments": len(processed),
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "summary": parsed.get("summary", "Processing complete."),
            "files_modified": files_modified,
            "next_steps": parsed.get("next_steps", ["Run tests", "Review changes", "Commit if satisfied"]),
            "details": processed,
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
            return {
                "success": False,
                "can_auto_fix": False,
                "summary": text[:500] if text else "Unable to parse response",
                "parse_error": True,
            }

    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the PR comment processor workflow.

        Args:
            input: Dictionary with:
                - repo_name (str, required): Repository name (e.g., "owner/repo")
                - pr_number (int, required): PR number
                - remote (str): Git remote provider ("github", "gitlab", etc.)
                - default_branch (str): Default branch name
                - all_comments (list): Pre-fetched comments from Greptile MCP
                - working_dir (str): Working directory for file operations
                - max_iterations (int): Maximum comments to process

        Returns:
            Dictionary with:
                - total_comments (int): Number of comments processed
                - applied (int): Number of fixes applied
                - skipped (int): Number of comments skipped
                - failed (int): Number of fixes that failed
                - summary (str): Human-readable summary
                - files_modified (list): List of modified file paths
                - next_steps (list): Recommended next actions
                - details (list): Detailed results for each comment
                - timestamp (str): ISO timestamp
        """
        # Validate required fields
        if "repo_name" not in input or "pr_number" not in input:
            return {
                "total_comments": 0,
                "applied": 0,
                "skipped": 0,
                "failed": 0,
                "summary": "Missing required fields: repo_name and pr_number",
                "files_modified": [],
                "next_steps": [],
                "details": [],
                "timestamp": datetime.now().isoformat(),
                "error": "Missing required fields",
            }

        # Initialize state
        state: PRCommentProcessorState = {
            "repo_name": input["repo_name"],
            "pr_number": input["pr_number"],
            "remote": input.get("remote", "github"),
            "default_branch": input.get("default_branch", "main"),
            "working_dir": input.get("working_dir") or self._working_dir,
            "all_comments": input.get("all_comments"),
            "pending_comments": [],
            "current_comment": None,
            "processed_comments": [],
            "current_file_path": None,
            "current_file_content": None,
            "analysis_result": None,
            "proposed_fix": None,
            "has_more_comments": False,
            "iteration_count": 0,
            "max_iterations": input.get("max_iterations") or self.max_iterations,
            "final_result": None,
        }

        # Run the workflow
        result = await super().run(state)

        # Return final_result or the full state
        return result.get("final_result", result)
