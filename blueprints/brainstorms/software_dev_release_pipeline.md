# Software Dev Release Pipeline - Brainstorm

## Agent Purpose

A hybrid LangGraph workflow that automates the release process for Python packages:
- Validates changelog and generates commit messages (LLM)
- Executes git operations (shell actions)
- Creates pull requests via GitHub CLI (shell actions)
- Generates release notes and announcements (LLM)

## Domain

`software_dev` - Software development automation

## Agent Type

`langgraph` - Multi-step workflow with mixed LLM and shell action steps

## Problem Being Solved

Manual release processes are:
- Error-prone (forgetting steps, typos)
- Time-consuming (running multiple commands)
- Inconsistent (different commit message formats)

This agent automates the entire flow while using LLM for intelligent content generation.

## Input/Output

### Input
- `version`: Version string (e.g., "0.3.0")
- `release_type`: Type of release (major, minor, patch)
- `changelog_content`: Changelog text for this release
- `base_branch`: Branch to create PR against (default: "main")

### Output
- `success`: Boolean indicating overall success
- `pr_url`: URL of created pull request
- `commit_sha`: SHA of the release commit
- `release_notes`: Generated release notes
- `summary`: Human-readable summary

## Workflow Steps

### 1. validate_changelog (LLM)
- Validates changelog format and content
- Generates commit message following conventional commits
- Checks version number matches

### 2. create_branch (ACTION: shell)
- `git checkout -b release/v{version}`

### 3. stage_changes (ACTION: shell)
- `git add -A`

### 4. commit_changes (ACTION: shell)
- `git commit -m "{commit_message}"`

### 5. push_branch (ACTION: shell)
- `git push -u origin release/v{version}`

### 6. create_pr (ACTION: shell)
- `gh pr create --title "Release v{version}" --body "{pr_body}"`

### 7. generate_release_notes (LLM)
- Creates formatted release notes from changelog
- Suitable for GitHub Releases page

### 8. generate_summary (LLM)
- Consolidates all results
- Provides next steps (merge PR, tag release, publish to PyPI)

## Validation Criteria

1. Changelog has proper version header
2. Changes are categorized (Added, Changed, Fixed, etc.)
3. No hardcoded secrets in staged files
4. Version follows semver format
5. Git operations complete successfully

## Test Fixtures

- `valid_changelog`: Well-formatted changelog entry
- `invalid_changelog`: Missing version header
- `empty_changelog`: No content

## Notes

- Uses `gh` CLI for GitHub operations (must be authenticated)
- Creates branch and PR rather than pushing directly to main
- LLM generates all text content; shell executes all commands
- Fails fast on any shell command error
