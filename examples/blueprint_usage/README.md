# Blueprint Usage Examples

This directory demonstrates how to use the AgentBuilder system to generate agent code from YAML blueprints.

## Overview

The blueprint system allows you to:
1. Define agents as YAML specifications
2. Validate blueprints for correctness
3. Generate Python code from blueprints
4. Write generated code to files

## Quick Start

```bash
# Run with default code_reviewer blueprint
uv run python examples/blueprint_usage/generate_agent.py

# Run with the example blueprint
uv run python examples/blueprint_usage/generate_agent.py examples/blueprint_usage/example_blueprint.yaml

# Generate and write to a file
uv run python examples/blueprint_usage/generate_agent.py blueprints/specs/software_dev_code_reviewer.yaml --output my_agent.py
```

## Files

- `generate_agent.py` - Main example script demonstrating all AgentBuilder features
- `example_blueprint.yaml` - Simple example blueprint for testing
- `.env.example` - Environment configuration template

## Examples in generate_agent.py

The script demonstrates five different approaches:

### 1. Load and Validate Blueprint
```python
from agent_workshop.blueprints import load_blueprint, validate_blueprint

blueprint = load_blueprint("blueprints/specs/my_agent.yaml")
validation = validate_blueprint(blueprint)
print(f"Valid: {validation.valid}")
```

### 2. Generate Code with Inline Templates
```python
from agent_workshop.blueprints import InlineCodeGenerator, load_blueprint

blueprint = load_blueprint("blueprints/specs/my_agent.yaml")
generator = InlineCodeGenerator()
code = generator.generate(blueprint)
```

### 3. Generate Code with Jinja2 Templates
```python
from agent_workshop.blueprints import CodeGenerator, load_blueprint

blueprint = load_blueprint("blueprints/specs/my_agent.yaml")
generator = CodeGenerator()  # Uses blueprints/code_templates/
code = generator.generate(blueprint)
```

### 4. Use AgentBuilder Meta-Agent
```python
from agent_workshop import Config
from agent_workshop.blueprints import AgentBuilder

builder = AgentBuilder(Config())
result = await builder.run({
    "blueprint_path": "blueprints/specs/my_agent.yaml",
    "output_path": "src/agents/my_agent.py",  # optional
    "overwrite": True,
})

if result["success"]:
    print(result["code"])
```

### 5. Use Convenience Function
```python
from agent_workshop.blueprints import generate_agent_from_blueprint

result = await generate_agent_from_blueprint(
    "blueprints/specs/my_agent.yaml",
    output_path="src/agents/my_agent.py",
    overwrite=True,
)
```

## Blueprint Structure

See `example_blueprint.yaml` for a minimal blueprint example. For complete documentation, see:
- `blueprints/README.md` - Blueprint system documentation
- `blueprints/schema/blueprint_schema.yaml` - Full schema reference
- `blueprints/templates/brainstorm_template.md` - Template for designing new agents

## Available Blueprints

Production blueprints are in `blueprints/specs/`:
- `software_dev_code_reviewer.yaml` - Simple agent for code review
- `software_dev_pr_pipeline.yaml` - LangGraph workflow for PR review

## Code Templates

The generator supports two modes:
1. **Jinja2 Templates** (default): Uses templates in `blueprints/code_templates/`
2. **Inline Templates**: Embedded templates, no external dependencies

Set `use_inline_generator=True` to use inline templates.
