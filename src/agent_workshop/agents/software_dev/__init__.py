"""
Software Development Agents for agent-workshop.

This module provides pre-built agents for software development tasks:
- CodeReviewer: Simple agent for code review (single-message pattern)
- PRPipeline: Multi-step PR review workflow (LangGraph)
- ReleasePipeline: Automated release workflow with git/PR operations (LangGraph)
- PRCommentProcessor: Iterative PR comment processor with auto-fix (LangGraph)

Usage:
    # Simple code review
    from agent_workshop.agents.software_dev import CodeReviewer
    from agent_workshop import Config

    reviewer = CodeReviewer(Config())
    result = await reviewer.run(code_content)

    # Multi-step PR review
    from agent_workshop.agents.software_dev import PRPipeline

    pipeline = PRPipeline(Config())
    result = await pipeline.run({
        "content": code_diff,
        "title": "Add feature"
    })

    # Automated release pipeline
    from agent_workshop.agents.software_dev import ReleasePipeline

    release = ReleasePipeline(Config())
    result = await release.run({
        "version": "0.3.0",
        "release_type": "minor",
        "changelog_content": changelog_text,
        "base_branch": "main",
    })

    # Process PR comments and auto-apply fixes
    from agent_workshop.agents.software_dev import PRCommentProcessor

    processor = PRCommentProcessor(Config())
    result = await processor.run({
        "repo_name": "owner/repo",
        "pr_number": 123,
        "all_comments": fetched_comments,  # From Greptile MCP
        "working_dir": "/path/to/repo",
    })
"""

from .code_reviewer import CodeReviewer
from .pr_pipeline import PRPipeline
from .release_pipeline import ReleasePipeline
from .pr_comment_processor import PRCommentProcessor
from .presets import get_preset, list_presets, PRESETS

__all__ = [
    "CodeReviewer",
    "PRPipeline",
    "ReleasePipeline",
    "PRCommentProcessor",
    "get_preset",
    "list_presets",
    "PRESETS",
]
