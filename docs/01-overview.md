# 01 - Overview

## What this is

Daedalus takes a natural-language software requirement and
autonomously plans, decomposes, implements, tests, debugs, and integrates it - while
treating "how much intelligence does this step actually need" as a first-class design
question, not an afterthought.

It is not a chatbot, not a RAG demo, and not a scripted multi-agent conversation. Every
agent run in this system executes real tools (reads/writes real files, runs real tests
in a sandboxed container) and every orchestration decision (what to schedule next, which
model to use, whether to retry) is made by inspecting real, persisted state.

## The one-sentence design principle

> Use intelligence only where intelligence is required.

A task that is mechanical (scaffold a folder, install dependencies, format code) never
touches an LLM. A task that requires reasoning (implement a feature, diagnose a failure)
is routed to a model tier sized for its difficulty, with only the context it actually
needs. See [07-token-optimization.md](07-token-optimization.md) for how this is measured,
not just claimed.

## A 60-second tour

1. A user submits a requirement via the frontend (`POST /projects`, then `POST /projects/{id}/start`).
2. The Planner agent (the one place this project deliberately spends extra tokens - see
   [23-design-decisions.md](23-design-decisions.md)) analyzes the requirement, proposes an
   architecture, and decomposes it into a task DAG.
3. A deterministic scheduler ([05-task-dag.md](05-task-dag.md)) figures out which tasks are
   unblocked and dispatches them - in parallel where possible - to a pool of ARQ workers.
4. Each task is routed ([08-model-routing.md](08-model-routing.md)) to either a tool call
   (no LLM) or a specialized agent at an appropriately-sized model tier, working from a
   minimal, task-specific context ([06-context-engineering.md](06-context-engineering.md)).
5. Failures are classified deterministically and either retried, escalated to a Debug
   agent, or routed to a human ([12-failure-recovery.md](12-failure-recovery.md),
   [13-human-in-the-loop.md](13-human-in-the-loop.md)).
6. Once the build phase completes, the integration test suite runs inside a sandboxed
   container ([11-code-execution-sandbox.md](11-code-execution-sandbox.md)).
7. The frontend shows all of this live via Server-Sent Events, plus a cost/token
   analytics view comparing the actual run against an estimated naive baseline.

## Where to go next

- Building a mental model of the system: [02-architecture.md](02-architecture.md)
- The LangGraph workflow itself: [03-agentic-workflow.md](03-agentic-workflow.md)
- "Why did you choose X over Y" for every major decision: [23-design-decisions.md](23-design-decisions.md)
- Running it locally: [20-local-development.md](20-local-development.md)
