"""
ProjectRunner - the production implementation of `GraphDependencies`
(app/orchestrator/graph.py). One instance drives one project's execution:
construct it, call `.run()`, and it walks the compiled LangGraph app from
requirement analysis through to finalization (or a human-approval pause).

Each method here corresponds 1:1 to a graph node. They are intentionally
short - the real logic lives in the service modules (task_service,
event_service, token_service, agent_execution_service); this class's job
is to sequence those calls and translate their results into the small
set of routing-relevant fields the graph's conditional edges look at
(batch_ready, project_complete, needs_human, test_status, ...).
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import build_agent
from app.core.config import Settings
from app.core.constants import (
    AgentType,
    ApprovalType,
    ProjectEventType,
    ProjectStatus,
    TaskStatus,
)
from app.models.plan import ProjectPlan
from app.orchestrator import model_router, scheduler
from app.orchestrator.failure_recovery import classify_error, decide_recovery
from app.orchestrator.llm_clients import build_llm_client, resolve_model_for_tier
from app.orchestrator.state import ProjectGraphState, initial_state, log_event
from app.services import approval_service, event_service, project_service, task_service, test_service, token_service

EnqueueFn = Callable[[uuid.UUID], Awaitable[None]]


def _strip_json_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


class PlannerOutputError(ValueError):
    """The Planner agent's response could not be parsed as the JSON shape
    the calling node needed. Callers treat this the same as any other
    task failure - it goes through the same classify/retry/escalate path,
    it just happens before any Task rows exist yet."""


class ProjectRunner:
    def __init__(
        self,
        project_id: uuid.UUID,
        db: AsyncSession,
        redis: Redis | None,
        settings: Settings,
        enqueue_task: EnqueueFn,
    ):
        self.project_id = project_id
        self.db = db
        self.redis = redis
        self.settings = settings
        self.enqueue_task = enqueue_task

    # -- shared planner-call helper -----------------------------------

    async def _run_planner_call(self, kind: str, prompt: str) -> str:
        routing = model_router.route_planning_call(kind)
        model_name, provider = resolve_model_for_tier(routing.tier, self.settings)
        llm_client = build_llm_client(routing, self.settings, model_name, provider)
        agent = build_agent(AgentType.PLANNER, llm_client, self.db, self.project_id, self.settings)
        result = await agent.run(prompt)
        await token_service.record_usage(
            self.db, self.project_id, model_name, provider,
            result.usage.input_tokens, result.usage.output_tokens,
        )
        return result.final_content or ""

    async def _run_planner_json_call(self, kind: str, prompt: str) -> Any:
        raw = await self._run_planner_call(kind, prompt)
        try:
            return json.loads(_strip_json_fences(raw))
        except json.JSONDecodeError as e:
            raise PlannerOutputError(f"Planner ({kind}) did not return valid JSON: {e}\nRaw: {raw[:500]}") from e

    # -- graph nodes ----------------------------------------------------

    async def analyze_requirement(self, state: ProjectGraphState) -> dict:
        requirement = await project_service.get_active_requirement(self.db, self.project_id)
        await project_service.set_status(self.db, self.project_id, ProjectStatus.PLANNING)
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.PLANNER_STARTED, {})

        prompt = (
            "Analyze this software requirement. Respond with ONLY a JSON object: "
            '{"goals": [...], "constraints": [...], "assumptions": [...]}.\n\n'
            f"Requirement:\n{requirement.raw_text if requirement else '(none provided)'}\n\n"
            f"Explicit constraints: {json.dumps(requirement.constraints) if requirement and requirement.constraints else '{}'}"
        )
        analysis = await self._run_planner_json_call("requirement_analysis", prompt)

        from app.models.file import Artifact  # local import keeps this node's DB touches close together

        artifact = Artifact(
            project_id=self.project_id, artifact_type="summary",
            content_ref=json.dumps(analysis)[:4000],
        )
        self.db.add(artifact)
        await self.db.commit()

        return {"log": log_event(state, "Requirement analysis complete."), "iteration": state.get("iteration", 0) + 1}

    async def plan_architecture(self, state: ProjectGraphState) -> dict:
        from sqlalchemy import select

        from app.models.file import Artifact

        result = await self.db.execute(
            select(Artifact)
            .where(Artifact.project_id == self.project_id, Artifact.artifact_type == "summary")
            .order_by(Artifact.created_at.desc())
        )
        analysis_artifact = result.scalars().first()

        prompt = (
            "Based on this requirement analysis, propose a concise architecture. Respond with ONLY a JSON object: "
            '{"architecture_summary": "...", "tech_stack": {...}, "milestones": ["..."]}.\n\n'
            f"Requirement analysis:\n{analysis_artifact.content_ref if analysis_artifact else '(none)'}"
        )
        architecture = await self._run_planner_json_call("architecture_planning", prompt)

        plan = ProjectPlan(
            project_id=self.project_id,
            version=1,
            architecture_summary=architecture.get("architecture_summary", ""),
            tech_stack=architecture.get("tech_stack"),
            milestones=architecture.get("milestones"),
            is_active=True,
        )
        self.db.add(plan)
        await self.db.commit()
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.PLAN_READY, {"plan_id": str(plan.id)})

        return {"log": log_event(state, "Architecture plan ready.")}

    async def decompose_tasks(self, state: ProjectGraphState) -> dict:
        from sqlalchemy import select

        plan_result = await self.db.execute(
            select(ProjectPlan).where(ProjectPlan.project_id == self.project_id, ProjectPlan.is_active.is_(True))
        )
        plan = plan_result.scalars().first()

        prompt = (
            "Decompose this architecture into a task DAG. Respond with ONLY a JSON array of objects, each: "
            '{"key": "T1", "title": "...", "description": "...", '
            '"task_type": one of [scaffold, install_dependencies, format_lint, schema_design, '
            "backend_implementation, frontend_implementation, integration, test_authoring, bugfix, "
            'documentation, review], "agent_type": one of [planner, coder, reviewer, debugger, tester, '
            'documenter] or null for deterministic task_types, "depends_on": ["T0", ...], "priority": 0, '
            '"deterministic_payload": {...} or null}.\n'
            "Prefer many small, independently schedulable tasks. Mark mechanical steps with their "
            "deterministic task_type so no LLM call is wasted on them.\n\n"
            f"Architecture:\n{plan.architecture_summary if plan else '(none)'}\n"
            f"Tech stack: {json.dumps(plan.tech_stack) if plan and plan.tech_stack else '{}'}"
        )
        proposed = await self._run_planner_json_call("task_decomposition", prompt)
        if not isinstance(proposed, list) or not proposed:
            raise PlannerOutputError("Planner task decomposition did not return a non-empty JSON array.")

        await task_service.create_tasks_from_plan(self.db, self.project_id, plan.id, proposed)
        await project_service.set_status(self.db, self.project_id, ProjectStatus.EXECUTING)
        for t in proposed:
            await event_service.publish_event(
                self.db, self.redis, self.project_id, ProjectEventType.TASK_CREATED, {"title": t.get("title")}
            )

        return {"log": log_event(state, f"Decomposed into {len(proposed)} tasks.")}

    async def schedule_batch(self, state: ProjectGraphState) -> dict:
        nodes = await task_service.to_scheduler_nodes(self.db, self.project_id)

        newly_blocked = scheduler.get_newly_blocked_tasks(nodes)
        if newly_blocked:
            await task_service.set_blocked(self.db, newly_blocked)
            nodes = await task_service.to_scheduler_nodes(self.db, self.project_id)

        running_count = len([n for n in nodes if n.status == TaskStatus.RUNNING])
        ready = scheduler.get_ready_tasks(nodes, running_count=running_count, max_parallel=self.settings.MAX_PARALLEL_TASKS)
        complete = scheduler.is_project_complete(nodes)
        stalled = scheduler.is_stalled(nodes, running_count=running_count)

        return {
            "current_batch_ids": ready,
            "batch_ready": len(ready) > 0,
            "project_complete": complete,
            "project_stalled": stalled,
            "needs_human": stalled,
            "human_reason": "Every remaining task is blocked on a failed dependency." if stalled else state.get("human_reason"),
            "iteration": state.get("iteration", 0) + 1,
            "log": log_event(state, f"Scheduled batch of {len(ready)} task(s); {running_count} already running."),
        }

    async def dispatch_batch(self, state: ProjectGraphState) -> dict:
        batch_ids = state.get("current_batch_ids", [])
        for raw_id in batch_ids:
            task_id = uuid.UUID(raw_id)
            await event_service.publish_event(
                self.db, self.redis, self.project_id, ProjectEventType.TASK_READY, {"task_id": raw_id}
            )
            await self.enqueue_task(task_id)
        return {"log": log_event(state, f"Dispatched {len(batch_ids)} task(s) to the worker pool.")}

    async def await_batch(self, state: ProjectGraphState) -> dict:
        batch_ids = [uuid.UUID(i) for i in state.get("current_batch_ids", [])]
        deadline = asyncio.get_event_loop().time() + self.settings.TASK_BATCH_AWAIT_TIMEOUT_SECONDS
        poll_interval = 1.0

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.NEEDS_APPROVAL, TaskStatus.SKIPPED, TaskStatus.BLOCKED}
        while True:
            # End the current transaction so we can see changes committed by workers
            await self.db.commit()
            # Force SQLAlchemy to drop cached task statuses so the next query fetches fresh rows
            self.db.expire_all()
            
            tasks = [await task_service.get_task(self.db, tid) for tid in batch_ids]
            if all(t is not None and t.status in terminal for t in tasks):
                break
            if asyncio.get_event_loop().time() >= deadline:
                # A batch that never resolves (a stuck worker, a crashed
                # job) must not hang the orchestrator forever - treat the
                # still-running tasks as failed so recovery logic can act.
                for t in tasks:
                    if t is not None and t.status == TaskStatus.RUNNING:
                        await task_service.mark_failed(self.db, t.id)
                break
            await asyncio.sleep(poll_interval)

        return {"log": log_event(state, f"Batch of {len(batch_ids)} task(s) resolved.")}

    async def evaluate_batch(self, state: ProjectGraphState) -> dict:
        batch_ids = [uuid.UUID(i) for i in state.get("current_batch_ids", [])]
        tasks = [await task_service.get_task(self.db, tid) for tid in batch_ids]
        had_failures = any(t is not None and t.status == TaskStatus.FAILED for t in tasks)
        return {
            "batch_had_new_failures": had_failures,
            "log": log_event(state, "Evaluated batch results." + (" Failures detected." if had_failures else "")),
        }

    async def handle_failures(self, state: ProjectGraphState) -> dict:
        from sqlalchemy import select

        from app.models.error import ErrorRecord

        batch_ids = [uuid.UUID(i) for i in state.get("current_batch_ids", [])]
        needs_human = False
        human_reason = None
        for task_id in batch_ids:
            task = await task_service.get_task(self.db, task_id)
            if task is None or task.status != TaskStatus.FAILED:
                continue
            err_result = await self.db.execute(
                select(ErrorRecord).where(ErrorRecord.task_id == task_id).order_by(ErrorRecord.created_at.desc())
            )
            latest_error = err_result.scalars().first()
            category = latest_error.category if latest_error else classify_error("")
            decision = decide_recovery(
                category, attempt_count=task.attempt_count, max_attempts=task.max_attempts,
                backoff_base_seconds=self.settings.RETRY_BACKOFF_BASE_SECONDS,
                backoff_max_seconds=self.settings.RETRY_BACKOFF_MAX_SECONDS,
            )
            if decision.action == "retry":
                if decision.backoff_seconds:
                    await asyncio.sleep(min(decision.backoff_seconds, 5.0))  # bounded: this is an orchestration loop, not a background timer
                await task_service.reset_for_retry(self.db, task_id, escalate_to_debugger=False)
            elif decision.action == "escalate_to_debugger":
                await task_service.reset_for_retry(self.db, task_id, escalate_to_debugger=True)
            else:  # human_approval
                await task_service.mark_needs_approval(self.db, task_id)
                await approval_service.create_approval(
                    self.db, self.project_id, ApprovalType.REPEATED_FAILURE, decision.reason, task_id=task_id,
                )
                await event_service.publish_event(
                    self.db, self.redis, self.project_id, ProjectEventType.APPROVAL_REQUESTED,
                    {"task_id": str(task_id), "reason": decision.reason},
                )
                needs_human = True
                human_reason = decision.reason

        return {
            "needs_human": needs_human,
            "human_reason": human_reason,
            "log": log_event(state, "Applied failure-recovery decisions to the batch."),
        }

    async def run_integration_tests(self, state: ProjectGraphState) -> dict:
        await project_service.set_status(self.db, self.project_id, ProjectStatus.TESTING)
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.TESTS_STARTED, {})
        test_run = await test_service.run_integration_tests(self.db, self.project_id, self.settings)
        await event_service.publish_event(
            self.db, self.redis, self.project_id, ProjectEventType.TESTS_FINISHED, {"status": test_run.status}
        )
        return {
            "test_status": "passed" if test_run.status == "passed" else "failed",
            "log": log_event(state, f"Integration tests: {test_run.status}."),
        }

    async def analyze_test_failure(self, state: ProjectGraphState) -> dict:
        retry_count = state.get("integration_test_retry_count", 0) + 1
        max_retries = state.get("max_integration_test_retries", self.settings.MAX_TASK_RETRIES)

        if retry_count > max_retries:
            reason = f"Integration tests failed {retry_count - 1} time(s); reached the configured retry limit."
            await approval_service.create_approval(self.db, self.project_id, ApprovalType.REPEATED_FAILURE, reason)
            await event_service.publish_event(
                self.db, self.redis, self.project_id, ProjectEventType.APPROVAL_REQUESTED, {"reason": reason}
            )
            return {
                "needs_human": True,
                "human_reason": reason,
                "integration_test_retry_count": retry_count,
                "log": log_event(state, reason),
            }

        from app.core.constants import TaskType

        active_plan_id = await self._active_plan_id()
        await task_service.create_tasks_from_plan(
            self.db, self.project_id,
            plan_id=active_plan_id,
            proposed_tasks=[{
                "key": f"integration-fix-{retry_count}",
                "title": "Fix integration test failures",
                "description": "The integration test suite failed. Investigate and fix the failing tests/code.",
                "task_type": TaskType.BUGFIX.value,
                "agent_type": AgentType.DEBUGGER.value,
                "depends_on": [],
                "priority": 100,  # highest priority: fixing a broken build always jumps the queue
            }],
        )
        return {
            "needs_human": False,
            "integration_test_retry_count": retry_count,
            "log": log_event(state, f"Queued a fix task for integration failures (attempt {retry_count}/{max_retries})."),
        }

    async def request_human_approval(self, state: ProjectGraphState) -> dict:
        await project_service.set_status(self.db, self.project_id, ProjectStatus.NEEDS_APPROVAL)
        return {"log": log_event(state, f"Paused for human approval: {state.get('human_reason')}")}

    async def finalize_project(self, state: ProjectGraphState) -> dict:
        await project_service.set_status(self.db, self.project_id, ProjectStatus.COMPLETED)
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.PROJECT_COMPLETED, {})
        return {"log": log_event(state, "Project finalized.")}

    async def _active_plan_id(self) -> uuid.UUID | None:
        from sqlalchemy import select

        result = await self.db.execute(
            select(ProjectPlan).where(ProjectPlan.project_id == self.project_id, ProjectPlan.is_active.is_(True))
        )
        plan = result.scalars().first()
        return plan.id if plan else None

    # -- entrypoints ------------------------------------------------------

    async def run(self) -> ProjectGraphState:
        """Always starts from the top (requirement analysis). Use this
        only for a brand-new project - see `run_or_resume` for the entry
        point that's safe to call repeatedly."""
        from app.orchestrator.graph import build_graph

        app = build_graph(self)
        state = initial_state(str(self.project_id), max_integration_test_retries=self.settings.MAX_TASK_RETRIES)
        result = await app.ainvoke(state, config={"recursion_limit": 500})
        return result

    async def run_or_resume(self) -> ProjectGraphState:
        """The entry point every call site (initial project creation,
        resuming after a human approval) should use. Deciding "fresh
        start vs. resume" is itself deterministic - based on whether an
        active ProjectPlan already exists in Postgres - never inferred
        from in-memory state, since the process handling an approval
        POST is frequently not the same process that started the
        project. Re-running the full graph on an already-planned project
        would re-invoke the Planner and build a second, duplicate task
        DAG, which is exactly the redundant-LLM-call anti-pattern this
        project exists to avoid."""
        from app.orchestrator.graph import build_resume_graph

        plan_id = await self._active_plan_id()
        if plan_id is None:
            return await self.run()

        app = build_resume_graph(self)
        state = initial_state(str(self.project_id), max_integration_test_retries=self.settings.MAX_TASK_RETRIES)
        result = await app.ainvoke(state, config={"recursion_limit": 500})
        return result
