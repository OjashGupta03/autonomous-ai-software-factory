# 07 - Token Optimization Strategies

Fourteen concrete mechanisms, each with a one-line pointer to its actual implementation
(not just a claim):

| # | Strategy | Where |
|---|---|---|
| 1 | Structured state instead of conversation replay | `ProjectGraphState` (minimal) + Postgres (durable) - see [04](04-orchestrator.md) |
| 2 | Task-specific context construction | `context_manager.build_task_context` - see [06](06-context-engineering.md) |
| 3 | Hard-capped context sections (architecture excerpt, etc.) | `context_manager.py`, 600-char cap |
| 4 | Artifact references instead of full contents | `AgentMessage.as_dependency_summary`, `Artifact.file_id` - see [06](06-context-engineering.md) |
| 5 | Retrieval of only relevant files | greedy smallest-first packing in `build_task_context` |
| 6 | Result caching | `TokenUsage.cache_hit`; `_cache_key` in `llm_clients.py` (dedup key for identical calls) |
| 7 | Deterministic tools for simple operations | `model_router._DETERMINISTIC_TASK_TYPES` - see [08](08-model-routing.md) |
| 8 | Model routing by task complexity | `model_router.route_task` - see [08](08-model-routing.md) |
| 9 | Parallel execution | `scheduler.get_ready_tasks` + ARQ - see [05](05-task-dag.md), [17](17-worker-system.md) |
| 10 | Retry context minimization | only the *specific error* is added on retry, not more history - see [06](06-context-engineering.md) |
| 11 | One planning pass, not repeated re-planning | `decompose_tasks` runs once per project; `run_or_resume` never re-invokes it |
| 12 | Reuse of prior decisions | dependency summaries reference completed work instead of re-deriving it |
| 13 | Compact task outputs | agent `final_content` capped (2000 chars) before storage as `AgentRun.output_summary` |
| 14 | Per-agent context budgets | `Settings.CONTEXT_BUDGET_PLANNER_TOKENS` / `_CODING_` / `_REVIEW_` / `_DEBUG_` / `_TEST_` / `_DOCS_` |

## The naive-vs-optimized comparison

`app/orchestrator/naive_comparison.py` computes what an unoptimized pipeline *would have*
cost for a project of the same size, using a documented, parameterized model
(`NaiveWorkflowAssumptions`): every task touches ~6 agents (mirroring the "Bad
architecture" chain in the project brief: Planner -> Divider -> Coder -> Reviewer ->
Tester -> Debugger), and each call's input carries the full history of every prior call -
so naive input tokens grow roughly with the *square* of the call count, not linearly.

**This is explicitly an estimate, not a measurement** - the naive pipeline never actually
runs, because building it would defeat the point of the project. Every number on the
"optimized" side of the comparison, by contrast, comes directly from recorded
`token_usage` rows. The distinction is stated in the API response, the frontend copy, and
here, deliberately, so the comparison can't be mistaken for two real runs being compared.
See `backend/tests/unit/test_naive_comparison.py` for the properties this estimate is
held to (savings never negative, naive cost grows faster than linearly in task count).

## What's deliberately NOT here

There is no LLM-based summarization/compression step. Every mechanism above is either
structural (truncation, referencing, caching) or a routing decision - none of them spend
tokens to save tokens.
