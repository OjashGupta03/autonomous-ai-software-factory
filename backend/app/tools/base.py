"""
Tool abstraction (docs/10-tool-system.md).

Agents act through tools, never by "hallucinating" a file write or a test
result into existence - every tool call is a real operation (against the
DB-backed workspace or the sandbox) that returns a structured ToolResult,
which is what gets recorded in the `tool_calls` table and shown in the
frontend's right panel.

Two tool families, split across two files:
- app/tools/db_tools.py: read/write/search operations against the
  project's DB-backed file store. Cheap, no subprocess, safe to run
  directly (they never execute generated code, only text I/O).
- app/tools/exec_tools.py: anything that actually *executes* something
  (tests, lint, formatters, shell commands). These always go through the
  sandbox (app/sandbox/docker_executor.py) - see docs/11-code-execution-sandbox.md
  for why that boundary is non-negotiable.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)
    execution_time_ms: float = 0.0

    def to_tool_call_row(self, tool_name: str, input_payload: dict) -> dict:
        """Shape matching the `tool_calls` table columns, for services to
        persist without duplicating this mapping everywhere."""
        return {
            "tool_name": tool_name,
            "input": input_payload,
            "output": self.output if isinstance(self.output, (dict, list, str, int, float, bool, type(None))) else str(self.output),
            "success": self.success,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


class _Timer:
    """Computes elapsed time live on every access (via a property, exposed
    through __getitem__ for the `t["elapsed_ms"]` call-site style used
    throughout app/tools/db_tools.py) rather than only on context-manager
    exit. This matters because several tools return early *inside* the
    `with timed() as t:` block (e.g. a no-op / already-exists short
    circuit) - if elapsed time were only finalized in a `finally` clause,
    reading `t["elapsed_ms"]` as part of that early return's own value
    would run before the block actually exits and raise a KeyError."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0

    def __getitem__(self, key: str) -> float:
        if key == "elapsed_ms":
            return self.elapsed_ms
        raise KeyError(key)


@contextmanager
def timed():
    yield _Timer()


class Tool(ABC):
    name: str
    description: str
    parameters_schema: dict  # JSON-schema-shaped, used for LangChain tool binding

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        ...

    def to_langchain_tool_spec(self) -> dict:
        """The dict shape LangChain's `bind_tools([...])` expects for a
        plain function-style tool spec (provider-agnostic across
        ChatOpenAI/ChatAnthropic)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }
