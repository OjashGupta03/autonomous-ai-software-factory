# 09 - Agent Design

## One loop, six configurations

Every agent is `app/agents/base.py::ToolCallingAgent` configured with a system prompt and
a bound tool subset - there is no per-agent bespoke prompting loop. The loop is a standard
ReAct cycle: send messages + tool specs, execute any requested tool calls for real (never
fabricated), append results as tool messages, repeat until the model stops requesting
tools or `AGENT_TOOL_LOOP_MAX_ITERATIONS` is hit. This was verified directly (not just
by inspection): `backend/tests/unit/test_agent_loop.py` drives the loop with a scripted
`StubLLMClient` and asserts on iteration counts, accumulated token usage, and - critically
- that a tool call which *raises* is caught as a failed `ToolResult` rather than crashing
the agent (a real failure mode a naive implementation would miss).

### Planner
Requirement analysis, architecture, task decomposition. Read-only tools. Always routed to
`REASONING` (see [08-model-routing.md](08-model-routing.md)). Its three calls produce
structured JSON (parsed by `ProjectRunner`, not by another LLM call) rather than prose.

### Coder
Implements one task. Read tools + `file_writer`. Receives a context-manager-built prompt
scoped to exactly that task - never the full project.

### Reviewer
Read-only by construction (`app/tools/registry.py` never grants it `file_writer`) - a
reviewer that can silently rewrite what it's reviewing isn't providing an independent
check. Routed to `CHEAP` by default.

### Debugger
Invoked specifically when `failure_recovery.decide_recovery` returns
`escalate_to_debugger` - i.e. a blind retry was judged unlikely to help. Always receives
the specific error via `context_manager`'s `current_issue` field; diagnosis is the point,
not another guess.

### Tester
Authors tests when a task calls for it, and can invoke `test_runner`. Test *execution* and
the pass/fail signal that drives orchestrator routing do not depend on this agent -
`app/services/test_service.py` parses pytest output deterministically. This agent is for
the reasoning parts (what to test, what a failure means), not the yes/no of whether it
passed.

### Documenter
Runs only on tasks explicitly typed `documentation` - never forced after every task.
Routed to `CHEAP`.

## Structured communication, not conversation

Agents do not exchange natural-language messages with each other. `AgentMessage`
(`app/orchestrator/messages.py`) is a small dataclass (`task_id`, `sender`, `intent`,
one-sentence `summary`, `artifacts` as references, `status`) - see
[06-context-engineering.md](06-context-engineering.md) for how its `summary` becomes a
dependency-summary line in a downstream task's context.

## Tool access is scoped per role

`app/tools/registry.py::build_tools_for_agent` is the single place that answers "what can
this agent type touch" - Planner and Reviewer get read-only tools; Coder/Debugger/Tester
additionally get `file_writer`; only Debugger and Tester get `test_runner`. This is a
narrower, auditable version of "give every agent every tool and hope the prompt is
enough".
