# agent-workshop

Cost-effective framework for building automation-focused AI agents with full observability.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **📦 Install as a Package**: Users should install agent-workshop via PyPI (`uv add agent-workshop` or `pip install agent-workshop`), not clone this repository. This repo is for framework development only. See [Quick Start](#quick-start) for the correct workflow.

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

## Quick Start

**Important**: Users should **install agent-workshop as a package**, not clone this repository. This repo is for framework development only.

### Installation

```bash
# Create your project
mkdir my-research-agents
cd my-research-agents

# Initialize with UV
uv init

# Install agent-workshop from PyPI
uv add agent-workshop

# Or with pip
pip install agent-workshop
```

### Simple Agent (80% use case)

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
