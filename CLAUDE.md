# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**agent-workshop** is a Python framework for building automation-focused AI agents with full observability. This repository is for framework development - end users install it via PyPI (`uv add agent-workshop` or `pip install agent-workshop`).

**Core Design**: Single-message pattern (input → output) for automation, NOT streaming conversations or chat interfaces.

## Architecture

### Dual-Provider System
The framework automatically switches LLM providers based on environment:
- **Development** (`AGENT_WORKSHOP_ENV=development`): Claude Agent SDK ($20/month flat rate)
- **Production** (`AGENT_WORKSHOP_ENV=production`): Anthropic API (pay-per-token)

Provider selection logic is in `src/agent_workshop/config.py` via `get_provider_type()` and `get_provider_config()`.

### Core Components

1. **Agent Base Classes**
   - `src/agent_workshop/agent.py`: Simple single-message agents (80% use case)
   - `src/agent_workshop/workflows/langgraph_agent.py`: Multi-step workflows via LangGraph (15% use case)
   - Both maintain single-message pattern externally; LangGraph has internal multi-step orchestration

2. **Pre-built Agents** (`src/agent_workshop/agents/`)
   - `validators/deliverable.py`: Production-ready DeliverableValidator
   - `validators/presets.py`: Industry presets (financial_report, research_paper, etc.)
   - `pipelines/validation.py`: Multi-step ValidationPipeline using LangGraph
   - Customizable via YAML config (`prompts.yaml`) or constructor args

3. **Configuration System** (`src/agent_workshop/config.py`)
   - Pydantic Settings-based with environment variable support
   - Environment-specific files: `.env.development`, `.env.production`, `.env.staging`
   - Cached via `@lru_cache` in `get_config()`

4. **Provider Abstraction** (`src/agent_workshop/providers/`)
   - `base.py`: LLMProvider abstract base class
   - `claude_agent_sdk.py`: Claude Agent SDK implementation (development)
   - `anthropic_api.py`: Anthropic API implementation (production)
   - All providers support Langfuse tracing integration

5. **Observability** (`src/agent_workshop/utils/langfuse_helpers.py`)
   - Automatic Langfuse tracing via `@observe` decorator
   - Token counting and cost estimation built-in
   - All agent completions are automatically traced

6. **Blueprint System** (`src/agent_workshop/blueprints/`)
   - `schema.py`: Pydantic models for blueprint validation
   - `validators.py`: Blueprint and code validation utilities
   - `code_generator.py`: Jinja2 and inline code generation
   - `agent_builder.py`: AgentBuilder meta-agent (LangGraph workflow)

7. **Domain Agents** (`src/agent_workshop/agents/`)
   - `software_dev/`: CodeReviewer, PRPipeline, presets for code review
   - `data_science/`: NotebookValidator (generated from blueprint)

## Development Commands

### Setup
```bash
# Install dependencies (development mode)
uv sync --all-extras
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_langfuse_integration.py

# Run tests matching a pattern
uv run pytest -k "test_langfuse"

# Run with verbose output
uv run pytest -v
```

### Code Quality
```bash
# Format code with Ruff
uv run ruff format

# Lint code
uv run ruff check

# Lint and auto-fix
uv run ruff check --fix

# Type checking
uv run mypy src/
```

### Environment Configuration
The framework uses environment-specific `.env` files:
- `.env.development`: Development settings (Claude SDK)
- `.env.production`: Production settings (Anthropic API)
- See `.env.example` for all available configuration options

## Code Patterns

### Creating New Agents

**Simple Agent** (for single-step validation):
```python
from agent_workshop import Agent, Config

class MyAgent(Agent):
    async def run(self, input: str) -> dict:
        messages = [{"role": "user", "content": input}]
        result = await self.complete(messages)
        return {"result": result}
```

**LangGraph Workflow** (for multi-step processes):
```python
from agent_workshop.workflows import LangGraphAgent
from langgraph.graph import StateGraph, END

class MyWorkflow(LangGraphAgent):
    def build_graph(self):
        workflow = StateGraph(dict)
        workflow.add_node("step1", self.step1)
        workflow.add_node("step2", self.step2)
        workflow.add_edge("step1", "step2")
        workflow.add_edge("step2", END)
        workflow.set_entry_point("step1")
        return workflow.compile()

    async def step1(self, state):
        result = await self.provider.complete([...])
        return {"step1_result": result, **state}
```

### Using Blueprints

**Generate agent from blueprint:**
```python
from agent_workshop.blueprints import generate_agent_from_blueprint

result = await generate_agent_from_blueprint(
    "blueprints/specs/my_agent.yaml",
    output_path="src/agents/my_agent.py",
)

if result["success"]:
    print(f"Generated: {result['written_path']}")
```

**Blueprint YAML structure:**
```yaml
blueprint:
  name: "my_agent"
  domain: "my_domain"
  type: "simple"  # or "langgraph"

agent:
  class_name: "MyAgent"
  input:
    type: "string"
  output:
    type: "dict"
  prompts:
    system_prompt: "..."
    user_prompt_template: "..."
  validation_criteria:
    - "Criterion 1"
    - "Criterion 2"
```

### Provider Management

- **Never instantiate providers directly** in agent subclasses; use `self.provider` from base class
- Providers are created automatically in `_create_provider()` based on config
- All providers must implement `complete()`, `estimate_tokens()`, and `estimate_cost()`

### Adding New Features

When adding features to the framework:
1. **Update both base classes** if the feature applies to simple agents and workflows
2. **Maintain backward compatibility** - users depend on stable APIs
3. **Add Langfuse tracing** for observability with `@observe` decorator
4. **Update type hints** - this is a typed codebase (Python 3.10+)
5. **Update docstrings** - comprehensive documentation is critical for framework users

## Important Constraints

1. **This is NOT a chat framework**
   - No streaming support
   - No conversation history management
   - Single input → single output only

2. **Users install as package**
   - Don't assume users have access to framework internals
   - Public API is what's exported in `src/agent_workshop/__init__.py`
   - Examples are for reference, not for direct execution

3. **Provider abstraction must remain clean**
   - New providers must implement full LLMProvider interface
   - Cost estimation must be accurate (used for production budgeting)
   - Langfuse integration must work with all providers

## Dependencies

Core dependencies (see `pyproject.toml`):
- `langfuse>=3.0.0`: Observability and tracing
- `anthropic>=0.40.0`: Anthropic API client
- `langgraph>=0.2.0`: Workflow orchestration
- `tiktoken>=0.7.0`: Token counting
- `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`: Configuration and validation
- `python-dotenv>=1.0.0`: Environment management

Optional extras:
- `[claude-agent]`: Claude Agent SDK for development
- `[validators]`: Pre-built validators with YAML config support
- `[pipelines]`: Pre-built LangGraph pipelines
- `[agents]`: All pre-built agents (validators + pipelines)
- `[blueprints]`: Blueprint system with code generation (includes Jinja2)
- `[dev]`: Development tools (pytest, ruff, mypy)

Dev tools: `pytest`, `pytest-asyncio`, `ruff`, `mypy`

## Environment Variables

Key environment variables (see `.env.example` for complete list):
- `AGENT_WORKSHOP_ENV`: Environment selector (development/staging/production)
- `CLAUDE_SDK_ENABLED`: Enable Claude Agent SDK
- `ANTHROPIC_API_KEY`: Anthropic API key for production
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`: Langfuse credentials
- `DEBUG`: Enable debug logging

## File Structure Note

- `src/agent_workshop/`: Framework source code
- `src/agent_workshop/blueprints/`: Blueprint system (schema, validation, code generation)
- `src/agent_workshop/agents/software_dev/`: Code review agents (CodeReviewer, PRPipeline)
- `src/agent_workshop/agents/data_science/`: Data science agents (NotebookValidator)
- `blueprints/`: Blueprint definitions (specs, templates, brainstorms)
- `examples/`: Reference implementations (simple_validator, langgraph_pipeline, blueprint_usage)
- `tests/`: Test suite with fixtures
- `docs/`: Documentation (currently empty but referenced in README)
