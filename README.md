# agent-workshop

Agentic PR automation framework with human-gated checkpoints and full observability.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/agent-workshop.svg)](https://pypi.org/project/agent-workshop/)

> **📦 Install as a Package**: Users should install agent-workshop via PyPI (`uv add agent-workshop` or `pip install agent-workshop`), not clone this repository. This repo is for framework development only.

> **🆕 v0.4.0**: Triangle Workflow for automated PR generation from GitHub issues with human-gated review checkpoints.

## Features

**Triangle Workflow** (Primary Feature)
- Issue → PR → Review → Merge automation
- Human-gated checkpoints for review control
- Greptile AI code review integration
- Per-project configuration via `.triangle.toml`

📊 **Full Observability**
- Langfuse integration out of the box
- Automatic tracing of all LLM calls
- Cost tracking and token estimation
- Workflow metrics and persistence

🚀 **Dual-Provider Architecture**
- Development: Claude Agent SDK ($20/month flat rate)
- Production: Anthropic API (pay-per-token)
- Automatic switching based on environment

🕸️ **LangGraph Workflows**
- Multi-step agent orchestration
- State management with SQLite persistence
- Conditional routing and retry logic
- Git worktree support for parallel workflows

## Quick Start

### Triangle Workflow (Primary Use Case)

Automate GitHub issue → PR generation with human-gated review checkpoints.

```bash
# Install agent-workshop
pip install agent-workshop
# or: uv add agent-workshop

# In your repository, start a workflow for an issue
triangle start --issue 42 --repo owner/repo

# Check workflow status
triangle status

# After human review, approve to continue
triangle approve owner-repo-issue-42
```

**What Triangle Does:**
1. **Parse Issue** - Fetches GitHub issue, extracts requirements via LLM
2. **Setup Worktree** - Creates isolated git worktree for development
3. **Generate Code** - Uses LLM to implement the requirements
4. **Verify Code** - Runs tiered verification (lint, type check, tests)
5. **Create PR** - Pushes branch and creates draft PR
6. **CHECKPOINT** - Pauses for human + Greptile AI review
7. **Process Comments** - After approval, auto-fixes review feedback
8. **Merge** - Completes the workflow

### Configuration

Create `.triangle.toml` in your project root:

```toml
[verification]
# Commands for code verification (optional)
check_command = "./scripts/check.sh"
fix_command = "./scripts/fix.sh"
fallback_tools = ["ruff", "black", "pyright"]

[style]
# Code style enforcement
formatter = "black"
linter = "ruff"
type_checker = "pyright"
guidelines_file = "CONTRIBUTING.md"  # Injected into prompts
line_length = 88

[commits]
# Commit message conventions
convention = "conventional"
link_pattern = "Closes #{issue}"
```

**Verification Scripts (optional):**
- `check_command` - Script to run all checks (e.g., lint, type check, tests)
- `fix_command` - Script to auto-fix formatting and linting issues
- If scripts don't exist, Triangle falls back to running `fallback_tools` directly

**Auto-detection:** If no `.triangle.toml` exists, Triangle auto-detects project type (Python/Node/Go) and uses sensible defaults.

---

### Custom Agents (Alternative Use Case)

For building standalone agents without the Triangle workflow:

```bash
# Install core framework
uv add agent-workshop

# Or with Claude SDK for development
uv add 'agent-workshop[claude-agent]'
```

**Simple Agent:**

```python
from agent_workshop import Agent, Config

class MyValidator(Agent):
    async def run(self, content: str) -> dict:
        messages = [{
            "role": "user",
            "content": f"Validate this:\n\n{content}"
        }]
        result = await self.complete(messages)
        return {"validation": result}

# Usage
config = Config()  # Auto-detects dev/prod environment
validator = MyValidator(config)
result = await validator.run(content)
```

**LangGraph Workflow:**

```python
from agent_workshop.workflows import LangGraphAgent
from langgraph.graph import StateGraph, END

class MyPipeline(LangGraphAgent):
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

pipeline = MyPipeline(Config())
result = await pipeline.run({"content": data})
```

---

## Other Features

### Pre-built Validators

Production-ready validators for common use cases (install with `uv add 'agent-workshop[agents]'`).

**DeliverableValidator** - Document validation with presets:
```python
from agent_workshop.agents.validators import DeliverableValidator
from agent_workshop.agents.validators.presets import get_preset

preset = get_preset("financial_report")  # or: research_paper, technical_spec, legal_document
validator = DeliverableValidator(Config(), **preset)
result = await validator.run(document_content)
```

**CodeReviewer** - Code review with security focus:
```python
from agent_workshop.agents.software_dev import CodeReviewer, get_preset

reviewer = CodeReviewer(Config(), **get_preset("security_focused"))
result = await reviewer.run(code_content)
```

**NotebookValidator** - Jupyter notebook quality checks:
```python
from agent_workshop.agents.data_science import NotebookValidator

validator = NotebookValidator(Config())
result = await validator.run(notebook_json)
```

### Blueprint System

Define agents as YAML specifications and generate code (install with `uv add 'agent-workshop[blueprints]'`).

```python
from agent_workshop.blueprints import generate_agent_from_blueprint

result = await generate_agent_from_blueprint(
    "blueprints/specs/my_agent.yaml",
    output_path="src/agents/my_agent.py",
)
```

See [blueprints/README.md](https://github.com/trentleslie/agent-workshop/blob/main/blueprints/README.md) for details.

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

### Triangle Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Triangle Workflow                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GitHub Issue                                                        │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐   ┌─────┐  │
│  │  Parse  │──▶│  Setup   │──▶│ Generate │──▶│ Verify │──▶│ PR  │  │
│  │  Issue  │   │ Worktree │   │   Code   │   │  Code  │   │     │  │
│  └─────────┘   └──────────┘   └──────────┘   └────────┘   └──┬──┘  │
│                                     ▲            │            │     │
│                                     │ retry      │ fail       │     │
│                                     └────────────┘            ▼     │
│                                                        ╔═══════════╗│
│  Human + Greptile Review ◀─────────────────────────── ║CHECKPOINT ║│
│       │                                                ╚═══════════╝│
│       ▼                                                              │
│  `triangle approve`                                                  │
│       │                                                              │
│       ▼                                                              │
│  ┌───────────────┐   ┌───────────────┐   ┌─────────┐               │
│  │ PRComment     │──▶│  Apply Fixes  │──▶│  Merge  │               │
│  │ Processor     │   │               │   │         │               │
│  └───────────────┘   └───────────────┘   └─────────┘               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Components

```
agent-workshop Package
├── cli/triangle.py              ← Triangle CLI (start, approve, status)
├── agents/software_dev/
│   ├── issue_to_pr.py           ← Issue-to-PR workflow (LangGraph)
│   ├── pr_comment_processor.py  ← Review comment processing
│   ├── triangle_orchestrator.py ← Full cycle orchestration
│   └── config/triangle_config.py← Project configuration
├── utils/
│   ├── persistence.py           ← SQLite checkpoint storage
│   └── git_operations.py        ← Worktree management
├── Agent (simple agents)
├── LangGraphAgent (workflows)
├── Providers (Claude SDK, Anthropic API)
└── Langfuse Integration

        ↓ traces to

Langfuse Dashboard
├── Traces (LLM calls, workflow steps)
├── Metrics (tokens, latency, costs)
└── Workflow history
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
