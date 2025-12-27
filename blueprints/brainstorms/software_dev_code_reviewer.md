# Agent Brainstorm: Code Reviewer

---

## Metadata

| Field | Value |
|-------|-------|
| **Name** | `code_reviewer` |
| **Domain** | `software_dev` |
| **Type** | `simple` |
| **Author** | agent-workshop team |
| **Date** | 2024-12-16 |
| **Status** | Ready for Spec |

---

## Problem Statement

Developers need quick, consistent code reviews that catch common issues before human review. Manual code review is time-consuming and inconsistent - different reviewers focus on different things. An automated first-pass review can catch obvious issues (security vulnerabilities, style violations, missing error handling) and free up human reviewers to focus on architecture and business logic.

---

## Description

A simple agent that reviews code snippets, diffs, or entire files for quality, security, and best practices. It produces a structured report with approval status, identified issues with severity levels, and actionable suggestions. The agent is language-agnostic but can be configured with language-specific presets (Python, JavaScript, etc.).

---

## Input Specification

| Field | Value |
|-------|-------|
| **Type** | `string` |
| **Description** | Code content to review (snippet, diff, or file) |

### Input Validation Rules

- [x] Input must be non-empty
- [x] Input should be valid text (not binary)
- [ ] Optional: Detect programming language from content

### Example Input

```python
def get_user_data(user_id):
    API_KEY = "sk-1234567890abcdef"
    response = requests.get(f"https://api.example.com/users/{user_id}",
                           headers={"Authorization": f"Bearer {API_KEY}"})
    return response.json()
```

---

## Output Specification

| Field | Value |
|-------|-------|
| **Type** | `dict` |

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `approved` | `bool` | Whether code passes review (no critical/high issues) |
| `issues` | `list[dict]` | List of identified issues |
| `issues[].severity` | `str` | critical / high / medium / low |
| `issues[].line` | `int \| None` | Line number if identifiable |
| `issues[].category` | `str` | security / quality / style / performance |
| `issues[].message` | `str` | Description of the issue |
| `issues[].suggestion` | `str` | How to fix it |
| `suggestions` | `list[str]` | General improvement suggestions |
| `summary` | `str` | Brief overall assessment |

### Example Output

```json
{
  "approved": false,
  "issues": [
    {
      "severity": "critical",
      "line": 2,
      "category": "security",
      "message": "Hardcoded API key detected",
      "suggestion": "Move to environment variable or secrets manager"
    },
    {
      "severity": "medium",
      "line": 3,
      "category": "quality",
      "message": "No error handling for HTTP request",
      "suggestion": "Add try/except block and handle connection errors"
    }
  ],
  "suggestions": [
    "Consider adding type hints for better code clarity",
    "Add docstring explaining function purpose and parameters"
  ],
  "summary": "Code has a critical security issue (hardcoded credentials) that must be addressed before merge."
}
```

---

## Prompts

### System Prompt

```
You are an expert code reviewer with deep knowledge of software security, clean code principles, and industry best practices.

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

Output your review as valid JSON matching the expected schema.
```

### User Prompt Template

```
Review the following code for quality, security, and best practices.

Validation Criteria:
{criteria}

Code to Review:
```
{content}
```

Provide your review as JSON with this structure:
{
  "approved": boolean (false if any critical or high severity issues),
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "line": number or null,
      "category": "security|quality|style|performance",
      "message": "description of issue",
      "suggestion": "how to fix"
    }
  ],
  "suggestions": ["general improvement suggestion"],
  "summary": "brief overall assessment"
}
```

---

## Validation Criteria

1. [x] **No hardcoded secrets** - API keys, passwords, tokens must not be in code
2. [x] **No SQL injection vulnerabilities** - Parameterized queries required
3. [x] **No command injection** - User input must not be passed to shell commands
4. [x] **Proper error handling** - Exceptions should be caught and handled appropriately
5. [x] **No obvious XSS vulnerabilities** - User input must be sanitized before rendering
6. [x] **Resource cleanup** - Files, connections, etc. should be properly closed
7. [x] **Input validation** - User/external input should be validated
8. [x] **Reasonable complexity** - Functions should not be excessively long or complex
9. [ ] **Code clarity** - Names should be descriptive, logic should be clear
10. [ ] **Documentation** - Public APIs should have docstrings/comments

---

## Workflow Steps (LangGraph Only)

*N/A - This is a simple agent.*

---

## Test Cases

### Fixtures

| Name | Description | Value |
|------|-------------|-------|
| `clean_python` | Simple clean Python code | `def add(a, b):\n    return a + b` |
| `hardcoded_secret` | Code with hardcoded API key | `API_KEY = "sk-secret123"\nrequests.get(url, headers={"key": API_KEY})` |
| `sql_injection` | Code vulnerable to SQL injection | `query = f"SELECT * FROM users WHERE id = {user_id}"\ncursor.execute(query)` |
| `no_error_handling` | Code without error handling | `data = json.loads(response.text)\nreturn data["result"]` |

### Test Cases

#### Test: test_clean_code_approved

| Field | Value |
|-------|-------|
| **Input** | `{{clean_python}}` |
| **Expected** | `{"approved": true, "issues": []}` |
| **Should Raise** | `false` |

#### Test: test_detects_hardcoded_secret

| Field | Value |
|-------|-------|
| **Input** | `{{hardcoded_secret}}` |
| **Expected** | `{"approved": false, "issues": [{"severity": "critical", "category": "security"}]}` |
| **Should Raise** | `false` |

#### Test: test_detects_sql_injection

| Field | Value |
|-------|-------|
| **Input** | `{{sql_injection}}` |
| **Expected** | `{"approved": false, "issues": [{"severity": "critical", "category": "security"}]}` |
| **Should Raise** | `false` |

#### Test: test_detects_missing_error_handling

| Field | Value |
|-------|-------|
| **Input** | `{{no_error_handling}}` |
| **Expected** | `{"approved": true, "issues": [{"severity": "medium", "category": "quality"}]}` |
| **Should Raise** | `false` |

---

## Presets

### Preset: security_focused

| Field | Value |
|-------|-------|
| **Description** | Focus on security issues only (for security team review) |
| **System Prompt Override** | Emphasize security-only review |
| **Criteria Override** | Only security-related criteria |

### Preset: python_specific

| Field | Value |
|-------|-------|
| **Description** | Python-specific review with PEP 8, type hints, etc. |
| **System Prompt Override** | Add Python-specific knowledge |
| **Criteria Override** | Add PEP 8, type hints, Python idioms |

### Preset: javascript_specific

| Field | Value |
|-------|-------|
| **Description** | JavaScript/TypeScript review |
| **System Prompt Override** | Add JS/TS-specific knowledge |
| **Criteria Override** | Add ESLint rules, async patterns, etc. |

### Preset: quick_scan

| Field | Value |
|-------|-------|
| **Description** | Fast review for critical issues only |
| **System Prompt Override** | Focus on critical/high only |
| **Criteria Override** | First 4 criteria only |

---

## Open Questions

- [x] Should output be JSON or allow markdown? → JSON for machine readability
- [x] Should we detect language automatically? → Nice to have, not required for v1
- [ ] Should we support file paths as input (read file)? → Future enhancement
- [ ] Should we integrate with diff format for PRs? → Consider for pr_pipeline

---

## Notes

- This agent is designed to be a "first pass" reviewer, not a replacement for human review
- Output is structured JSON to enable downstream processing (CI/CD integration, dashboards)
- Presets allow customization without changing core agent logic
- Consider rate limiting for large codebases (many files)

---

## Iteration Log

### Version 1 (2024-12-16)

**Changes:** Initial brainstorm based on common code review needs

**Results:** Ready for spec conversion

**Next:** Convert to YAML spec, implement agent
