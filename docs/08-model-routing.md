# 08 - Model Routing

## The core mechanism

`app/orchestrator/model_router.py::route_task(task_type, attempt_count, prior_attempt_failed)`
is a pure function returning a `RoutingDecision(tier, reason, requires_llm, escalated)`.
No LLM call is ever made to decide this - it's a lookup table plus two rules:

1. **Mechanical task types never touch an LLM.** `scaffold`, `install_dependencies`, and
   `format_lint` route to `DETERMINISTIC` regardless of anything else. This is the single
   biggest lever for cutting LLM calls: it removes whole task categories from the token
   budget rather than making them cheaper.
2. **A retry after a real failure escalates one tier.** `CHEAP -> CODING -> REASONING`
   (capped). A second failure at the same tier is evidence the task needs more reasoning,
   not another identical guess - see [12-failure-recovery.md](12-failure-recovery.md) for
   how this interacts with the retry-vs-escalate-to-Debug-agent decision.

| Task type | Default tier |
|---|---|
| scaffold, install_dependencies, format_lint | deterministic (no LLM) |
| documentation, review | cheap |
| schema_design, backend_implementation, frontend_implementation, integration, test_authoring, bugfix | coding |
| Planner calls (requirement analysis, architecture, decomposition) | reasoning, always |

## Provider abstraction

Tier -> concrete model name/provider resolution happens in exactly one place
(`llm_clients.resolve_model_for_tier`), reading four independent env var pairs
(`MODEL_CHEAP`/`MODEL_PROVIDER_CHEAP`, etc.). Changing which model backs a tier is a
one-line `.env` edit, never a code change. `llm_clients.py` wraps LangChain's
`ChatOpenAI`/`ChatAnthropic` behind one small `LLMClient` interface (`acomplete(messages,
tools) -> LLMResult`), so the agent loop (`app/agents/base.py`) never imports a
provider SDK directly.

## The stub/dry-run provider

`MODEL_PROVIDER_*=stub` routes to `StubLLMClient`, a deterministic, zero-network test
double. It has two legitimate uses: the test suite (so agent-loop tests need no API key),
and an explicit "dry run" deployment mode for validating the full orchestration graph -
scheduling, context assembly, tool calls, retries - end to end with zero API cost before
pointing it at a real provider. It is never silently substituted for a misconfigured real
provider: `build_llm_client` raises if a real provider's API key is missing, rather than
falling back.

## Why the Planner is the one place this project doesn't economize

Every other routing rule exists to spend fewer tokens. The Planner is routed to
`REASONING` unconditionally because a bad plan is the most expensive mistake the system
can make: every downstream task inherits it, and cheap-but-wrong architecture decisions
compound into far more retries and Debug-agent escalations than a single well-reasoned
planning call costs. See [23-design-decisions.md](23-design-decisions.md).
