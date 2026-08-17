"""
Per-run tool registry - builds the concrete set of Tool instances (bound
to a db session / project_id / settings) that a given agent type is
allowed to use. Keeping this centralized means "what can the Reviewer
touch" is answered in one place, not scattered across agent classes.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AgentType
from app.tools.base import Tool
from app.tools.db_tools import (
    CodeSearchTool,
    DirectoryListerTool,
    FileDiffTool,
    FileReaderTool,
    FileSearchTool,
    FileWriterTool,
    PackageInspectorTool,
)
from app.tools.exec_tools import FormatterTool, LintRunnerTool, ShellCommandRunnerTool, TestRunnerTool

# Read-only tools every agent gets, regardless of role - inspecting the
# workspace is never the dangerous part, writing to it or executing
# something is.
_READ_ONLY = ("file_reader", "file_search", "directory_lister", "code_search", "file_diff", "package_inspector")

_AGENT_TOOL_NAMES: dict[AgentType, tuple[str, ...]] = {
    AgentType.PLANNER: _READ_ONLY,
    AgentType.CODER: _READ_ONLY + ("file_writer",),
    AgentType.REVIEWER: _READ_ONLY,
    AgentType.DEBUGGER: _READ_ONLY + ("file_writer", "test_runner"),
    AgentType.TESTER: _READ_ONLY + ("file_writer", "test_runner"),
    AgentType.DOCUMENTER: _READ_ONLY + ("file_writer",),
}


def build_tools_for_agent(
    agent_type: AgentType,
    db: AsyncSession,
    project_id: uuid.UUID,
    settings: Settings,
    task_id: uuid.UUID | None = None,
) -> list[Tool]:
    all_tools: dict[str, Tool] = {
        "file_reader": FileReaderTool(db, project_id),
        "file_writer": FileWriterTool(db, project_id, created_by_task_id=task_id),
        "file_search": FileSearchTool(db, project_id),
        "directory_lister": DirectoryListerTool(db, project_id),
        "code_search": CodeSearchTool(db, project_id),
        "file_diff": FileDiffTool(db, project_id),
        "package_inspector": PackageInspectorTool(db, project_id),
        "test_runner": TestRunnerTool(db, project_id, settings),
        "lint_runner": LintRunnerTool(db, project_id, settings),
        "formatter": FormatterTool(db, project_id, settings),
        "shell_command_runner": ShellCommandRunnerTool(db, project_id, settings),
    }
    names = _AGENT_TOOL_NAMES.get(agent_type, _READ_ONLY)
    return [all_tools[n] for n in names]
