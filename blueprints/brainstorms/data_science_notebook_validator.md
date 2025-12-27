# Agent Brainstorm: Notebook Validator

> **Purpose**: Validate Jupyter notebooks for reproducibility, quality, and data science best practices.

---

## Metadata

| Field | Value |
|-------|-------|
| **Name** | `notebook_validator` |
| **Domain** | `data_science` |
| **Type** | `simple` |
| **Author** | agent-workshop |
| **Date** | 2024-12-27 |
| **Status** | Ready for Spec |

---

## Problem Statement

Data science notebooks often suffer from reproducibility issues, poor documentation, and code quality problems that make them difficult to share, review, or deploy. Common issues include:

- Missing or incomplete markdown documentation
- Cells executed out of order (non-linear execution)
- Hardcoded paths and credentials
- Missing dependency declarations
- Large outputs left in cells
- No clear narrative structure

Teams need automated validation to catch these issues before notebooks are shared or committed.

---

## Description

The Notebook Validator agent analyzes Jupyter notebook content (as JSON or parsed structure) and validates it against data science best practices. It checks for reproducibility issues (execution order, dependencies), documentation quality (markdown cells, comments), and security concerns (hardcoded credentials, absolute paths). Returns a structured report with pass/fail status, issues found, and improvement suggestions.

---

## Input Specification

| Field | Value |
|-------|-------|
| **Type** | `string` |
| **Description** | Jupyter notebook content (raw JSON or cell content string) |

### Input Validation Rules

- [x] Non-empty content required
- [x] Valid notebook JSON structure preferred (but plain cell content also accepted)
- [x] At least one cell required

### Example Input

```json
{
  "cells": [
    {"cell_type": "code", "source": ["import pandas as pd"]},
    {"cell_type": "markdown", "source": ["# Analysis"]},
    {"cell_type": "code", "source": ["df = pd.read_csv('/home/user/data.csv')"]}
  ]
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
| `valid` | `bool` | Overall pass/fail status |
| `score` | `int` | Quality score 0-100 |
| `issues` | `list[dict]` | List of issues found |
| `suggestions` | `list[str]` | Improvement recommendations |
| `summary` | `str` | Brief overall assessment |

### Issue Schema

| Field | Type | Description |
|-------|------|-------------|
| `severity` | `str` | critical/high/medium/low |
| `category` | `str` | reproducibility/documentation/security/quality |
| `cell_index` | `int` | Cell number (0-indexed) |
| `message` | `str` | Description of issue |

### Example Output

```json
{
  "valid": false,
  "score": 65,
  "issues": [
    {
      "severity": "high",
      "category": "reproducibility",
      "cell_index": 2,
      "message": "Hardcoded absolute path detected: /home/user/data.csv"
    },
    {
      "severity": "medium",
      "category": "documentation",
      "cell_index": 0,
      "message": "Code cell has no preceding markdown explanation"
    }
  ],
  "suggestions": [
    "Use relative paths or environment variables for file paths",
    "Add markdown cells to explain the purpose of code sections",
    "Consider adding a requirements.txt or environment.yml reference"
  ],
  "summary": "Notebook has reproducibility issues due to hardcoded paths and lacks sufficient documentation."
}
```

---

## Prompts

### System Prompt

```
You are an expert data scientist and notebook reviewer specializing in reproducibility, documentation quality, and best practices.

Your role is to review Jupyter notebooks and identify issues in these categories:

1. REPRODUCIBILITY - Can others run this notebook?
   - Non-linear cell execution (cells run out of order)
   - Hardcoded absolute paths
   - Missing dependency imports
   - Environment-specific code
   - Random seeds not set

2. DOCUMENTATION - Is the notebook well-documented?
   - Missing or inadequate markdown cells
   - No clear narrative structure
   - Undocumented data transformations
   - Missing section headers

3. SECURITY - Are there security concerns?
   - Hardcoded credentials or API keys
   - Sensitive data exposed in outputs
   - Insecure network calls

4. QUALITY - Is the code quality good?
   - Long cells that should be split
   - Unused imports
   - Poor variable naming
   - No error handling

Prioritize issues by severity:
- CRITICAL: Security vulnerabilities, completely broken reproducibility
- HIGH: Major reproducibility or documentation gaps
- MEDIUM: Quality issues, minor documentation gaps
- LOW: Style suggestions, nice-to-haves

Output your review as valid JSON matching the expected schema.
```

### User Prompt Template

```
Review the following Jupyter notebook content for quality, reproducibility, and best practices.

Validation Criteria:
{criteria}

Notebook Content:
```
{content}
```

Provide your review as JSON with this structure:
{
  "valid": boolean (true if score >= 70 and no critical issues),
  "score": integer 0-100,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "reproducibility|documentation|security|quality",
      "cell_index": number or null,
      "message": "description"
    }
  ],
  "suggestions": ["improvement suggestion"],
  "summary": "brief assessment"
}
```

---

## Validation Criteria

1. [x] No hardcoded credentials or API keys - *Security risk*
2. [x] No absolute file paths - *Breaks reproducibility on other machines*
3. [x] Cells should appear in executable order - *Prevents confusion and errors*
4. [x] Markdown cells explain code sections - *Documentation for understanding*
5. [x] Imports are declared at the top or documented - *Dependency clarity*
6. [x] No large outputs stored in cells - *Bloats notebook size*
7. [x] Random seeds set for reproducible results - *ML/statistics reproducibility*
8. [x] Clear section structure with headers - *Navigation and organization*

---

## Workflow Steps (LangGraph Only)

*N/A - This is a simple agent.*

---

## Test Cases

### Fixtures

| Name | Description | Value |
|------|-------------|-------|
| `clean_notebook` | Well-structured notebook | Valid JSON with markdown and code |
| `notebook_with_hardcoded_path` | Contains absolute path | Cell with `/home/user/data.csv` |
| `notebook_with_secret` | Contains API key | Cell with `API_KEY = "sk-..."` |
| `undocumented_notebook` | No markdown cells | Only code cells |

### Test Cases

#### Test: test_clean_notebook_passes

| Field | Value |
|-------|-------|
| **Input** | `{{clean_notebook}}` |
| **Expected** | `valid: true, score >= 80` |
| **Should Raise** | `false` |

#### Test: test_hardcoded_path_detected

| Field | Value |
|-------|-------|
| **Input** | `{{notebook_with_hardcoded_path}}` |
| **Expected** | Issue with category=reproducibility detected |
| **Should Raise** | `false` |

#### Test: test_secret_detected

| Field | Value |
|-------|-------|
| **Input** | `{{notebook_with_secret}}` |
| **Expected** | Issue with severity=critical, category=security |
| **Should Raise** | `false` |

---

## Presets (Optional)

### Preset: strict

| Field | Value |
|-------|-------|
| **Description** | Strict validation for production notebooks |
| **Criteria Override** | All criteria required, score threshold 85 |

### Preset: quick

| Field | Value |
|-------|-------|
| **Description** | Quick check for critical issues only |
| **Criteria Override** | Only security and major reproducibility checks |

### Preset: educational

| Field | Value |
|-------|-------|
| **Description** | Focus on documentation and learning value |
| **Criteria Override** | Emphasize markdown, explanations, narrative |

---

## Open Questions

- [x] Should we parse actual notebook JSON or accept any text? → Accept both
- [x] What score threshold indicates "valid"? → 70 with no critical issues
- [ ] Should we integrate with nbformat for proper parsing? → Future enhancement

---

## Notes

- This agent complements code review by focusing on notebook-specific concerns
- Could be integrated into CI/CD for notebook quality gates
- Future versions could suggest specific markdown templates

---

## Iteration Log

### Version 1 (2024-12-27)

**Changes:** Initial brainstorm from Phase 4 meta-agent validation

**Results:** Ready for YAML spec conversion

**Next:** Generate YAML spec, then use AgentBuilder to generate code
