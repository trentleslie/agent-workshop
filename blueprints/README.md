# Agent Blueprints

This directory contains the blueprint system for designing and specifying new agents in agent-workshop.

## Overview

Blueprints are structured specifications that define agents before implementation. They serve as:
1. **Design documents** - Human-readable specs for planning agents
2. **Machine-readable specs** - YAML files that can be used by the AgentBuilder meta-agent
3. **Documentation** - Living docs that stay in sync with implementations

## Directory Structure

```
blueprints/
├── README.md                 # This file
├── schema/
│   └── blueprint_schema.yaml # YAML schema reference
├── templates/
│   └── brainstorm_template.md # Template for brainstorming docs
├── brainstorms/              # Human ideation (template-driven markdown)
│   └── {domain}_{agent_name}.md
├── specs/                    # Structured specifications (YAML)
│   └── {domain}_{agent_name}.yaml
├── code_templates/           # Jinja2 templates for code generation
│   ├── simple_agent.py.jinja2
│   └── langgraph_agent.py.jinja2
└── patterns/                 # Extracted patterns and best practices
    └── README.md
```

## Workflow: Brainstorm → Spec → Implementation

### Step 1: Brainstorm (Markdown)

Start with a brainstorm document using the template in `templates/brainstorm_template.md`.

```bash
cp templates/brainstorm_template.md brainstorms/my_domain_my_agent.md
```

The brainstorm template mirrors the YAML spec structure, making conversion straightforward.

### Step 2: Spec (YAML)

Convert your brainstorm into a structured YAML specification in `specs/`.

See `schema/blueprint_schema.yaml` for the full schema reference.

**Minimal Example:**
```yaml
blueprint:
  version: "1.0"
  name: "my_agent"
  domain: "my_domain"
  description: "What this agent does"
  type: "simple"  # or "langgraph"

agent:
  class_name: "MyAgent"

  input:
    type: "string"
    description: "What the agent receives"

  output:
    type: "dict"
    schema:
      result: "str"
      success: "bool"

  prompts:
    system_prompt: |
      You are an expert at...
    user_prompt_template: |
      Process this: {content}

  validation_criteria:
    - "Criterion 1"
    - "Criterion 2"
```

### Step 3: Implementation

Two paths:

**Manual Implementation:**
Use the spec as a guide to implement the agent in `src/agent_workshop/agents/{domain}/`.

**Auto-Generation (Phase 3+):**
Use the AgentBuilder meta-agent:
```python
from agent_workshop.blueprints import AgentBuilder
from agent_workshop import Config

builder = AgentBuilder(Config())
result = await builder.run({
    "blueprint_path": "blueprints/specs/my_domain_my_agent.yaml"
})
```

## Blueprint Types

### Simple Agent (`type: "simple"`)

For single-message automation (80% use case):
- Input → LLM → Output
- No complex state management
- Perfect for validators, analyzers, classifiers

### LangGraph Workflow (`type: "langgraph"`)

For multi-step workflows (15% use case):
- Multiple LLM calls with state threading
- Conditional routing between steps
- Perfect for pipelines, multi-stage validation

## Validation

Blueprints are validated using Pydantic models in `src/agent_workshop/blueprints/schema.py`.

```python
from agent_workshop.blueprints.schema import AgentBlueprint
import yaml

with open("specs/my_agent.yaml") as f:
    data = yaml.safe_load(f)
    blueprint = AgentBlueprint(**data)  # Validates against schema
```

## Naming Conventions

- **Files**: `{domain}_{agent_name}.{md|yaml}` (lowercase, underscores)
- **Classes**: PascalCase derived from agent name
- **Domains**: Group related agents (e.g., `software_dev`, `data_science`, `bioinformatics`)

## Current Blueprints

| Domain | Agent | Type | Status |
|--------|-------|------|--------|
| software_dev | code_reviewer | simple | Complete |
| software_dev | pr_pipeline | langgraph | Complete |
| data_science | notebook_validator | simple | Planned (Phase 4) |

## Code Templates

Jinja2 templates for code generation are in `code_templates/`:
- `simple_agent.py.jinja2` - Template for Simple Agent subclasses
- `langgraph_agent.py.jinja2` - Template for LangGraph workflow agents

## Pattern Library

See `patterns/README.md` for documented patterns:
- Simple Agent pattern
- LangGraph Pipeline pattern
- Preset system
- JSON output parsing
- Configuration priority
- Error handling
