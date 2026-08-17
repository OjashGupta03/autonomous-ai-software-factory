# 24 - Troubleshooting

## `pip install` / `npm install` behaves unexpectedly

This repository was authored in a sandbox with outbound network access blocked at the
registry level (`pip install` returned "No matching distribution found" even after
resolving the `externally-managed-environment` restriction; `npm ping` returned a 403).
If your own environment has similar restrictions, package installation will fail the same
way there - check your network/proxy/registry configuration first. See
[21-testing.md](21-testing.md) for exactly what this constraint did and didn't allow
verifying before this code reached you.

## `langgraph`/`langchain` import errors, or an API you expected isn't there

These packages release frequently, and the versions pinned in
`backend/requirements.txt` were the author's best knowledge at authoring time, not
verified against a live PyPI index (see the note at the top of that file). If
`app/orchestrator/graph.py` fails to import, check `pip show langgraph` against the
current LangGraph changelog - the code intentionally sticks to the long-stable
`StateGraph`/`START`/`END`/`add_node`/`add_edge`/`add_conditional_edges`/`compile()`
surface rather than newer/more volatile APIs (checkpointers, the `Send` fan-out
primitive), specifically to minimize this risk, but a major-version bump could still move
something.

## Sandbox execution fails immediately

Check, in order: (1) is the Docker daemon reachable from the backend/worker container -
`docker-compose.yml` mounts `/var/run/docker.sock` for exactly this; (2) has
`docker build -f docker/sandbox.Dockerfile -t factory-sandbox:latest .` actually been run
- the image is not built automatically by `docker compose up`; (3) does the host user
running Docker have permission to use that socket. See
[11-code-execution-sandbox.md](11-code-execution-sandbox.md) - this code path could not be
exercised against a real daemon while building this repo, so a first real run is the
actual test of it.

## A from-scratch build fails on `npm install`/`pip install` inside the sandbox

Expected, by default: `SANDBOX_NETWORK_DISABLED=true` blocks outbound network from
generated-code execution, including dependency installation. Either handle dependency
installation as a deliberate, reviewed exception (a task type that explicitly sets
`network_disabled=False` for that one call) or pre-seed a base sandbox image with the
project's expected dependencies already installed. See
[11-code-execution-sandbox.md](11-code-execution-sandbox.md).

## Frontend shows a blank screen / fails to build

TypeScript compilation was never run against this frontend while building it (no
installable npm packages in that environment). Run `npm install && npm run build` and
read the actual `tsc` errors - every file was checked for brace/paren balance and that
every import resolves to a real export, but that only catches a subset of what a full
type-check would. See [16-frontend.md](16-frontend.md).

## `/auth/login` returns 422 from a custom client

The endpoint uses the OAuth2 password-grant form shape (`application/x-www-form-urlencoded`,
field name `username`, not a JSON body with `email`) - see [15-api.md](15-api.md). This
was a real bug during development (a test helper called it with a JSON body before the
endpoint was aligned to the standard OAuth2 form) - if you're integrating a new client,
send a form body, not JSON.

## An orchestrator run seems stuck

Check `GET /projects/{id}/events` for the last event, and the project's `status`. A run
genuinely pauses (not hangs) at `needs_approval` - check
`GET /projects/{id}/approvals` for a pending decision. If `status` is `executing` with no
recent events, check the worker process's logs; `await_batch`'s deadline
(`TASK_BATCH_AWAIT_TIMEOUT_SECONDS`) will eventually force-fail a stuck batch rather than
hang forever, but that can take up to the configured timeout.
