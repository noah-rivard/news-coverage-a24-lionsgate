# Agents SDK quick reference (Python)

This repo already depends on `openai>=1.54.0` and `openai-agents>=0.6.1`. Use this page as a thin layer between the code and the official docs so we do not flood Codex with duplicated detail.

## Where to read more (authoritative)
- Agents SDK overview: https://platform.openai.com/docs/guides/agents-sdk
- Python API reference and examples: https://openai.github.io/openai-agents-python/
- GitHub repo (changelog, examples): https://github.com/openai/openai-agents-python

## Core primitives you will see in this codebase
- `Agent`: an LLM with instructions plus optional `tools`, `handoffs`, guardrails, and `output_type`.
- `Runner.run` / `Runner.run_sync`: executes an agent loop and returns `RunResult` with `final_output`, `messages`, and trace info.
- Tools: plain Python functions decorated with `@function_tool`; schema and descriptions come from type hints/docstring. Agents themselves can be turned into tools (`agent.as_tool()`), which matches our manager-agent-calls-specialists pattern.
- Handoffs: let one agent hand control to another; helpful when delegation, not needed when a manager keeps control.
- Sessions: `SQLiteSession` or `RedisSession` to persist conversation context between runs; optional for stateless CLI runs.
- Tracing: on by default; wire in a processor (Logfire, AgentOps, etc.) only when we need external observability.

## Minimal usage pattern (fits our summarizer)
```python
from agents import Agent, Runner, function_tool
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    key_points: list[str]

@function_tool
def fetch_article(url: str) -> str:
    """Return raw article text for summarization."""
    ...

summarizer = Agent(
    name="Article summarizer",
    instructions="Summarize entertainment news in non-technical language.",
    tools=[fetch_article],
    output_type=list[Summary],  # structured output via Pydantic
)

result = Runner.run_sync(summarizer, "https://example.com/news/123")
print(result.final_output)
```
Tips:
- Put shared state (API clients, feature flags) on a context object and pass it to `Runner.run(_sync)` so every tool and handoff receives it.
- Prefer `output_type` for anything we later parse (summaries, ingest payloads) to keep validation strict.
- Use `ModelSettings(tool_choice="required")` if the LLM should be forced to call a specific tool (e.g., ingest before summarize).

## Pattern choice for this repo
- Default to **manager agent with tools** (our current roadmap): a coordinator agent exposes ingest/summarize/format helpers as tools and keeps the conversation. Use handoffs only when a sub-agent should take over the dialog entirely.
- Keep tools small, deterministic, and side-effect aware so tests can stub them without hitting the network.
- When adding a new agent or tool, document its intent and inputs in the docstring; that text becomes the tool description sent to the model.

## Sessions and state
- Current decision: one run per article, stateless. Do not persist sessions for the CLI or service right now.
- If we ever need continuity (e.g., multi-article chat), wrap runs with `SQLiteSession("data/agent.db")` and let the session replay context instead of manually passing message history.

## Guardrails and validation
- Add guardrails to validate user/article inputs or enforce tone on outputs when we expand beyond trusted sources.
- Guardrails run alongside the agent; fail fast on validation errors to save tokens.

## Tracing and observability
- Tracing is automatic; plug in a processor when debugging or during load testing. For privacy, disable or scrub traces that include raw article text before shipping logs elsewhere.

## When to stay with Responses API
- For single-shot summarization (current implementation), the Responses API alone is fine. Move to Agents when we need multi-step orchestration, tool calls, or persistent context. Document the pivot in `src/AGENTS.md` if/when we switch.
