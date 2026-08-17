# 06 - Context Engineering

## The problem this solves

A naive multi-agent system tends to hand every agent the entire conversation history, or
the entire project state, "just in case". Costs grow with every call, and most of what's
in context is irrelevant to the task at hand. `app/orchestrator/context_manager.py`
exists to make the opposite the default: **construct the minimum useful context for each
task, on a fixed budget, and make truncation visible rather than silent.**

## What gets assembled, and in priority order

`build_task_context` receives plain data (never queries the DB itself - see
`app/services/agent_execution_service.py::_gather_context_inputs` for the fetch side) and
assembles, strictly in this priority order, stopping whenever the token budget
(`Settings.CONTEXT_BUDGET_*`, one per agent role) runs out:

1. **Task title + description** - never dropped or truncated, even if it alone exceeds
   the budget. This is the minimum viable ask.
2. **Current issue** (the specific error, on a retry) - a Debug agent given a task
   description but not the actual failure is not meaningfully debugging anything.
3. **Architecture excerpt** - hard-capped at 600 characters regardless of remaining
   budget. A coding agent needs "React + TypeScript, REST over `/api/v1`", not the full
   architecture document.
4. **API contract excerpt** - small, high value.
5. **Dependency summaries** - one line each (see below), not full transcripts.
6. **Relevant files** - greedy-packed smallest-first so more distinct files fit before any
   get dropped; a file that doesn't fully fit gets a truncated head rather than being
   omitted outright, so the agent at least knows it exists.

The result (`TaskContext`) reports `estimated_tokens` vs. `budget_tokens` and a
`truncated` flag - callers and tests can assert on whether the budget was actually
respected, not just hope it was.

## "Reference, don't replay"

Section 4 of `TaskContextInput` (`dependency_summaries`) is deliberately a list of short
strings, not file contents or prior agent transcripts. This is produced by
`AgentMessage.as_dependency_summary()` (`app/orchestrator/messages.py`) - a structured,
one-sentence record of what a completed task produced, referencing artifact/file paths
rather than embedding them. A frontend agent working on login UI receives "T3 (backend
auth) completed: added POST /auth/login." plus the actual `authApi.ts` file if it's
relevant - never the backend agent's full conversation.

## Token estimation without a live tiktoken cache

`estimate_tokens` tries `tiktoken.get_encoding("cl100k_base")` and falls back to a
`len(text) // 4` heuristic if tiktoken (or its downloaded BPE tables) is unavailable -
which is exactly the situation in the sandbox that generated this repository (no network
access). The fallback is deliberately conservative (tends to *overestimate* token count
for code), which is the safer failure direction for a budget check. This is documented
here rather than left as a silent implementation detail because it is a real operational
consideration: the first time this runs in an environment with no network access to
download tiktoken's encoding files, budgets are still enforced, just slightly more
conservatively.

## What this is not

The context manager does not summarize or compress file contents with an LLM call -
that would reintroduce the exact cost this module exists to avoid. Compression here is
purely structural (truncation, exclusion, referencing) and free.
