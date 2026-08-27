"""
Sandbox-backed tools (docs/10-tool-system.md, docs/11-code-execution-sandbox.md).
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.file import File
from app.sandbox.docker_executor import (
    DockerSandboxExecutor, SandboxExecutionRequest, SandboxUnavailableError, Workspace,
)
from app.tools.base import Tool, ToolResult, timed
from app.tools.db_tools import _latest_files

_SHELL_ALLOWLIST = {
    "ls", "cat", "echo", "pwd", "find", "wc", "grep",
    "python3", "pip3", "node", "npm", "npx", "pytest", "black", "ruff",
}


async def _write_back(db: AsyncSession, project_id: uuid.UUID, changed_files: dict[str, str]) -> list[str]:
    current = await _latest_files(db, project_id)
    modified_paths: list[str] = []
    for path, content in changed_files.items():
        prev = current.get(path)
        if prev is not None and prev.content == content:
            continue
        next_version = (prev.version + 1) if prev else 1
        db.add(File(project_id=project_id, path=path, content=content,
                     content_hash=hashlib.sha256(content.encode()).hexdigest(), version=next_version))
        modified_paths.append(path)
    if modified_paths:
        await db.commit()
    return modified_paths


class TestRunnerTool(Tool):
    name = "test_runner"
    description = "Run the project's test suite inside the sandbox."
    parameters_schema = {"type": "object", "properties": {"test_path": {"type": "string"}}}

    def __init__(self, db: AsyncSession, project_id: uuid.UUID, settings: Settings):
        self.db = db
        self.project_id = project_id
        self.settings = settings

    async def run(self, test_path: str = "") -> ToolResult:
        files = await _latest_files(self.db, self.project_id)
        content_map = {p: f.content for p, f in files.items()}
        ws = Workspace(self.settings, str(self.project_id))
        ws.materialize(content_map)
        is_js = any(p.endswith("package.json") for p in content_map)
        if is_js:
            base_cmd = f"npm install && npm test{' -- ' + test_path if test_path else ''}"
        else:
            base_cmd = f"if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; elif [ -f requirements.txt ]; then pip install -r requirements.txt; fi && if [ -d backend ]; then cd backend && python3 -m pytest -q{' ' + test_path if test_path else ''}; else python3 -m pytest -q{' ' + test_path if test_path else ''}; fi"
        command = ["bash", "-c", base_cmd]
        try:
            with timed() as t:
                executor = DockerSandboxExecutor(self.settings)
                result = await executor.execute(SandboxExecutionRequest(
                    command=command, workspace_dir=ws.path, timeout_seconds=self.settings.SANDBOX_TIMEOUT_SECONDS,
                    memory_limit=self.settings.SANDBOX_MEMORY_LIMIT, cpu_limit=self.settings.SANDBOX_CPU_LIMIT,
                    network_disabled=self.settings.SANDBOX_NETWORK_DISABLED, image=self.settings.SANDBOX_IMAGE,
                ))
        except SandboxUnavailableError as e:
            ws.cleanup()
            return ToolResult(success=False, error=str(e))
        ws.cleanup()
        return ToolResult(success=result.success, output={"stdout": result.stdout[-8000:], "exit_code": result.exit_code, "timed_out": result.timed_out, "command": command}, execution_time_ms=t.elapsed_ms)


class LintRunnerTool(Tool):
    name = "lint_runner"
    description = "Run static analysis inside the sandbox. Does not modify files."
    parameters_schema = {"type": "object", "properties": {"path": {"type": "string"}}}

    def __init__(self, db: AsyncSession, project_id: uuid.UUID, settings: Settings):
        self.db = db
        self.project_id = project_id
        self.settings = settings

    async def run(self, path: str = ".") -> ToolResult:
        files = await _latest_files(self.db, self.project_id)
        content_map = {p: f.content for p, f in files.items()}
        ws = Workspace(self.settings, str(self.project_id))
        ws.materialize(content_map)
        is_js = any(p.endswith("package.json") for p in content_map)
        command = ["npx", "eslint", path] if is_js else ["ruff", "check", path]
        try:
            with timed() as t:
                executor = DockerSandboxExecutor(self.settings)
                result = await executor.execute(SandboxExecutionRequest(
                    command=command, workspace_dir=ws.path, timeout_seconds=self.settings.SANDBOX_TIMEOUT_SECONDS,
                    memory_limit=self.settings.SANDBOX_MEMORY_LIMIT, cpu_limit=self.settings.SANDBOX_CPU_LIMIT,
                    network_disabled=self.settings.SANDBOX_NETWORK_DISABLED, image=self.settings.SANDBOX_IMAGE,
                ))
        except SandboxUnavailableError as e:
            ws.cleanup()
            return ToolResult(success=False, error=str(e))
        ws.cleanup()
        return ToolResult(success=result.success, output={"stdout": result.stdout[-8000:], "exit_code": result.exit_code, "command": command}, execution_time_ms=t.elapsed_ms)


class FormatterTool(Tool):
    name = "formatter"
    description = "Auto-format the project's code inside the sandbox, and persist any resulting changes."
    parameters_schema = {"type": "object", "properties": {"path": {"type": "string"}}}

    def __init__(self, db: AsyncSession, project_id: uuid.UUID, settings: Settings):
        self.db = db
        self.project_id = project_id
        self.settings = settings

    async def run(self, path: str = ".") -> ToolResult:
        files = await _latest_files(self.db, self.project_id)
        content_map = {p: f.content for p, f in files.items()}
        ws = Workspace(self.settings, str(self.project_id))
        ws.materialize(content_map)
        is_js = any(p.endswith("package.json") for p in content_map)
        command = ["npx", "prettier", "--write", path] if is_js else ["black", path]
        try:
            with timed() as t:
                executor = DockerSandboxExecutor(self.settings)
                result = await executor.execute(SandboxExecutionRequest(
                    command=command, workspace_dir=ws.path, timeout_seconds=self.settings.SANDBOX_TIMEOUT_SECONDS,
                    memory_limit=self.settings.SANDBOX_MEMORY_LIMIT, cpu_limit=self.settings.SANDBOX_CPU_LIMIT,
                    network_disabled=self.settings.SANDBOX_NETWORK_DISABLED, image=self.settings.SANDBOX_IMAGE,
                ))
            modified: list[str] = []
            if result.success:
                changed = ws.collect()
                modified = await _write_back(self.db, self.project_id, changed)
        except SandboxUnavailableError as e:
            ws.cleanup()
            return ToolResult(success=False, error=str(e))
        ws.cleanup()
        return ToolResult(success=result.success, output={"modified_files": modified, "exit_code": result.exit_code}, execution_time_ms=t.elapsed_ms)


class ShellCommandRunnerTool(Tool):
    name = "shell_command_runner"
    description = (
        "Run a single allowlisted command (argv form, no shell metacharacters) inside the sandbox. "
        f"Allowed binaries: {', '.join(sorted(_SHELL_ALLOWLIST))}."
    )
    # NOTE: `network_disabled` is intentionally NOT declared here. This
    # schema is what gets bound to the LLM via to_langchain_tool_spec(),
    # so a model-driven tool call can only ever supply `argv` - it has no
    # way to request network access for itself. The `network_disabled`
    # parameter on run() below exists purely for a trusted, non-LLM
    # caller (the deterministic scaffold-task executor - see
    # agent_execution_service._execute_deterministic_task) to run a
    # Planner-authorized scaffold command (e.g. `npm create vite@latest`)
    # that legitimately needs the registry, without loosening what an
    # agent's own tool calls can do.
    parameters_schema = {
        "type": "object",
        "properties": {"argv": {"type": "array", "items": {"type": "string"}}},
        "required": ["argv"],
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID, settings: Settings):
        self.db = db
        self.project_id = project_id
        self.settings = settings

    async def run(self, argv: list[str], network_disabled: bool | None = None) -> ToolResult:
        if not argv:
            return ToolResult(success=False, error="argv must be a non-empty list.")
        if argv[0] not in _SHELL_ALLOWLIST:
            return ToolResult(success=False, error=f"'{argv[0]}' is not on the shell allowlist. Allowed: {sorted(_SHELL_ALLOWLIST)}")
        files = await _latest_files(self.db, self.project_id)
        content_map = {p: f.content for p, f in files.items()}
        ws = Workspace(self.settings, str(self.project_id))
        ws.materialize(content_map)
        effective_network_disabled = self.settings.SANDBOX_NETWORK_DISABLED if network_disabled is None else network_disabled
        try:
            with timed() as t:
                executor = DockerSandboxExecutor(self.settings)
                result = await executor.execute(SandboxExecutionRequest(
                    command=argv, workspace_dir=ws.path, timeout_seconds=self.settings.SANDBOX_TIMEOUT_SECONDS,
                    memory_limit=self.settings.SANDBOX_MEMORY_LIMIT, cpu_limit=self.settings.SANDBOX_CPU_LIMIT,
                    network_disabled=effective_network_disabled, image=self.settings.SANDBOX_IMAGE,
                ))
            modified: list[str] = []
            if result.success:
                changed = ws.collect()
                modified = await _write_back(self.db, self.project_id, changed)
        except SandboxUnavailableError as e:
            ws.cleanup()
            return ToolResult(success=False, error=str(e))
        ws.cleanup()
        return ToolResult(
            success=result.success,
            output={"stdout": result.stdout[-8000:], "exit_code": result.exit_code, "timed_out": result.timed_out, "modified_files": modified},
            execution_time_ms=t.elapsed_ms,
        )
