# Agent Brainstorm: [Agent Name]

> **Instructions**: Fill out each section below. This template mirrors the YAML spec structure for easy conversion. Delete instructional text (in italics) before finalizing.

---

## Metadata

| Field | Value |
|-------|-------|
| **Name** | `agent_name` |
| **Domain** | `domain_name` |
| **Type** | `simple` or `langgraph` |
| **Author** | Your name |
| **Date** | YYYY-MM-DD |
| **Status** | Draft / In Review / Ready for Spec |

---

## Problem Statement

*What problem does this agent solve? Be specific about the pain point.*

[Describe the problem here]

---

## Description

*One paragraph description of what this agent does.*

[Agent description here]

---

## Input Specification

| Field | Value |
|-------|-------|
| **Type** | `string` / `dict` / `list` |
| **Description** | What the agent receives |

### Input Validation Rules

*What constraints apply to the input?*

- [ ] Rule 1
- [ ] Rule 2

### Example Input

```
[Example input here]
```

---

## Output Specification

| Field | Value |
|-------|-------|
| **Type** | `dict` / `string` / `list` |

### Output Schema

*Define the structure of the output.*

| Field | Type | Description |
|-------|------|-------------|
| `field_name` | `type` | Description |
| | | |

### Example Output

```json
{
  "field": "value"
}
```

---

## Prompts

### System Prompt

*What role/expertise should the LLM embody? What context does it need?*

```
[Draft system prompt here]
```

### User Prompt Template

*Template with {placeholders} for dynamic content.*

```
[Draft user prompt template here]

Available placeholders:
- {content} - The input content
- {criteria} - Validation criteria list
- {output_format} - Expected output format
```

---

## Validation Criteria

*What specific things should the agent check/validate?*

1. [ ] Criterion 1 - *Why important?*
2. [ ] Criterion 2 - *Why important?*
3. [ ] Criterion 3 - *Why important?*
4. [ ] Criterion 4 - *Why important?*
5. [ ] Criterion 5 - *Why important?*

---

## Workflow Steps (LangGraph Only)

*Skip this section for simple agents.*

### Step 1: [Step Name]

| Field | Value |
|-------|-------|
| **Purpose** | What this step accomplishes |
| **Input** | What state fields it reads |
| **Output** | What state fields it writes |

**Prompt:**
```
[Step prompt here]
```

### Step 2: [Step Name]

| Field | Value |
|-------|-------|
| **Purpose** | What this step accomplishes |
| **Input** | What state fields it reads |
| **Output** | What state fields it writes |

**Prompt:**
```
[Step prompt here]
```

### Workflow Edges

```
[entry] → step1 → step2 → [END]
```

*Or for conditional routing:*
```
[entry] → step1 → {condition} → step2a (if true)
                             → step2b (if false)
```

---

## Test Cases

### Fixtures

| Name | Description | Value |
|------|-------------|-------|
| `fixture_name` | Description | `value or reference` |

### Test Cases

#### Test: [test_name]

| Field | Value |
|-------|-------|
| **Input** | `{{fixture_name}}` or inline |
| **Expected** | Expected output or behavior |
| **Should Raise** | `true` / `false` |

---

## Presets (Optional)

*Should this agent have presets for common use cases?*

### Preset: [preset_name]

| Field | Value |
|-------|-------|
| **Description** | What this preset is for |
| **System Prompt Override** | If different from default |
| **Criteria Override** | If different from default |

---

## Open Questions

*Unresolved decisions or things to research.*

- [ ] Question 1
- [ ] Question 2

---

## Notes

*Additional thoughts, references, or context.*

- Note 1
- Note 2

---

## Iteration Log

*Track prompt iterations and what worked/didn't.*

### Version 1 (YYYY-MM-DD)

**Changes:** Initial draft

**Results:** [How it performed]

**Next:** [What to try next]
