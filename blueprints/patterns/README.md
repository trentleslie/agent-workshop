# Agent Patterns Library

This document captures common patterns extracted from building agents with agent-workshop. Use these patterns when designing new agents.

## Overview

| Pattern | When to Use | Example Agent |
|---------|-------------|---------------|
| Simple Agent | Single-step analysis, 80% use case | CodeReviewer |
| LangGraph Pipeline | Multi-step with state threading | PRPipeline |
| Preset System | Multiple configurations for same agent | CodeReviewer presets |
| JSON Output | Machine-readable results | Both agents |

---

## Pattern 1: Simple Agent (Single-Message)

**Use when:** Task can be completed in a single LLM call.

### Structure

```python
class MyAgent(Agent):
    DEFAULT_SYSTEM_PROMPT = "..."
    DEFAULT_CRITERIA = [...]
    DEFAULT_USER_PROMPT_TEMPLATE = "..."

    def __init__(self, config, system_prompt=None, ...):
        super().__init__(config)
        self.system_prompt = system_prompt or ... or DEFAULT

    async def run(self, content: str) -> dict:
        # 1. Format prompt
        user_prompt = self.user_prompt_template.format(...)

        # 2. Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 3. Call LLM
        result = await self.complete(messages)

        # 4. Parse and return
        return self._parse_response(result)
```

### Key Characteristics

- Inherits from `Agent` base class
- Single `run()` method that calls `self.complete()` once
- Configuration priority: constructor > YAML > env vars > defaults
- Returns structured dict (usually JSON-parsed)

### When NOT to Use

- Task requires multiple analysis steps
- Later steps depend on earlier results
- Need conditional routing based on intermediate results

---

## Pattern 2: LangGraph Pipeline (Multi-Step)

**Use when:** Task benefits from multiple sequential LLM calls with state.

### Structure

```python
class MyPipeline(LangGraphAgent):
    DEFAULT_STEP1_PROMPT = "..."
    DEFAULT_STEP2_PROMPT = "..."

    def __init__(self, config, step1_prompt=None, ...):
        self.step1_prompt = step1_prompt or ... or DEFAULT
        super().__init__(config)  # Calls build_graph()

    def build_graph(self):
        workflow = StateGraph(MyState)

        workflow.add_node("step1", self.step1)
        workflow.add_node("step2", self.step2)

        workflow.add_edge("step1", "step2")
        workflow.add_edge("step2", END)

        workflow.set_entry_point("step1")
        return workflow.compile()

    async def step1(self, state: MyState) -> MyState:
        prompt = self.step1_prompt.format(**state)
        result = await self.provider.complete([...])
        return {**state, "step1_result": result}

    async def step2(self, state: MyState) -> MyState:
        # Has access to step1_result
        prompt = self.step2_prompt.format(**state)
        result = await self.provider.complete([...])
        return {**state, "step2_result": result}
```

### Key Characteristics

- Inherits from `LangGraphAgent` base class
- `build_graph()` defines workflow structure
- Each step is an async method receiving/returning state
- Steps access previous results via state dict
- Uses `self.provider.complete()` (not `self.complete()`)

### State Design

```python
class MyState(TypedDict):
    # Input fields
    content: str
    metadata: str | None

    # Intermediate results
    step1_result: dict | None
    step2_result: dict | None

    # Final output
    final_result: dict | None
```

### When to Use

- Security scan → Quality review → Summary (like PRPipeline)
- Parse → Validate → Transform
- Classify → Route → Process
- Extract → Verify → Summarize

---

## Pattern 3: Preset System

**Use when:** Same agent logic with different configurations for different use cases.

### Structure

```python
# presets.py
PRESETS = {
    "general": {
        "system_prompt": "...",
        "validation_criteria": [...],
    },
    "security_focused": {
        "system_prompt": "Security-focused...",
        "validation_criteria": [...],
    },
}

def get_preset(name: str) -> dict:
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    return PRESETS[name].copy()
```

### Usage

```python
from agent_workshop.agents.software_dev import CodeReviewer, get_preset

# Use preset
preset = get_preset("security_focused")
reviewer = CodeReviewer(Config(), **preset)

# Override specific fields
preset = get_preset("general")
preset["validation_criteria"].append("Custom criterion")
reviewer = CodeReviewer(Config(), **preset)
```

### Design Guidelines

- Keep presets focused on specific use cases
- Include `description` field for discoverability
- Allow partial overrides (don't make all-or-nothing)
- Document when to use each preset

---

## Pattern 4: JSON Output Parsing

**Use when:** Need machine-readable structured output.

### Prompt Design

```python
USER_PROMPT = """
...analysis instructions...

Return JSON:
{
  "field1": type,
  "field2": type,
  ...
}
"""
```

### Parser Implementation

```python
def _parse_json_response(self, response: str) -> dict:
    text = response.strip()

    # Handle markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Parse failed", "raw": text[:500]}
```

### Guidelines

- Always handle markdown code blocks (LLMs often wrap JSON)
- Provide fallback for parse failures
- Include `raw_response` in output for debugging
- Use explicit JSON schema in prompt for consistency

---

## Pattern 5: Configuration Priority

**Standard priority order (highest to lowest):**

1. Constructor parameters
2. YAML config file (`prompts.yaml`)
3. Environment variables
4. Preset configuration
5. Built-in defaults

### Implementation

```python
def __init__(self, config, system_prompt=None, preset=None, config_file=None):
    # Load from preset/file first
    prompt_config = self._load_prompt_config(config_file, preset)

    # Apply with priority
    self.system_prompt = (
        system_prompt                           # 1. Constructor
        or prompt_config.get("system_prompt")   # 2. YAML / 4. Preset
        or os.getenv("AGENT_SYSTEM_PROMPT")     # 3. Env var
        or self.DEFAULT_SYSTEM_PROMPT           # 5. Default
    )
```

---

## Pattern 6: Error Handling

### Input Validation

```python
async def run(self, content: str) -> dict:
    if not content or not content.strip():
        return {
            "error": "Empty input",
            "timestamp": datetime.now().isoformat(),
        }
    # ... proceed with analysis
```

### LLM Response Handling

```python
try:
    result = await self.complete(messages)
    parsed = self._parse_response(result)
except Exception as e:
    return {
        "error": str(e),
        "timestamp": datetime.now().isoformat(),
    }
```

### State Defaults (LangGraph)

```python
prompt = self.prompt.format(
    field1=state.get("field1") or "N/A",
    field2=json.dumps(state.get("field2", {}), indent=2),
)
```

---

## Anti-Patterns to Avoid

### 1. Don't Use LangGraph for Single-Step Tasks

```python
# BAD: Overkill for single step
class SimpleValidator(LangGraphAgent):
    def build_graph(self):
        workflow.add_node("validate", self.validate)
        workflow.add_edge("validate", END)  # Only one step!
        ...

# GOOD: Use simple Agent
class SimpleValidator(Agent):
    async def run(self, content):
        return await self.complete(...)
```

### 2. Don't Hardcode Prompts (Use Configuration)

```python
# BAD: Can't customize without code changes
async def run(self, content):
    prompt = "You are a validator..."  # Hardcoded

# GOOD: Configurable
self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
```

### 3. Don't Ignore Parse Failures

```python
# BAD: Crashes on invalid JSON
return json.loads(response)

# GOOD: Graceful fallback
try:
    return json.loads(response)
except json.JSONDecodeError:
    return {"error": "Parse failed", "raw": response[:500]}
```

### 4. Don't Forget State Threading (LangGraph)

```python
# BAD: Loses previous state
async def step2(self, state):
    return {"step2_result": result}  # step1_result lost!

# GOOD: Preserve state
async def step2(self, state):
    return {**state, "step2_result": result}
```

---

## Choosing Between Patterns

| Question | Simple Agent | LangGraph |
|----------|--------------|-----------|
| Single LLM call sufficient? | Yes | No |
| Steps depend on each other? | N/A | Yes |
| Need conditional routing? | No | Yes |
| Multiple analysis phases? | No | Yes |
| CI/CD batch processing? | Yes | Maybe |
| Complex state management? | No | Yes |

**Rule of thumb:** Start with Simple Agent. Only use LangGraph when you need multi-step state threading.
