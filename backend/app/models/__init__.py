"""
SQLAlchemy models.

Schema notes (full rationale in docs/14-database-design.md):
- Every table uses a UUID primary key + created_at/updated_at (TimestampMixin).
- `model_usage` from the original spec is intentionally NOT a separate table:
  it is a pure aggregation of `token_usage` grouped by model, which is
  cheaper and less error-prone as a query/view than a second write path
  that could drift from the source rows. See TokenUsage below.
- `artifacts` reference `files` by id + version rather than duplicating
  file content, per the "reference, don't copy" principle used throughout
  the context manager and agent messaging layer.
"""
from app.models.agent import Agent, AgentRun
from app.models.approval import Approval
from app.models.error import ErrorRecord, RetryAttempt
from app.models.event import ProjectEvent
from app.models.file import Artifact, File
from app.models.plan import ProjectPlan
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task, TaskDependency
from app.models.test_run import TestResult, TestRun
from app.models.token_usage import TokenUsage
from app.models.tool_call import ToolCall
from app.models.user import User

__all__ = [
    "Agent",
    "AgentRun",
    "Approval",
    "ErrorRecord",
    "RetryAttempt",
    "ProjectEvent",
    "Artifact",
    "File",
    "ProjectPlan",
    "Project",
    "Requirement",
    "Task",
    "TaskDependency",
    "TestResult",
    "TestRun",
    "TokenUsage",
    "ToolCall",
    "User",
]
