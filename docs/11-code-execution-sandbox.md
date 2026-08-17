# 11 - Code Execution Sandbox

## Why this is non-negotiable

This system executes LLM-generated code. That is a fundamentally different trust
situation from running code a human reviewed and committed. Every test run, lint pass,
format, or shell command goes through `app/sandbox/docker_executor.py` -
there is no code path in this repository where generated code runs directly on the host
or inside the backend/worker application containers.

## What the sandbox actually does

For every execution request (`SandboxExecutionRequest`): launches a container from the
`factory-sandbox:latest` image (`docker/sandbox.Dockerfile`) with:

- `network_mode="none"` by default (`SANDBOX_NETWORK_DISABLED=true`) - generated code
  cannot make outbound network calls unless an operator deliberately re-enables it.
- A memory limit (`SANDBOX_MEMORY_LIMIT`, default `512m`) and a CPU share
  (`nano_cpus`, from `SANDBOX_CPU_LIMIT`).
- `pids_limit=256` - blunts fork-bomb-style resource exhaustion.
- `cap_drop=["ALL"]` and `security_opt=["no-new-privileges"]`.
- A non-root user inside the image itself (`docker/sandbox.Dockerfile` creates and
  switches to `sandbox`, uid 1000) - defense in depth alongside the cap-drop above.
- A hard wall-clock timeout (`SANDBOX_TIMEOUT_SECONDS`) enforced from the *host* side via
  `container.wait(timeout=...)`, independent of whatever the process inside is doing -
  a hung process gets killed and its container force-removed either way.
- stdout/stderr captured and returned as a structured `SandboxExecutionResult`, never
  streamed directly into anything that executes it further.

Argv only, never a shell string (`command: list[str]`) - see
[10-tool-system.md](10-tool-system.md) for the allowlist on top of that for the
general-purpose shell tool specifically.

## Workspace materialization

The sandbox needs a real, bind-mountable directory; the project's canonical file store is
Postgres rows. `sandbox.Workspace.materialize()` writes the current `files` table content
out to a throwaway directory under `WORKSPACE_ROOT/{project_id}/{uuid}`, the container
mounts it read-write at `/workspace`, and (only for tools that can legitimately mutate
files, like the formatter) `Workspace.collect()` reads back whatever changed and persists
it as new file versions. The directory is removed (`Workspace.cleanup()`) after every
call, success or failure.

## Known limitations (stated plainly, not glossed over)

- **This is a single Docker container boundary, not a hardened micro-VM.** A container-
  escape vulnerability in the Docker runtime itself is out of scope for this project to
  defend against. For genuinely hostile/multi-tenant workloads, the `DockerSandboxExecutor`
  interface is narrow enough to swap for a gVisor- or Firecracker-based executor without
  touching call sites, but that swap is not implemented here.
- **This could not be exercised end-to-end in the environment that generated this
  repository** - no Docker daemon was available there (confirmed via `which docker`
  returning nothing). The container-construction logic (arguments, timeout handling,
  cleanup) is written to the best of the author's knowledge of the `docker` Python SDK,
  but running it against a real daemon is what actually confirms it, not a code review.
  See [20-local-development.md](20-local-development.md) for the first-run check to do
  this yourself, and [24-troubleshooting.md](24-troubleshooting.md) if it doesn't behave
  as documented.
- **The bind mount is read-write.** A determined piece of generated code could still fill
  the mounted directory with junk (bounded by whatever disk quota the host enforces, which
  this project does not configure) or, within the container, do anything the dropped
  capabilities + non-root user still permit. This is an acceptable risk for a
  local-development/demo-scale system; a production deployment executing untrusted code at
  scale should add disk quotas and consider a stricter isolation layer.
- **Dependency installation runs inside the same sandbox**, with network access disabled
  by default - meaning `npm install`/`pip install` steps will fail unless an operator
  explicitly re-enables sandbox networking for that step, which is a deliberate default,
  not an oversight, but does mean a truly from-scratch build needs that setting reviewed.
  See [24-troubleshooting.md](24-troubleshooting.md).
