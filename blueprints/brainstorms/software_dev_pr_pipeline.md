# Agent Brainstorm: PR Review Pipeline

---

## Metadata

| Field | Value |
|-------|-------|
| **Name** | `pr_pipeline` |
| **Domain** | `software_dev` |
| **Type** | `langgraph` |
| **Author** | agent-workshop team |
| **Date** | 2024-12-16 |
| **Status** | Ready for Spec |

---

## Problem Statement

Single-pass code review (like CodeReviewer) is fast but can miss issues that require multi-step analysis. For PR reviews, we need:
1. **Security-first scanning** - Check for vulnerabilities before anything else
2. **Contextual quality review** - Review quality in context of security findings
3. **Consolidated summary** - Combine all findings into actionable feedback

A LangGraph workflow allows each step to build on previous findings, with state management for tracking issues across steps.

---

## Description

A multi-step PR review pipeline that performs thorough code analysis in three stages:
1. **Security Scan** - Identify security vulnerabilities, secrets, injection risks
2. **Quality Review** - Analyze code quality, error handling, maintainability
3. **Summary Generation** - Consolidate findings into PR-ready feedback

Each step has access to the results of previous steps, enabling contextual analysis. The pipeline maintains state throughout, accumulating issues and building a comprehensive review.

---

## Input Specification

| Field | Value |
|-------|-------|
| **Type** | `dict` |
| **Description** | PR content with code and optional metadata |

### Input Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | `str` | Yes | Code diff or file contents |
| `title` | `str` | No | PR title for context |
| `description` | `str` | No | PR description for context |
| `files_changed` | `list[str]` | No | List of changed file paths |

### Example Input

```python
{
    "content": """
    def get_user(user_id):
        API_KEY = "sk-secret123"
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return db.execute(query)
    """,
    "title": "Add user retrieval function",
    "description": "Implements user lookup by ID"
}
```

---

## Output Specification

| Field | Value |
|-------|-------|
| **Type** | `dict` |

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `approved` | `bool` | Overall approval status |
| `security_issues` | `list[dict]` | Security findings from step 1 |
| `quality_issues` | `list[dict]` | Quality findings from step 2 |
| `summary` | `str` | Consolidated PR feedback |
| `recommendation` | `str` | approve / request_changes / comment |
| `blocking_issues` | `int` | Count of critical/high issues |

### Example Output

```json
{
  "approved": false,
  "security_issues": [
    {
      "severity": "critical",
      "category": "credentials",
      "message": "Hardcoded API key detected",
      "line": 2,
      "suggestion": "Use environment variable or secrets manager"
    },
    {
      "severity": "critical",
      "category": "injection",
      "message": "SQL injection vulnerability",
      "line": 3,
      "suggestion": "Use parameterized queries"
    }
  ],
  "quality_issues": [
    {
      "severity": "medium",
      "category": "error_handling",
      "message": "No error handling for database operation",
      "suggestion": "Add try/except block"
    }
  ],
  "summary": "This PR has 2 critical security issues that must be addressed...",
  "recommendation": "request_changes",
  "blocking_issues": 2
}
```

---

## Workflow Steps (LangGraph)

### State Definition

```python
class PRReviewState(TypedDict):
    # Input
    content: str
    title: str | None
    description: str | None
    files_changed: list[str] | None

    # Step outputs
    security_result: dict | None
    quality_result: dict | None

    # Final output
    final_result: dict | None
```

### Step 1: Security Scan

| Field | Value |
|-------|-------|
| **Purpose** | Identify security vulnerabilities before quality review |
| **Input** | `content`, `title`, `description` |
| **Output** | `security_result` |

**Prompt:**
```
You are a security-focused code reviewer. Analyze this code for security vulnerabilities.

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
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "credentials|injection|auth|exposure|config",
      "message": "description",
      "line": number or null,
      "suggestion": "how to fix"
    }
  ],
  "critical_count": number,
  "high_count": number,
  "summary": "brief security assessment"
}
```

### Step 2: Quality Review

| Field | Value |
|-------|-------|
| **Purpose** | Review code quality in context of security findings |
| **Input** | `content`, `security_result` |
| **Output** | `quality_result` |

**Prompt:**
```
You are a code quality reviewer. Analyze this code for quality issues.

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
{
  "issues": [
    {
      "severity": "high|medium|low",
      "category": "error_handling|clarity|resources|performance|organization",
      "message": "description",
      "line": number or null,
      "suggestion": "how to fix"
    }
  ],
  "summary": "brief quality assessment"
}
```

### Step 3: Summary Generation

| Field | Value |
|-------|-------|
| **Purpose** | Consolidate findings into PR-ready feedback |
| **Input** | `content`, `security_result`, `quality_result`, `title` |
| **Output** | `final_result` |

**Prompt:**
```
You are generating a PR review summary. Consolidate the findings into actionable feedback.

PR Title: {title}

Security Findings:
{security_result}

Quality Findings:
{quality_result}

Generate a comprehensive PR review:

Return JSON:
{
  "approved": boolean (false if any critical or high severity issues),
  "recommendation": "approve|request_changes|comment",
  "blocking_issues": number (count of critical + high),
  "summary": "2-3 paragraph PR review comment suitable for GitHub"
}
```

### Workflow Edges

```
[entry] → security_scan → quality_review → generate_summary → [END]
```

Linear flow - each step builds on the previous.

---

## Test Cases

### Fixtures

| Name | Description | Value |
|------|-------------|-------|
| `clean_code` | Simple clean code | `{"content": "def add(a, b):\\n    return a + b", "title": "Add helper"}` |
| `security_issues` | Code with security problems | `{"content": "API_KEY = 'secret'\\ndb.execute(f'SELECT {id}')", "title": "Add query"}` |
| `quality_issues` | Code with quality problems | `{"content": "def f(x):\\n    return json.loads(x)['a']['b']['c']", "title": "Parse data"}` |

### Test Cases

#### Test: test_clean_code_approved

| Field | Value |
|-------|-------|
| **Input** | `{{clean_code}}` |
| **Expected** | `{"approved": true, "recommendation": "approve"}` |

#### Test: test_security_issues_blocked

| Field | Value |
|-------|-------|
| **Input** | `{{security_issues}}` |
| **Expected** | `{"approved": false, "recommendation": "request_changes", "blocking_issues": 2}` |

#### Test: test_quality_issues_flagged

| Field | Value |
|-------|-------|
| **Input** | `{{quality_issues}}` |
| **Expected** | `{"approved": true, "recommendation": "comment"}` |

---

## Presets

### Preset: thorough

| Field | Value |
|-------|-------|
| **Description** | Full security + quality review (default) |
| **Steps** | All 3 steps |

### Preset: security_only

| Field | Value |
|-------|-------|
| **Description** | Security scan only, skip quality review |
| **Steps** | security_scan → generate_summary |

### Preset: quick

| Field | Value |
|-------|-------|
| **Description** | Fast review for critical issues only |
| **Prompts** | Simplified prompts, critical/high only |

---

## Open Questions

- [x] Should steps be linear or conditional? → Linear for v1, conditional routing later
- [x] Should we support file-by-file review? → Future enhancement
- [ ] Should we cache security_result for re-reviews? → Consider for optimization

---

## Notes

- This pipeline demonstrates LangGraph state management across steps
- Each step's output is available to subsequent steps
- The summary step has access to all previous findings
- Pattern can be extended with conditional routing (e.g., skip quality if critical security issues)

---

## Iteration Log

### Version 1 (2024-12-16)

**Changes:** Initial brainstorm based on PR review workflow needs

**Results:** Ready for spec conversion

**Next:** Convert to YAML spec, implement LangGraph workflow
