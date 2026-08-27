"""
Executes a single Task end-to-end: either a deterministic mechanical
action (no LLM) or a full agent tool-calling loop.

This file previously had several bugs that made the whole "deterministic
task" mechanism a no-op and silently broke several other documented
features. Each one is called out at its fix site below rather than only
summarized here - see docs/23-design-decisions.md's own stated
philosophy ("a project whose stated purpose is verifiability should be
able to show its own verification process").
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.agents.factory import build_agent
from app.core.config import Settings
from app.core.constants import TaskStatus, TaskType
from app.models.agent import AgentRun
from app.models.error import ErrorRecord
from app.models.task import Task
from app.orchestrator import model_router
from app.orchestrator.failure_recovery import classify_error
from app.orchestrator.llm_clients import build_llm_client, resolve_model_for_tier
from app.services import event_service, token_service
from app.tools.db_tools import FileWriterTool
from app.tools.exec_tools import FormatterTool, ShellCommandRunnerTool

# Task types the model router marks DETERMINISTIC. SCAFFOLD and
# INSTALL_DEPENDENCIES describe real work that has to come from
# somewhere (there is no LLM call at execution time to improvise it), so
# if the Planner didn't attach a deterministic_payload for one of these,
# that is a planning bug, not something to silently paper over.
_MECHANICAL_REQUIRES_PAYLOAD = {TaskType.SCAFFOLD, TaskType.INSTALL_DEPENDENCIES}


def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


async def _execute_deterministic_task(db: AsyncSession, settings: Settings, task: Task) -> None:
    """FIX (the core bug in this report): this function used to be

        task.status = TaskStatus.COMPLETED
        task.completed_at = dt.datetime.utcnow()

    i.e. an empty stub that marked every scaffold/install/format task
    COMPLETED without ever running the mkdir/npm/pip/formatter command
    the Planner asked for. Because these task types are specifically the
    ones routed with requires_llm=False (see model_router.py), nothing
    else in the system ever got a chance to do the work either - it was
    silently skipped, every time, for every project. Downstream Coder
    tasks would then try to write e.g. "backend/main.py" into a project
    that never actually got a "backend/" scaffold, and (depending on the
    agent's own judgement) sometimes fall back to writing into the
    project root instead.

    This now actually interprets `task.deterministic_payload` (a
    Planner-authored, structured description of the mechanical step -
    see docs on Task.deterministic_payload and app/agents/planner.py).
    """
    payload = task.deterministic_payload or {}
    action = payload.get("action")

    if action is None and task.task_type == TaskType.FORMAT_LINT:
        action = "format"

    if action == "create_files":
        files = payload.get("files") or {}
        if not files:
            raise RuntimeError(f"Task '{task.title}' is a create_files scaffold task with an empty 'files' map - nothing to write.")
        writer = FileWriterTool(db, task.project_id, created_by_task_id=task.id)
        for path, content in files.items():
            result = await writer.run(path=path, content=content if content is not None else "")
            if not result.success:
                raise RuntimeError(f"create_files failed for '{path}': {result.error}")

    elif action == "install":
        manager = (payload.get("manager") or "npm").lower()
        packages = payload.get("packages") or []
        if manager == "npm":
            argv = ["npm", "install", *packages] if packages else ["npm", "install"]
        elif manager in ("pip", "pip3"):
            argv = ["pip3", "install", *packages] if packages else ["pip3", "install", "-r", "requirements.txt"]
        else:
            raise RuntimeError(f"Unsupported install manager '{manager}' in task '{task.title}'.")
        tool = ShellCommandRunnerTool(db, task.project_id, settings)
        result = await tool.run(argv=argv, network_disabled=not bool(payload.get("network", True)))
        if not result.success:
            raise RuntimeError(f"Dependency install failed for task '{task.title}': {result.error}")

    elif action == "run_command":
        argv = payload.get("argv")
        if not argv:
            raise RuntimeError(f"Task '{task.title}' is a run_command scaffold task with no 'argv'.")
        if argv[0] == "mkdir":
            # This project's workspace is a DB table of (path -> content)
            # rows, not a real filesystem - "directories" are just path
            # prefixes and never need to be created up front. A real
            # `mkdir` inside the sandbox would also be pointless, since
            # the sandbox workspace is a throwaway directory torn down
            # after every tool call. Treat it as a deliberate no-op
            # instead of either silently completing without saying why,
            # or failing on a command that was never going to do anything.
            pass
        else:
            if argv and argv[0] in ("npm", "npx") and len(argv) > 1:
                # Prevent interactive prompts from hanging the sandbox
                if argv[0] == "npm" and argv[1] == "create" and "--yes" not in argv:
                    argv.insert(2, "--yes")
                elif argv[0] == "npx" and "--yes" not in argv:
                    argv.insert(1, "--yes")
                    
            tool = ShellCommandRunnerTool(db, task.project_id, settings)
            result = await tool.run(argv=argv, network_disabled=not bool(payload.get("network", False)))
            if not result.success:
                raise RuntimeError(f"run_command failed for task '{task.title}': {result.error}")

    elif action == "format":
        tool = FormatterTool(db, task.project_id, settings)
        result = await tool.run()
        if not result.success:
            raise RuntimeError(f"format_lint failed for task '{task.title}': {result.error}")

    elif action is None:
        if task.task_type in _MECHANICAL_REQUIRES_PAYLOAD:
            raise RuntimeError(
                f"Task '{task.title}' (task_type={task.task_type.value}) never uses an LLM call at execution "
                "time, but the Planner did not attach a deterministic_payload describing what to actually do "
                "(e.g. {'action': 'create_files', 'files': {...}}). Failing loudly here - through the normal "
                "retry/escalate/human-approval path - instead of silently marking it done with nothing changed."
            )
        # No mechanical work is implied for this task_type/payload
        # combination (e.g. a format_lint task on a project with no
        # files yet) - genuinely nothing to do.
    else:
        raise RuntimeError(f"Unknown deterministic action '{action}' for task '{task.title}'.")

    task.status = TaskStatus.COMPLETED
    task.completed_at = _utcnow()


async def execute_task(db: AsyncSession, redis: Redis | None, settings: Settings, task_id: uuid.UUID) -> None:
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalars().first()
    if not task:
        return

    task.status = TaskStatus.RUNNING
    task.started_at = _utcnow()
    await db.commit()

    await event_service.publish_event(db, redis, task.project_id, "TASK_STARTED", {"task_id": str(task.id), "title": task.title})

    agent_run: AgentRun | None = None
    try:
        if task.assigned_agent_type is None:
            await _execute_deterministic_task(db, settings, task)
        else:
            # FIX: attempt_count/prior_attempt_failed wiring. Previously
            # this called `model_router.route_task(task.task_type,
            # task.attempt_count)` with no `prior_attempt_failed` at all.
            # model_router.route_task only escalates the model tier when
            # BOTH `attempt_count > 1` AND `prior_attempt_failed` is
            # True - so with prior_attempt_failed always defaulting to
            # False, tier escalation on retry (extensively documented in
            # docs/08-model-routing.md and docs/04-orchestrator.md) could
            # never fire, no matter how many times a task failed.
            #
            # Task.attempt_count means "number of prior FAILED attempts"
            # (it is only incremented by task_service.reset_for_retry,
            # which only runs after a failure). model_router's own
            # attempt_count convention is 1-indexed ("this is attempt
            # number N"), so the correct translation is attempt_count+1,
            # with prior_attempt_failed simply being "has this task ever
            # failed before" (attempt_count > 0).
            routing = model_router.route_task(
                task.task_type,
                attempt_count=task.attempt_count + 1,
                prior_attempt_failed=task.attempt_count > 0,
            )
            model_name, provider = resolve_model_for_tier(routing.tier, settings)
            llm_client = build_llm_client(routing, settings, model_name, provider)

            agent_run = AgentRun(task_id=task.id, status="running", model_tier=routing.tier, model_used=model_name, started_at=_utcnow())
            db.add(agent_run)
            await db.commit()
            await db.refresh(agent_run)

            # FIX: `task_id=task.id` was previously omitted entirely.
            # build_agent forwards task_id into build_tools_for_agent,
            # which is what tells FileWriterTool which task to attribute
            # a write to (`created_by_task_id`). Without it, every single
            # file any Coder/Debugger/Tester/Documenter agent ever wrote
            # was attributed to created_by_task_id=None, which meant
            # GET /tasks/{id} always reported files_modified=[] - the
            # "what did this task actually change" feature was silently
            # broken for every task in every project.
            agent = build_agent(task.assigned_agent_type, llm_client, db, task.project_id, settings, task_id=task.id)

            # FIX: fold in a human's "Modify & retry" instruction if one
            # was recorded (see task_service.reset_for_retry). Previously
            # ApprovalDecision.modified_instruction was accepted by the
            # API, and then never read back by anything.
            prompt = task.description
            if task.human_instruction_override:
                prompt = f"{task.description}\n\nHuman guidance for this attempt (follow this):\n{task.human_instruction_override}"

            agent_result = await agent.run(prompt)

            agent_run.status = "completed"
            agent_run.finished_at = _utcnow()
            agent_run.tokens_input = agent_result.usage.input_tokens
            agent_run.tokens_output = agent_result.usage.output_tokens
            # FIX: output_summary was declared on the AgentRun model and
            # referenced by docs/07-token-optimization.md (#13, "compact
            # task outputs... capped (2000 chars) before storage as
            # AgentRun.output_summary") and by docs/16-frontend.md (the
            # right panel is supposed to render it) but nothing ever
            # actually assigned it - the "what did the agent decide"
            # panel had no data to show, for every task, ever.
            agent_run.output_summary = (agent_result.final_content or "")[:2000]

            await token_service.record_usage(
                db=db, project_id=task.project_id, model_name=model_name, provider=provider,
                input_tokens=agent_run.tokens_input, output_tokens=agent_run.tokens_output,
                task_id=task.id, agent_run_id=agent_run.id,
            )

            task.status = TaskStatus.COMPLETED
            task.completed_at = _utcnow()

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.completed_at = _utcnow()

        # FIX: if an AgentRun row was already created before the
        # exception (e.g. agent.run() itself raised), it previously was
        # left at status="running"/finished_at=None forever - an agent
        # run that crashed looked, permanently, exactly like one that
        # was still in progress.
        if agent_run is not None:
            agent_run.status = "failed"
            agent_run.finished_at = _utcnow()

        category = classify_error(str(e))
        db.add(ErrorRecord(task_id=task.id, category=category, message=str(e)))

    await db.commit()

    status_str = task.status.value if hasattr(task.status, "value") else str(task.status)
    await event_service.publish_event(
        db, redis, task.project_id,
        "TASK_COMPLETED" if task.status == TaskStatus.COMPLETED else "TASK_FAILED",
        {"task_id": str(task.id), "status": status_str},
    )
