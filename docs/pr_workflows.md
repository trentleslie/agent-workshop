# PR Workflow Agents

This document describes the PR-related LangGraph workflows in agent-workshop.

## Overview

| Workflow | Purpose | Pattern | Use Case |
|----------|---------|---------|----------|
| **PRPipeline** | Comprehensive PR review | Linear 3-step | Review entire PR for security/quality issues |
| **PRCommentProcessor** | Auto-fix reviewer comments | Iterative loop | Process and apply fixes for PR feedback |

Both workflows maintain the **single-message pattern** externally (input → output) while orchestrating multiple internal LLM calls via LangGraph.

---

## PRPipeline

A 3-step sequential workflow that performs comprehensive PR analysis.

### Flow

```
security_scan → quality_review → generate_summary → END
```

### Steps

1. **security_scan** - Identifies security vulnerabilities:
   - Hardcoded credentials (API keys, passwords, tokens)
   - Injection vulnerabilities (SQL, command, XSS)
   - Authentication/authorization issues
   - Sensitive data exposure

2. **quality_review** - Reviews code quality (with security context):
   - Error handling and edge cases
   - Code clarity and readability
   - Resource management
   - Performance concerns

3. **generate_summary** - Consolidates findings:
   - Determines approval recommendation
   - Counts blocking issues
   - Generates GitHub-ready review comment

### Usage

```python
from agent_workshop import Config
from agent_workshop.agents.software_dev import PRPipeline

pipeline = PRPipeline(Config())

result = await pipeline.run({
    "content": code_diff,              # Required: code to review
    "title": "Add authentication",     # Optional: PR title
    "description": "Implements JWT",   # Optional: PR description
    "files_changed": ["src/auth.py"]   # Optional: file list
})

print(f"Approved: {result['approved']}")
print(f"Recommendation: {result['recommendation']}")
print(f"Blocking Issues: {result['blocking_issues']}")
print(f"\nSummary:\n{result['summary']}")
```

### Output Format

```python
{
    "approved": bool,
    "recommendation": "approve" | "request_changes" | "comment",
    "blocking_issues": int,
    "summary": "2-3 paragraph review comment",
    "security_issues": [
        {
            "severity": "critical|high|medium|low",
            "category": "credentials|injection|auth|exposure|config",
            "message": "issue description",
            "line": int | None,
            "suggestion": "how to fix"
        }
    ],
    "quality_issues": [
        {
            "severity": "high|medium|low",
            "category": "error_handling|clarity|resources|performance",
            "message": "issue description",
            "line": int | None,
            "suggestion": "how to fix"
        }
    ],
    "timestamp": "2024-01-15T10:30:00"
}
```

---

## PRCommentProcessor

An iterative loop workflow that processes unaddressed PR comments and automatically applies code fixes.

### Flow

```
fetch_comments → select_next_comment ──┐
                      ↓                │
                 (has more?)           │
                   ↙   ↘               │
            read_file  skip            │
                ↓       ↓              │
          analyze_comment              │
                ↓                      │
            generate_fix               │
                ↓                      │
            apply_fix                  │
                ↓                      │
          record_result                │
                ↓                      │
          (check loop) ───────────────→(back)
                ↓
          (exit loop)
                ↓
          generate_summary → END
```

### Steps

1. **fetch_comments** - Initialize queue from pre-fetched comments
2. **select_next_comment** - Pop next comment (loop controller)
3. **read_file** - Load the file referenced by comment
4. **analyze_comment** - LLM determines what change is needed
5. **generate_fix** - LLM generates complete fixed file content
6. **apply_fix** - Write fixed content to file
7. **record_result** - Log outcome (applied/skipped/failed)
8. **generate_summary** - Final summary of all changes

### Usage

```python
from agent_workshop import Config
from agent_workshop.agents.software_dev import PRCommentProcessor

processor = PRCommentProcessor(Config())

result = await processor.run({
    "repo_name": "owner/repo",           # Required
    "pr_number": 123,                    # Required
    "remote": "github",                  # Optional: default "github"
    "default_branch": "main",            # Optional: default "main"
    "all_comments": comments,            # Optional: pre-fetched comments
    "working_dir": "/path/to/repo",      # Optional: uses cwd if not set
    "max_iterations": 50                 # Optional: safety limit
})

print(f"Applied: {result['applied']}/{result['total_comments']}")
print(f"Files Modified: {result['files_modified']}")
print(f"\nSummary:\n{result['summary']}")
```

### Integration with Greptile MCP

```python
# Pre-fetch unaddressed comments using Greptile MCP
comments = await mcp__plugin_greptile_greptile__list_merge_request_comments(
    name="owner/repo",
    remote="github",
    defaultBranch="main",
    prNumber=123,
    addressed=False  # Only unaddressed comments
)

# Pass to processor
result = await processor.run({
    "repo_name": "owner/repo",
    "pr_number": 123,
    "all_comments": comments,
    "working_dir": "/path/to/repo"
})
```

### Output Format

```python
{
    "total_comments": int,
    "applied": int,                      # Successfully applied fixes
    "skipped": int,                      # Skipped (can't auto-fix)
    "failed": int,                       # Failed to apply
    "summary": "2-3 paragraph summary",
    "files_modified": ["file1.py", "file2.py"],
    "next_steps": ["Run tests", "Review changes", "Commit"],
    "details": [
        {
            "comment_id": "abc123",
            "path": "src/main.py",
            "line": 42,
            "comment_body": "Add type hints",
            "status": "applied|skipped|failed",
            "explanation": "Fixed with type annotations",
            "change_type": "enhancement",
            "complexity": "simple"
        }
    ],
    "timestamp": "2024-01-15T10:30:00"
}
```

---

## Configuration

Both workflows support 3-level configuration priority:

1. **Constructor parameters** (highest priority)
2. **YAML config file** (`prompts.yaml`)
3. **Built-in defaults** (lowest priority)

### Custom Prompts

```python
# PRPipeline
pipeline = PRPipeline(
    config=Config(),
    security_prompt="Custom security scan...",
    quality_prompt="Custom quality review...",
    summary_prompt="Custom summary..."
)

# PRCommentProcessor
processor = PRCommentProcessor(
    config=Config(),
    analyze_prompt="Custom analysis prompt",
    generate_fix_prompt="Custom fix generation prompt",
    summary_prompt="Custom summary prompt"
)
```

---

## Environment Setup

Create `.env.development` in your project:

```bash
AGENT_WORKSHOP_ENV=development
CLAUDE_SDK_ENABLED=true

# Optional but recommended for observability
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## Comparison

| Aspect | PRPipeline | PRCommentProcessor |
|--------|-----------|-------------------|
| **Purpose** | Review entire PR | Fix individual comments |
| **Flow** | Linear 3-step | Iterative loop |
| **Input** | Code diff + metadata | Comment list + repo info |
| **Output** | Single review | Per-comment fixes |
| **LLM Calls** | 3 fixed | Variable (1-3 per comment) |
| **File Mutations** | Read-only | Writes fixes to files |
| **Main Use Case** | PR review automation | Auto-fix reviewer feedback |
