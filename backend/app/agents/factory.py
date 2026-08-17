"""
Builds a ready-to-run ToolCallingAgent for a given AgentType: resolves
the system prompt, binds the tool set (app/tools/registry.py), and wraps
the LLM client the model router selected.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import coder, debugger, documenter, planner, reviewer, tester
from app.agents.base import ToolCallingAgent
from app.core.config import Settings
from app.core.constants import AgentType
from app.orchestrator.llm_clients import LLMClient
from app.tools.registry import build_tools_for_agent

_SYSTEM_PROMPTS: dict[AgentType, str] = {
    AgentType.PLANNER: planner.SYSTEM_PROMPT,
    AgentType.CODER: coder.SYSTEM_PROMPT,
    AgentType.REVIEWER: reviewer.SYSTEM_PROMPT,
    AgentType.DEBUGGER: debugger.SYSTEM_PROMPT,
    AgentType.TESTER: tester.SYSTEM_PROMPT,
    AgentType.DOCUMENTER: documenter.SYSTEM_PROMPT,
}


def build_agent(
    agent_type: AgentType,
    llm_client: LLMClient,
    db: AsyncSession,
    project_id: uuid.UUID,
    settings: Settings,
    task_id: uuid.UUID | None = None,
) -> ToolCallingAgent:
    tools = build_tools_for_agent(agent_type, db, project_id, settings, task_id=task_id)
    return ToolCallingAgent(
        system_prompt=_SYSTEM_PROMPTS[agent_type],
        tools=tools,
        llm_client=llm_client,
        max_iterations=settings.AGENT_TOOL_LOOP_MAX_ITERATIONS,
    )
