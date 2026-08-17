"""
Structured agent-to-agent messages (docs/18... folded into
docs/09-agent-design.md and docs/06-context-engineering.md).

Agents never exchange free-form natural-language conversation with each
other. When one task's output matters to another (e.g. the backend task
that defines an API contract, consumed by the frontend task that calls
it), it is passed as an AgentMessage: a short, structured record that
references artifacts by id rather than embedding their content. The
receiving task's context is then built from these messages via
context_manager.build_task_context (dependency_summaries), not by
replaying the sender's full run.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

MessageStatus = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class AgentMessage:
    task_id: str
    sender: str  # agent name, e.g. "coder"
    recipient: str | None  # None = broadcast to any dependent task
    intent: str  # e.g. "artifact_ready", "api_contract_defined", "blocked"
    summary: str  # ONE short sentence - this is what ends up in a dependent
    # task's context, so it needs to stand alone without the sender's
    # original prompt/response.
    artifacts: list[str] = field(default_factory=list)  # artifact ids, not content
    required_context: list[str] = field(default_factory=list)  # file paths a recipient may need
    result: dict | None = None
    status: MessageStatus = "ok"
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def as_dependency_summary(self) -> str:
        """The compact, one-line form injected into a dependent task's
        context (see TaskContextInput.dependency_summaries)."""
        prefix = f"[{self.sender}] "
        suffix = f" (see artifacts: {', '.join(self.artifacts)})" if self.artifacts else ""
        return f"{prefix}{self.summary}{suffix}"
