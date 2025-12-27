# agent-workshop

Batteries-included framework for building automation-focused AI agents with full observability.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **📦 Install as a Package**: Users should install agent-workshop via PyPI (`uv add agent-workshop` or `pip install agent-workshop`), not clone this repository. This repo is for framework development only. See [Quick Start](#quick-start) for the correct workflow.

> **🆕 NEW in v0.2.0**: Pre-built agents with customizable prompts! Install `agent-workshop[agents]` to get production-ready validators and pipelines you can use immediately or customize for your needs.

## Features

🚀 **Dual-Provider Architecture**
- Development: Claude Agent SDK ($20/month flat rate)
- Production: Anthropic API (pay-per-token)
- Automatic switching based on environment

📊 **Full Observability**
- Langfuse integration out of the box
- Automatic tracing of all LLM calls
- Cost tracking and token estimation
- Performance metrics

🕸️ **LangGraph Support**
- Multi-step agent workflows
- State management
- Conditional routing
- Iterative refinement

⚡ **Fast Setup with UV**
- Modern dependency management
- 10-100x faster than pip/poetry
- Reproducible environments

🤖 **Pre-built Agents (NEW in v0.2.0)**
- Production-ready validators and pipelines
- Customizable prompts via env vars, YAML, or code
- Built-in presets for common use cases
- 5-minute setup to first validation

🏗️ **Blueprint System (NEW)**
- Define agents as YAML specifications
- Generate agent code from blueprints
- AgentBuilder meta-agent for automation
- Validated schemas with Pydantic

## Quick Start

### Option 1: Pre-built Agents (Fastest - 5 minutes)

**Perfect for:** Getting started quickly, common validation tasks, learning the framework

```bash
# Install with pre-built agents
uv add 'agent-workshop[agents]'

# Configure environment
cat > .env.development << 'EOF'
AGENT_WORKSHOP_ENV=development
CLAUDE_SDK_ENABLED=true
CLAUDE_MODEL=sonnet

# Langfuse (optional)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
EOF

# Use immediately with built-in preset
python -c "
import asyncio
from agent_workshop.agents.validators import DeliverableValidator
from agent_workshop.agents.validators.presets import get_preset
from agent_workshop import Config

async def main():
    # Use financial report preset
    preset = get_preset('financial_report')
    validator = DeliverableValidator(Config(), **preset)

    result = await validator.run('Your financial report content...')
    print(result)

asyncio.run(main())
"
```

**Available presets:**
- `financial_report` - Financial reports and statements (GAAP, SEC compliance)
- `research_paper` - Academic research papers (methodology, citations)
- `technical_spec` - Technical documentation (API docs, architecture)
- `marketing_content` - Marketing materials (brand voice, SEO, CTAs)
- `legal_document` - Legal documents (contracts, compliance)
- `general` - General-purpose validation

**Customize via YAML config:**
```yaml
# prompts.yaml
deliverable_validator:
  system_prompt: "Custom system prompt for your use case..."
  validation_criteria:
    - "Custom criterion 1"
    - "Custom criterion 2"
  output_format: json
```

```python
from agent_workshop.agents.validators import DeliverableValidator
from agent_workshop import Config

# Automatically loads prompts.yaml if present
validator = DeliverableValidator(Config())
result = await validator.run(content)
```

See [prompts.yaml.example](https://github.com/trentleslie/agent-workshop/blob/main/prompts.yaml.example) for full configuration options.

---

### Option 2: Custom Agents (Full Flexibility)

**Perfect for:** Unique use cases, complex workflows, maximum customization

**Installation:**
```bash
# Install core framework (no pre-built agents)
uv add agent-workshop

# Or install with Claude SDK for development
uv add 'agent-workshop[claude-agent]'
```

**Simple Agent (80% use case):**

```python
from agent_workshop import Agent, Config

class DeliverableValidator(Agent):
    async def run(self, content: str) -> dict:
        messages = [{
            "role": "user",
            "content": f"Validate this deliverable:\n\n{content}"
        }]
        result = await self.complete(messages)
        return {"validation": result}

# Usage
config = Config()  # Auto-detects dev/prod environment
validator = DeliverableValidator(config)
result = await validator.run(report_content)
```

### LangGraph Workflow (15% use case)

```python
from agent_workshop.workflows import LangGraphAgent
from langgraph.graph import StateGraph, END

class ValidationPipeline(LangGraphAgent):
    def build_graph(self):
        workflow = StateGraph(dict)

        workflow.add_node("scan", self.quick_scan)
        workflow.add_node("verify", self.verify)

        workflow.add_edge("scan", "verify")
        workflow.add_edge("verify", END)
        workflow.set_entry_point("scan")

        return workflow.compile()

    async def quick_scan(self, state):
        result = await self.provider.complete([{
            "role": "user",
            "content": f"Quick scan: {state['content']}"
        }])
        return {"scan_result": result, **state}

    async def verify(self, state):
        result = await self.provider.complete([{
            "role": "user",
            "content": f"Verify: {state['scan_result']}"
        }])
        return {"final_result": result}

# Usage (still single invocation!)
pipeline = ValidationPipeline(Config())
result = await pipeline.run({"content": report})
```

---

### Option 3: Blueprint-Generated Agents (NEW)

**Perfect for:** Standardized agent definitions, team collaboration, automated agent creation

```bash
# Install with blueprint support
uv add 'agent-workshop[blueprints]'
```

```python
from agent_workshop.blueprints import generate_agent_from_blueprint
from agent_workshop import Config

# Generate agent code from a blueprint
result = await generate_agent_from_blueprint(
    "blueprints/specs/my_agent.yaml",
    output_path="src/agents/my_agent.py",
)

if result["success"]:
    print(f"Generated: {result['written_path']}")
```

**Blueprint structure:**
```yaml
blueprint:
  name: "my_validator"
  domain: "my_domain"
  type: "simple"  # or "langgraph"

agent:
  class_name: "MyValidator"
  input:
    type: "string"
  output:
    type: "dict"
  prompts:
    system_prompt: "You are an expert validator..."
    user_prompt_template: "Validate: {content}"
  validation_criteria:
    - "Check for quality"
    - "Verify completeness"
```

See [blueprints/README.md](https://github.com/trentleslie/agent-workshop/blob/main/blueprints/README.md) for complete documentation.

---

## Pre-built Agents Reference

### DeliverableValidator

Production-ready validator for documents with customizable prompts and criteria.

**Usage:**
```python
from agent_workshop.agents.validators import DeliverableValidator
from agent_workshop import Config

# Option 1: Use preset
from agent_workshop.agents.validators.presets import get_preset
preset = get_preset("financial_report")
validator = DeliverableValidator(Config(), **preset)

# Option 2: Custom prompts
validator = DeliverableValidator(
    config=Config(),
    system_prompt="You are a compliance validator...",
    validation_criteria=["Criterion 1", "Criterion 2"],
    output_format="json"
)

# Option 3: YAML config (loads prompts.yaml automatically)
validator = DeliverableValidator(Config())

result = await validator.run(document_content)
```

### ValidationPipeline

Multi-step LangGraph pipeline for thorough validation.

**Usage:**
```python
from agent_workshop.agents.pipelines import ValidationPipeline
from agent_workshop import Config

# Default prompts
pipeline = ValidationPipeline(Config())

# Custom prompts
pipeline = ValidationPipeline(
    config=Config(),
    quick_scan_prompt="Custom scan for {content}",
    detailed_verify_prompt="Custom verify for {scan_result} and {content}"
)

result = await pipeline.run({"content": document_content})
```

### CodeReviewer (Software Dev)

Reviews code for security, quality, and best practices.

**Usage:**
```python
from agent_workshop.agents.software_dev import CodeReviewer, get_preset
from agent_workshop import Config

# Use security-focused preset
preset = get_preset("security_focused")
reviewer = CodeReviewer(Config(), **preset)

result = await reviewer.run(code_content)
# Returns: {approved: bool, issues: list, suggestions: list, summary: str}
```

**Available presets:** `general`, `security_focused`, `python_specific`, `javascript_specific`, `quick_scan`

### NotebookValidator (Data Science)

Validates Jupyter notebooks for reproducibility, documentation, and quality.

**Usage:**
```python
from agent_workshop.agents.data_science import NotebookValidator
from agent_workshop import Config

validator = NotebookValidator(Config())

# Pass notebook JSON or cell content
result = await validator.run(notebook_json)
# Returns: {valid: bool, score: int, issues: list, suggestions: list, summary: str}
```

---

## Configuration

### Environment Setup

In your project directory, create `.env.development` or `.env.production`:

```bash
# .env.development
AGENT_WORKSHOP_ENV=development

# Claude Agent SDK (development)
CLAUDE_SDK_ENABLED=true
CLAUDE_MODEL=sonnet  # opus, sonnet, haiku

# Anthropic API (production - optional in dev)
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Langfuse Observability (optional but recommended)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

For a complete example, see the [.env.example](https://github.com/trentleslie/agent-workshop/blob/main/.env.example) in the repository.

### Provider Switching

The framework automatically switches providers based on environment:

- **Development** (`AGENT_WORKSHOP_ENV=development`): Uses Claude Agent SDK
- **Production** (`AGENT_WORKSHOP_ENV=production`): Uses Anthropic API

## Troubleshooting

### Langfuse Authentication Warnings

**Problem**: You see warnings like "Langfuse client initialized without public_key"

**Solution**: This is usually caused by missing environment variables. The framework now automatically loads `.env` files before initializing Langfuse, but you need to ensure:

1. **Create the correct .env file**:
   ```bash
   # For development
   cp .env.example .env.development

   # Edit and add your Langfuse credentials
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```

2. **Set the environment**:
   ```bash
   export AGENT_WORKSHOP_ENV=development
   ```

3. **Test your Langfuse connection**:
   ```python
   from agent_workshop.utils import test_langfuse_connection

   if test_langfuse_connection():
       print("✓ Langfuse configured correctly")
   else:
       print("✗ Check your credentials")
   ```

**If you don't want to use Langfuse**:
```bash
# In your .env file
LANGFUSE_ENABLED=false
```

### Environment Variables Not Loading

**Problem**: Environment variables from `.env` files aren't being picked up

**Cause**: The `.env` file needs to match your environment:
- `AGENT_WORKSHOP_ENV=development` → looks for `.env.development`
- `AGENT_WORKSHOP_ENV=production` → looks for `.env.production`
- Default → looks for `.env`

**Solution**:
```bash
# Option 1: Use environment-specific files (recommended)
export AGENT_WORKSHOP_ENV=development
# Then create .env.development

# Option 2: Use generic .env file
# Just create .env (no export needed)
```

### Provider Configuration Errors

**Problem**: "No valid provider configuration found"

**Solution**: Ensure you have credentials for at least one provider:

**For Development**:
```bash
CLAUDE_SDK_ENABLED=true
CLAUDE_MODEL=sonnet
```

**For Production**:
```bash
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'agent_workshop'`

**Solution**: Install the package (not clone the repo):
```bash
# Correct way (users)
uv add agent-workshop

# Or with pip
pip install agent-workshop

# Incorrect way
git clone https://github.com/trentleslie/agent-workshop.git  # ❌ Only for contributors
```

### Claude Agent SDK Issues

**Problem**: "claude-agent-sdk is not installed"

**Solution**: Install with the optional extra:
```bash
uv add 'agent-workshop[claude-agent]'

# Or with pip
pip install 'agent-workshop[claude-agent]'
```

### Getting Help

If you encounter other issues:
1. Check the [examples](https://github.com/trentleslie/agent-workshop/tree/main/examples) in the repository
2. Review the [documentation](https://github.com/trentleslie/agent-workshop/tree/main/docs)
3. [Open an issue](https://github.com/trentleslie/agent-workshop/issues) with:
   - Your Python version (`python --version`)
   - Your environment configuration (`.env` file, with credentials redacted)
   - Full error message and traceback

## Design Philosophy

### Single-Message Pattern

agent-workshop focuses on **single-message automation** (input → output), NOT streaming conversations.

**Perfect for:**
- ✅ Automated validations
- ✅ Batch processing
- ✅ Scheduled jobs
- ✅ CI/CD pipelines

**Not designed for:**
- ❌ ChatGPT-like interfaces
- ❌ Streaming conversations
- ❌ Real-time chat

### Simple Agent vs LangGraph

| Use Case | Recommended Approach |
|----------|---------------------|
| Single validation check | Simple Agent |
| Multi-step validation pipeline | LangGraph |
| Batch processing | Simple Agent |
| Iterative refinement | LangGraph |
| One-shot classification | Simple Agent |
| Multi-agent collaboration | LangGraph |

## Example Usage

### Complete User Workflow

```bash
# 1. Create your project
mkdir my-research-agents
cd my-research-agents

# 2. Initialize and install
uv init
uv add agent-workshop

# 3. Create .env.development file with your keys

# 4. Create your first agent
cat > agents/validator.py << 'EOF'
from agent_workshop import Agent, Config

class DeliverableValidator(Agent):
    async def run(self, content: str) -> dict:
        messages = [{
            "role": "user",
            "content": f"Validate this deliverable:\n\n{content}"
        }]
        result = await self.complete(messages)
        return {"validation": result}
EOF

# 5. Run your agent
python -c "
import asyncio
from agents.validator import DeliverableValidator
from agent_workshop import Config

async def main():
    validator = DeliverableValidator(Config())
    result = await validator.run('Sample deliverable content')
    print(result)

asyncio.run(main())
"
```

### Reference Examples

For complete examples, see the repository:
- **[Simple Validator](https://github.com/trentleslie/agent-workshop/tree/main/examples/simple_validator)** - Single-message pattern, batch processing, cost tracking
- **[LangGraph Pipeline](https://github.com/trentleslie/agent-workshop/tree/main/examples/langgraph_pipeline)** - Multi-step workflow, state management, conditional routing

**Note**: These examples are for reference only. Build your agents in your own project, not by cloning the framework repository.

## Building Your Own Agents

**Users**: You build agents in **your own project** by installing agent-workshop as a dependency. See the [Complete User Workflow](#complete-user-workflow) above.

**Your project structure should look like**:
```
my-research-agents/              # Your project
├── pyproject.toml               # dependencies = ["agent-workshop"]
├── .env.development
├── .env.production
├── agents/
│   ├── __init__.py
│   ├── deliverable_validator.py
│   └── analysis_checker.py
└── main.py
```

For detailed guidance, see the [Building Agents Guide](https://github.com/trentleslie/agent-workshop/blob/main/docs/building_agents.md).

## Contributing to the Framework

**This section is for contributors who want to improve the agent-workshop framework itself.**

### Development Setup

```bash
# Clone the framework repository (contributors only)
git clone https://github.com/trentleslie/agent-workshop.git
cd agent-workshop

# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Format code
uv run ruff format

# Type check
uv run mypy src/
```

## Cost Comparison

| Environment | Provider | Cost Model | Best For |
|------------|----------|------------|----------|
| Development | Claude Agent SDK | $20/month flat | Unlimited experimentation |
| Production | Anthropic API | $3/1M input tokens<br>$15/1M output tokens | Production workloads |

**Example**: 1,000 validations/day with ~500 tokens each
- **Development**: $20/month (unlimited)
- **Production**: ~$30-50/month (depending on response length)

## Architecture

```
User's Project (your own repo)
├── pyproject.toml
│   └── dependencies: ["agent-workshop"]  ← Install as package
├── agents/
│   ├── deliverable_validator.py
│   └── analysis_checker.py
└── .env.development

        ↓ imports from

agent-workshop Package (from PyPI)
├── Agent (simple agents)
├── LangGraphAgent (workflows)
├── Blueprints                    ← AgentBuilder, code generation
│   ├── Schema validation
│   └── Code generation
├── Domain Agents
│   ├── software_dev (CodeReviewer, PRPipeline)
│   └── data_science (NotebookValidator)
├── Providers (Claude SDK, Anthropic API)
└── Langfuse Integration

        ↓ traces to

Langfuse Dashboard
├── Traces
├── Metrics
├── Costs
└── Performance
```

**Key Point**: Users install agent-workshop via `uv add agent-workshop` or `pip install agent-workshop`, they do NOT clone the repository.

## Documentation

Full documentation available in the repository:
- [Quickstart Guide](https://github.com/trentleslie/agent-workshop/blob/main/docs/quickstart.md)
- [Building Agents](https://github.com/trentleslie/agent-workshop/blob/main/docs/building_agents.md)
- [LangGraph Workflows](https://github.com/trentleslie/agent-workshop/blob/main/docs/langgraph_workflows.md)
- [Langfuse Observability](https://github.com/trentleslie/agent-workshop/blob/main/docs/langfuse_observability.md)
- [User Project Setup](https://github.com/trentleslie/agent-workshop/blob/main/docs/user_project_setup.md)

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](https://github.com/trentleslie/agent-workshop/blob/main/CONTRIBUTING.md) for guidelines.

To contribute to the framework itself, see the [Contributing to the Framework](#contributing-to-the-framework) section above.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with:
- [Claude](https://anthropic.com/) - LLM provider
- [Langfuse](https://langfuse.com/) - Observability platform
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent workflows
- [UV](https://github.com/astral-sh/uv) - Fast Python packaging
