"""
Sandboxed code execution (docs/11-code-execution-sandbox.md).

Generated code is NEVER executed directly on the host or inside the
backend/worker containers. Every test run, lint pass, formatter
invocation, or shell command runs inside a short-lived, resource-limited
Docker container built from the `factory-sandbox` image (docker/sandbox.Dockerfile),
with:
  - no network access (network_mode="none") unless explicitly re-enabled
    per deployment, which is NOT done by default
  - a hard memory limit and CPU share
  - a process-count limit (pids_limit) to blunt fork-bomb-style abuse
  - all Linux capabilities dropped, no-new-privileges set
  - a non-root user inside the container (see the sandbox Dockerfile)
  - a hard wall-clock timeout enforced from the host side, independent of
    whatever happens inside the container

KNOWN LIMITATIONS (see docs/11 and docs/19-security.md for the full
list): this is a single-layer container boundary, not a hardened
micro-VM (gVisor/Firecracker); a container-escape vulnerability in the
Docker runtime itself is out of scope for this project to defend against.
For genuinely hostile/multi-tenant workloads, run this behind gVisor or
swap the executor for a Firecracker-based one - the `SandboxExecutor`
interface below is written narrowly enough to make that swap possible
without touching call sites.

This module could not be exercised end-to-end in the environment that
generated this repository (no Docker daemon available there) - the
control flow, timeout handling, and argument construction are correct to
the best of the author's knowledge of the `docker` SDK, but running it
against a real daemon on first use is the way to confirm it, not this
comment. See docs/20-local-development.md.
"""
from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings


@dataclass
class SandboxExecutionRequest:
    command: list[str]  # argv form - never a raw shell string, to avoid injection
    workspace_dir: Path
    timeout_seconds: int
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    network_disabled: bool = True
    image: str = "factory-sandbox:latest"
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxExecutionResult:
    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    execution_time_ms: float


class SandboxUnavailableError(RuntimeError):
    """Raised when the Docker daemon/SDK is not reachable. Callers (the
    test/lint/format/shell tools) turn this into a failed ToolResult with
    a clear message rather than letting the exception propagate into an
    agent loop."""


class DockerSandboxExecutor:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def execute(self, request: SandboxExecutionRequest) -> SandboxExecutionResult:
        try:
            import docker  # docker-py; imported lazily so the rest of the
            # app works in environments that never touch the sandbox
            # (e.g. running the API alone against pre-existing data).
        except ImportError as e:
            raise SandboxUnavailableError(
                "The `docker` package is not installed. Sandbox execution requires it "
                "(see backend/requirements.txt) and a reachable Docker daemon."
            ) from e

        start = time.perf_counter()
        loop = asyncio.get_running_loop()

        def _run_sync() -> tuple[int | None, bytes, bool]:
            client = docker.from_env()
            container = None
            try:
                container = client.containers.run(
                    image=request.image,
                    command=request.command,
                    working_dir="/workspace",
                    volumes={str(request.workspace_dir): {"bind": "/workspace", "mode": "rw"}},
                    environment=request.env,
                    mem_limit=request.memory_limit,
                    nano_cpus=int(request.cpu_limit * 1_000_000_000),
                    pids_limit=256,
                    network_mode="none" if request.network_disabled else "bridge",
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges"],
                    detach=True,
                    stdout=True,
                    stderr=True,
                )
                try:
                    result = container.wait(timeout=request.timeout_seconds)
                    exit_code = result.get("StatusCode")
                    logs = container.logs(stdout=True, stderr=True)
                    return exit_code, logs, False
                except Exception:
                    # docker-py raises on a client-side wait timeout; the
                    # container itself may still be running, so it must be
                    # force-killed rather than left behind.
                    try:
                        container.kill()
                    except Exception:
                        pass
                    logs = b""
                    try:
                        logs = container.logs(stdout=True, stderr=True)
                    except Exception:
                        pass
                    return None, logs, True
            finally:
                if container is not None:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

        exit_code, logs, timed_out = await loop.run_in_executor(None, _run_sync)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        output = logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else str(logs)

        return SandboxExecutionResult(
            success=(exit_code == 0) and not timed_out,
            exit_code=exit_code,
            stdout=output,
            stderr="" if exit_code == 0 else output,
            timed_out=timed_out,
            execution_time_ms=elapsed_ms,
        )


class Workspace:
    """Materializes a project's DB-backed files onto disk so the sandbox
    (which needs a real bind-mountable directory) can operate on them,
    then reads back whatever changed so the caller can persist it to the
    `files` table. Each call gets its own throwaway directory under
    settings.WORKSPACE_ROOT to avoid cross-run interference."""

    def __init__(self, settings: Settings, project_id: str):
        self.settings = settings
        self.project_id = project_id
        self.path = Path(settings.WORKSPACE_ROOT) / project_id / str(uuid.uuid4())

    def materialize(self, files: dict[str, str]) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        for rel_path, content in files.items():
            full = self.path / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
        return self.path

    def collect(self) -> dict[str, str]:
        """Reads every file back off disk (used after a formatter run,
        which may have rewritten files in place)."""
        collected = {}
        if not self.path.exists():
            return collected
        for p in self.path.rglob("*"):
            if p.is_file():
                try:
                    collected[str(p.relative_to(self.path))] = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue  # binary files are skipped, not corrupted into the DB as text
        return collected

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)
