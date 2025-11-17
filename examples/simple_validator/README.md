# Simple Validator Example

This example demonstrates the basic usage of agent-workshop with a simple deliverable validator agent.

## Pattern: Single-Message Agent

Input → Output (no ongoing conversation)

Perfect for:
- Automated validations
- Batch processing
- Scheduled jobs
- CI/CD pipelines

## Files

- `validator.py` - Simple validation agent implementation
- `.env.example` - Environment configuration template

## Setup

1. Install agent-workshop:
```bash
uv add agent-workshop
```

2. Configure environment:
```bash
cp .env.example .env.development
# Edit .env.development with your API keys
```

3. Run the example:
```bash
python validator.py
```

## What It Does

The `DeliverableValidator` agent:
1. Takes a deliverable (report, analysis, etc.) as input
2. Sends it to the LLM for validation
3. Returns a structured validation result
4. All interactions are automatically traced in Langfuse

## Key Features

- **Automatic provider switching** - Uses Claude SDK in dev, Anthropic API in prod
- **Full observability** - Every validation is traced in Langfuse
- **Cost tracking** - See estimated and actual costs
- **Simple to extend** - Just override the `run()` method

## Usage in Your Projects

```python
from agent_workshop import Agent, Config

class MyValidator(Agent):
    async def run(self, content: str) -> dict:
        messages = [{
            "role": "user",
            "content": f"Validate this content:\\n\\n{content}"
        }]
        result = await self.complete(messages)
        return {"validation": result, "status": "completed"}

# Use in automation
config = Config()
validator = MyValidator(config)

for item in get_items_to_validate():
    result = await validator.run(item.content)
    save_result(item.id, result)
```

## Next Steps

- Try the [LangGraph Pipeline Example](../langgraph_pipeline/) for multi-step workflows
- Read the [Building Agents Guide](../../docs/building_agents.md)
- Learn about [Langfuse Observability](../../docs/langfuse_observability.md)
