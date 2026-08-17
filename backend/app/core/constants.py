"""Shared enums and constant string values used across the app.

Kept as plain str-Enums (rather than scattering magic strings) so the
orchestrator, DB models and API schemas all agree on the same vocabulary.
"""
from __future__ import annotations

import enum


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"
    SKIPPED = "skipped"


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    EXECUTING = "executing"
    TESTING = "testing"
    NEEDS_APPROVAL = "needs_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, enum.Enum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"
    TESTER = "tester"
    DOCUMENTER = "documenter"


class ModelTier(str, enum.Enum):
    """Routing tiers - deliberately decoupled from concrete model names.
    See app/orchestrator/model_router.py."""
    DETERMINISTIC = "deterministic"  # no LLM call at all
    CHEAP = "cheap"
    CODING = "coding"
    REASONING = "reasoning"
    FALLBACK = "fallback"


class TaskType(str, enum.Enum):
    """Used by the scheduler/router to decide whether a task even needs an
    agent, and if so, which one and at what model tier."""
    SCAFFOLD = "scaffold"                # deterministic, tool-only
    INSTALL_DEPENDENCIES = "install_dependencies"  # deterministic, tool-only
    FORMAT_LINT = "format_lint"          # deterministic, tool-only
    SCHEMA_DESIGN = "schema_design"
    BACKEND_IMPLEMENTATION = "backend_implementation"
    FRONTEND_IMPLEMENTATION = "frontend_implementation"
    INTEGRATION = "integration"
    TEST_AUTHORING = "test_authoring"
    BUGFIX = "bugfix"
    DOCUMENTATION = "documentation"
    REVIEW = "review"


class ErrorCategory(str, enum.Enum):
    """Deterministic classification bucket for a failure. Drives the
    retry-vs-escalate decision in app/orchestrator/failure_recovery.py."""
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    ASSERTION_FAILURE = "assertion_failure"
    TIMEOUT = "timeout"
    DEPENDENCY_MISSING = "dependency_missing"
    RESOURCE_LIMIT = "resource_limit"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


class ApprovalType(str, enum.Enum):
    DESTRUCTIVE_DB_CHANGE = "destructive_db_change"
    EXTERNAL_DEPLOYMENT = "external_deployment"
    SENSITIVE_CONFIG_CHANGE = "sensitive_config_change"
    SUSPICIOUS_PACKAGE = "suspicious_package"
    REPEATED_FAILURE = "repeated_failure"
    HIGH_COST_ESCALATION = "high_cost_escalation"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ProjectEventType(str, enum.Enum):
    PLANNER_STARTED = "planner_started"
    PLAN_READY = "plan_ready"
    TASK_CREATED = "task_created"
    TASK_READY = "task_ready"
    AGENT_STARTED = "agent_started"
    TOOL_CALLED = "tool_called"
    FILE_MODIFIED = "file_modified"
    TASK_SUCCEEDED = "task_succeeded"
    TASK_FAILED = "task_failed"
    TESTS_STARTED = "tests_started"
    TESTS_FINISHED = "tests_finished"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    PROJECT_COMPLETED = "project_completed"
    PROJECT_FAILED = "project_failed"
