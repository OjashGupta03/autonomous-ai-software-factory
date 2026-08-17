"""
Single-task execution (docs/09-agent-design.md, docs/10-tool-system.md).

This is the function the ARQ worker job (app/workers/tasks.py) calls for
every dispatched task. It is the one place that ties together: model
routing (does this task even need an LLM), context assembly (if it
does), running the agent's tool-calling loop, and recording everything
(AgentRun, ToolCall, TokenUsage, File/Artifact writes already happen
inside the tools themselves) - then updating the task's terminal status
and publishing the events the frontend's live view renders.

Two paths:
- `_execute_deterministic_task`: DETERMINISTIC-tier tasks (scaffold,
  install_dependencies, format_lint) never touch an LLM. They apply a
  structured payload the Planner already produced, or run a tool
  directly (formatter/shell_command_runner).
- `_execute_agent_task`: everything else goes through the ReAct-style
  ToolCallingAgent loop (app/agents/base.py).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import build_agent
from app.core.config import Settings
from app.core.constants import AgentType, ErrorCategory, ProjectEventType, TaskType
from app.models.agent import AgentRun
from app.models.error import ErrorRecord
from app.models.file import File
from app.models.plan import ProjectPlan
from app.models.tool_call import ToolCall
from app.orchestrator import context_manager, model_router
from app.orchestrator.failure_recovery import classify_error
from app.orchestrator.llm_clients import build_llm_client, resolve_model_for_tier
from app.services import event_service, task_service, token_service
from app.tools.exec_tools import FormatterTool, ShellCommandRunnerTool


async def _execute_deterministic_task(
    db: AsyncSession, redis: Redis | None, settings: Settings, task
) -> tuple[bool, str]:
    """Returns (success, summary). No LLM call, no AgentRun row - purely
    mechanical, so there is nothing to route or account for token-wise."""
    payload = task.deterministic_payload or {}
    action = payload.get("action")

    if task.task_type == TaskType.SCAFFOLD or action == "create_files":
        files = payload.get("files", {})
        for path, content in files.items():
            row = File(
                project_id=task.project_id,
                path=path,
                content=content,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                version=1,
                created_by_task_id=task.id,
            )
            db.add(row)
            await event_service.publish_event(
                db, redis, task.project_id, ProjectEventType.FILE_MODIFIED, {"path": path, "task_id": str(task.id)}
            )
        await db.commit()
        return True, f"Scaffolded {len(files)} file(s)."

    if task.task_type == TaskType.INSTALL_DEPENDENCIES or action == "install":
        # Recorded as metadata for now (the actual `npm install`/`pip
        # install` happens once, inside the sandbox, as part of a later
        # test_runner/build call rather than as its own network-touching
        # step here - see docs/11-code-execution-sandbox.md on why
        # SANDBOX_NETWORK_DISABLED defaults to true and what that implies
        # for this task type).
        packages = payload.get("packages", [])
        return True, f"Recorded {len(packages)} dependency/dependencies to install: {', '.join(packages[:10])}"

    if task.task_type == TaskType.FORMAT_LINT or action == "format":
        tool = FormatterTool(db, task.project_id, settings)
        result = await tool.run(payload.get("path", "."))
        return result.success, f"Formatted {len(result.output.get('modified_files', []))} file(s)." if result.success else (result.error or "Formatting failed.")

    if action == "shell":
        tool = ShellCommandRunnerTool(db, task.project_id, settings)
        result = await tool.run(payload.get("argv", []))
        return result.success, "Shell command completed." if result.success else (result.error or "Shell command failed.")

    return False, f"No deterministic handler for task_type={task.task_type} / action={action}."


async def _gather_context_inputs(db: AsyncSession, task) -> context_manager.TaskContextInput:
    """Fetches the plain data context_manager.build_task_context needs.
    This is the ONLY place that queries the DB on behalf of the context
    manager - the manager itself stays DB-free (see its module docstring)."""
    plan_result = await db.execute(
        select(ProjectPlan)
        .where(ProjectPlan.project_id == task.project_id, ProjectPlan.is_active.is_(True))
        .order_by(ProjectPlan.version.desc())
    )
    plan = plan_result.scalars().first()

    # Relevant files = path mentions in the task description + anything a
    # direct dependency task most recently wrote. Deliberately NOT "every
    # file in the project" - that is the entire point of docs/06.
    mentioned = context_manager.extract_mentioned_paths(task.description)
    dep_task_ids = [d.depends_on_task_id for d in task.dependencies]
    dep_files_result = await db.execute(
        select(File).where(File.project_id == task.project_id, File.created_by_task_id.in_(dep_task_ids))
    ) if dep_task_ids else None
    dep_files = list(dep_files_result.scalars().all()) if dep_files_result else []

    all_files_result = await db.execute(select(File).where(File.project_id == task.project_id))
    by_path: dict[str, File] = {}
    for f in all_files_result.scalars().all():
        cur = by_path.get(f.path)
        if cur is None or f.version > cur.version:
            by_path[f.path] = f

    candidates: dict[str, str] = {}
    for path in mentioned:
        if path in by_path:
            candidates[path] = by_path[path].content
    for f in dep_files:
        candidates.setdefault(f.path, f.content)

    dependency_summaries = [
        f"Dependency task produced {f.path} (v{f.version})." for f in dep_files[:10]
    ]

    latest_error: str | None = None
    if task.attempt_count > 1:
        err_result = await db.execute(
            select(ErrorRecord).where(ErrorRecord.task_id == task.id).order_by(ErrorRecord.created_at.desc())
        )
        latest = err_result.scalars().first()
        if latest:
            latest_error = latest.message

    return context_manager.TaskContextInput(
        task_title=task.title,
        task_description=task.description,
        task_type=task.task_type.value,
        architecture_summary=plan.architecture_summary if plan else None,
        dependency_summaries=dependency_summaries,
        candidate_files=[context_manager.FileSnippet(path=p, content=c) for p, c in candidates.items()],
        current_issue=latest_error,
        budget_tokens=task.context_budget_tokens or 4000,
    )


async def _execute_agent_task(
    db: AsyncSession, redis: Redis | None, settings: Settings, task, routing: model_router.RoutingDecision
) -> tuple[bool, str]:
    model_name, provider = resolve_model_for_tier(routing.tier, settings)
    try:
        llm_client = build_llm_client(routing, settings, model_name, provider)
    except RuntimeError as e:
        # Misconfigured provider (missing API key) - fail the task cleanly
        # rather than crash the worker; the retry/escalation logic in
        # evaluate_batch will decide what happens next.
        db.add(ErrorRecord(task_id=task.id, category=ErrorCategory.UNKNOWN, message=str(e)))
        await db.commit()
        return False, str(e)

    agent_type = task.assigned_agent_type or AgentType.CODER
    agent_run = AgentRun(
        task_id=task.id,
        status="running",
        model_tier=routing.tier,
        model_used=model_name,
        decision_summary=routing.reason,
        started_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(agent_run)

    await event_service.publish_event(
        db, redis, task.project_id, ProjectEventType.AGENT_STARTED,
        {"task_id": str(task.id), "agent_run_id": str(agent_run.id), "agent_type": agent_type.value, "model": model_name},
    )

    context_input = await _gather_context_inputs(db, task)
    context = context_manager.build_task_context(context_input)

    agent = build_agent(agent_type, llm_client, db, task.project_id, settings, task_id=task.id)
    result = await agent.run(context.to_prompt())

    for tc in result.tool_calls_made:
        db.add(ToolCall(
            agent_run_id=agent_run.id, tool_name=tc.tool_name, input=tc.args,
            output=tc.result.output if isinstance(tc.result.output, (dict, list, str, int, float, bool, type(None))) else str(tc.result.output),
            success=tc.result.success, error=tc.result.error, execution_time_ms=tc.result.execution_time_ms,
        ))
        if tc.tool_name == "file_writer" and tc.result.success:
            await event_service.publish_event(
                db, redis, task.project_id, ProjectEventType.FILE_MODIFIED,
                {"path": tc.args.get("path"), "task_id": str(task.id)},
            )
        await event_service.publish_event(
            db, redis, task.project_id, ProjectEventType.TOOL_CALLED,
            {"tool": tc.tool_name, "success": tc.result.success, "task_id": str(task.id)},
        )

    await token_service.record_usage(
        db, task.project_id, model_name, provider,
        result.usage.input_tokens, result.usage.output_tokens,
        task_id=task.id, agent_run_id=agent_run.id,
    )

    agent_run.tokens_input = result.usage.input_tokens
    agent_run.tokens_output = result.usage.output_tokens
    agent_run.output_summary = (result.final_content or "")[:2000]
    agent_run.finished_at = dt.datetime.now(dt.timezone.utc)

    if result.hit_iteration_limit:
        agent_run.status = "failed"
        await db.commit()
        message = f"Agent '{agent_type.value}' hit the {settings.AGENT_TOOL_LOOP_MAX_ITERATIONS}-iteration tool-loop limit without finishing."
        db.add(ErrorRecord(task_id=task.id, agent_run_id=agent_run.id, category=ErrorCategory.UNKNOWN, message=message))
        await db.commit()
        return False, message

    failed_tool_calls = [tc for tc in result.tool_calls_made if not tc.result.success]
    if failed_tool_calls and agent_type in (AgentType.CODER, AgentType.DEBUGGER):
        # A coder/debugger whose final tool calls included failures (e.g.
        # a test_runner call that failed) is treated as a failed task -
        # classify the most recent failure so retry logic has something
        # concrete to act on.
        last_failure = failed_tool_calls[-1]
        category = classify_error(last_failure.result.error or "")
        agent_run.status = "completed_with_errors"
        await db.commit()
        db.add(ErrorRecord(
            task_id=task.id, agent_run_id=agent_run.id, category=category,
            message=last_failure.result.error or "Tool call failed with no message.",
        ))
        await db.commit()
        return False, last_failure.result.error or "A tool call failed."

    agent_run.status = "completed"
    await db.commit()
    return True, result.final_content or "(agent produced no summary)"


async def execute_task(db: AsyncSession, redis: Redis | None, settings: Settings, task_id: uuid.UUID) -> None:
    task = await task_service.get_task(db, task_id)
    if task is None:
        return

    await task_service.mark_running(db, task_id)
    await db.refresh(task)  # picks up the bumped attempt_count

    routing = model_router.route_task(
        task.task_type,
        attempt_count=task.attempt_count,
        prior_attempt_failed=task.attempt_count > 1,
    )

    if not routing.requires_llm:
        success, summary = await _execute_deterministic_task(db, redis, settings, task)
    else:
        success, summary = await _execute_agent_task(db, redis, settings, task, routing)

    if success:
        await task_service.mark_completed(db, task_id)
        await event_service.publish_event(
            db, redis, task.project_id, ProjectEventType.TASK_SUCCEEDED,
            {"task_id": str(task_id), "title": task.title, "summary": summary[:500]},
        )
    else:
        await task_service.mark_failed(db, task_id)
        await event_service.publish_event(
            db, redis, task.project_id, ProjectEventType.TASK_FAILED,
            {"task_id": str(task_id), "title": task.title, "summary": summary[:500]},
        )
