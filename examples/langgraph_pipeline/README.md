# LangGraph Pipeline Example

This example demonstrates using LangGraph for multi-step agent workflows with agent-workshop.

## Pattern: Multi-Step Orchestration

One input → Orchestrated steps → One output

Still single-message pattern externally! Multiple LLM calls happen internally, but from the outside it's one invocation with one result.

## Files

- `pipeline.py` - Multi-step validation pipeline using LangGraph
- `.env.example` - Environment configuration template

## What Is This For?

Use LangGraph workflows when you need:
- Multiple validation steps (scan → analyze → verify)
- Iterative refinement
- Conditional logic (if X then Y, else Z)
- Multi-agent collaboration
- Complex decision trees

## Setup

1. Install agent-workshop with LangGraph:
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
python pipeline.py
```

## What It Does

The `ValidationPipeline` workflow:
1. **Quick Scan** - Fast check for obvious issues
2. **Deep Analysis** - Thorough analysis based on scan results
3. **Final Verification** - Verify findings and generate report

Each step is a separate LLM call, but they're orchestrated together into a single workflow.

## Key Features

- **State management** - LangGraph tracks state between steps
- **Automatic tracing** - Each step is traced in Langfuse
- **Cost tracking** - See cost breakdown per step
- **Reusable patterns** - Build once, use everywhere

## Workflow Structure

```python
from agent_workshop.workflows import LangGraphAgent
from langgraph.graph import StateGraph, END

class MyPipeline(LangGraphAgent):
    def build_graph(self):
        workflow = StateGraph(dict)

        # Define steps
        workflow.add_node("step1", self.step1)
        workflow.add_node("step2", self.step2)
        workflow.add_node("step3", self.step3)

        # Define flow
        workflow.add_edge("step1", "step2")
        workflow.add_edge("step2", "step3")
        workflow.add_edge("step3", END)

        workflow.set_entry_point("step1")

        return workflow.compile()

    async def step1(self, state):
        result = await self.provider.complete([{
            "role": "user",
            "content": f"Process: {state['input']}"
        }])
        return {"step1_result": result, **state}
```

## When to Use Simple Agent vs LangGraph

| Use Case | Agent Type |
|----------|-----------|
| Single validation check | Simple Agent |
| Multi-step validation pipeline | LangGraph |
| Batch processing | Simple Agent |
| Iterative refinement workflow | LangGraph |
| One-shot classification | Simple Agent |
| Multi-agent collaboration | LangGraph |

## Advanced Features

### Conditional Routing

```python
def should_analyze_deeper(state):
    return "issues" in state.get("scan_result", "")

workflow.add_conditional_edges(
    "scan",
    should_analyze_deeper,
    {
        True: "deep_analysis",
        False: "final_verification"
    }
)
```

### Checkpointing

```python
# Save workflow state for resumption
config = Config()
config.langgraph_checkpointer = "postgres"
config.langgraph_postgres_url = "postgresql://..."

pipeline = ValidationPipeline(config)
```

## Next Steps

- Read the [LangGraph Integration Guide](../../docs/langgraph_workflows.md)
- Learn about [Langfuse Observability](../../docs/langfuse_observability.md)
- Try building your own multi-step workflow
