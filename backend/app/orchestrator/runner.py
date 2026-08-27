"""
ProjectRunner - the production implementation of `GraphDependencies`.
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
    AgentType, ApprovalType, ProjectEventType, ProjectStatus, TaskStatus,
)
from app.models.error import ErrorRecord
from app.models.plan import ProjectPlan
from app.core.constants import ErrorCategory
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
    """The Planner agent's response could not be parsed/validated. Caught
    by ProjectRunner.run()/run_or_resume()'s top-level wrapper, which
    marks the project FAILED with a readable reason instead of leaving
    it stuck at whatever status it last had."""


class ProjectRunner:
    def __init__(self, project_id: uuid.UUID, db: AsyncSession, redis: Redis | None, settings: Settings, enqueue_task: EnqueueFn):
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
        await token_service.record_usage(self.db, self.project_id, model_name, provider, result.usage.input_tokens, result.usage.output_tokens)
        return result.final_content or ""

    async def _run_planner_json_call(self, kind: str, prompt: str) -> Any:
        """FIX (Bug #3 in the report, "No Auto-Retry"): a Planner call
        that returns slightly malformed JSON (a missing comma, an
        unescaped quote - the kind of thing LLMs occasionally produce on
        a large structured generation) used to raise PlannerOutputError
        immediately, with no attempt to have the model correct itself.
        That exception used to propagate all the way out of
        run_project_job uncaught (see the ProjectRunner.run/run_or_resume
        fix below for the other half of this).

        Now: on a JSONDecodeError, send the parser's own error plus the
        invalid output straight back to the model and ask it to resend
        ONLY corrected JSON, up to `PLANNER_JSON_REPAIR_ATTEMPTS` times
        (default 2) before giving up.
        """
        raw = await self._run_planner_call(kind, prompt)
        last_error: Exception | None = None
        max_attempts = self.settings.PLANNER_JSON_REPAIR_ATTEMPTS

        for attempt in range(max_attempts + 1):
            try:
                return json.loads(_strip_json_fences(raw))
            except json.JSONDecodeError as e:
                last_error = e
                if attempt >= max_attempts:
                    break
                repair_prompt = (
                    "Your previous response was not valid JSON and could not be parsed. "
                    f"The parser reported: {e}\n\n"
                    "Re-send ONLY the corrected JSON - no prose, no markdown code fences, no explanation.\n\n"
                    f"Your previous response was:\n{raw[:4000]}"
                )
                raw = await self._run_planner_call(f"{kind}_repair_{attempt + 1}", repair_prompt)

        raise PlannerOutputError(
            f"Planner ({kind}) did not return valid JSON after {max_attempts + 1} attempt(s): {last_error}\nRaw: {raw[:500]}"
        )

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

        from app.models.file import Artifact

        artifact = Artifact(project_id=self.project_id, artifact_type="summary", content_ref=json.dumps(analysis)[:4000])
        self.db.add(artifact)
        await self.db.commit()

        return {"log": log_event(state, "Requirement analysis complete."), "iteration": state.get("iteration", 0) + 1}

    async def plan_architecture(self, state: ProjectGraphState) -> dict:
        from sqlalchemy import select
        from app.models.file import Artifact

        result = await self.db.execute(select(Artifact).where(Artifact.project_id == self.project_id, Artifact.artifact_type == "summary").order_by(Artifact.created_at.desc()))
        analysis_artifact = result.scalars().first()

        prompt = (
            "Based on this requirement analysis, propose a concise architecture. Respond with ONLY a JSON object: "
            '{"architecture_summary": "...", "tech_stack": {...}, "milestones": ["..."]}.\n\n'
            f"Requirement analysis:\n{analysis_artifact.content_ref if analysis_artifact else '(none)'}"
        )
        architecture = await self._run_planner_json_call("architecture_planning", prompt)

        plan = ProjectPlan(
            project_id=self.project_id, version=1, architecture_summary=architecture.get("architecture_summary", ""),
            tech_stack=architecture.get("tech_stack"), milestones=architecture.get("milestones"), is_active=True,
        )
        self.db.add(plan)
        await self.db.commit()
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.PLAN_READY, {"plan_id": str(plan.id)})

        return {"log": log_event(state, "Architecture plan ready.")}

    async def decompose_tasks(self, state: ProjectGraphState) -> dict:
        from sqlalchemy import select

        plan_result = await self.db.execute(select(ProjectPlan).where(ProjectPlan.project_id == self.project_id, ProjectPlan.is_active.is_(True)))
        plan = plan_result.scalars().first()
        if plan is None:
            raise PlannerOutputError("decompose_tasks was reached with no active ProjectPlan - cannot decompose without an architecture.")

        prompt = (
            "Decompose this architecture into a task DAG. Respond with ONLY a JSON array of objects, each: "
            '{"key": "T1", "title": "...", "description": "...", '
            '"task_type": one of [scaffold, install_dependencies, format_lint, schema_design, '
            "backend_implementation, frontend_implementation, integration, test_authoring, bugfix, "
            'documentation, review], "agent_type": one of [planner, coder, reviewer, debugger, tester, '
            'documenter] or null for deterministic task_types, "depends_on": ["T0", ...], "priority": 0, '
            '"deterministic_payload": {...} or null}. For scaffold/install_dependencies tasks, '
            "deterministic_payload is REQUIRED (see the action shapes you were given) since those tasks run "
            "with zero further LLM calls and only do exactly what the payload says.\n"
            "Prefer many small, independently schedulable tasks.\n\n"
            f"Architecture:\n{plan.architecture_summary if plan else '(none)'}\n"
            f"Tech stack: {json.dumps(plan.tech_stack) if plan and plan.tech_stack else '{}'}"
        )
        proposed = await self._run_planner_json_call("task_decomposition", prompt)
        if not isinstance(proposed, list) or not proposed:
            raise PlannerOutputError("Planner task decomposition did not return a non-empty JSON array.")

        # FIX (Bug: "DAG validation never actually ran"): docs/05-task-dag.md
        # documents that scheduler.validate_dag rejects a cyclic or
        # dangling-dependency graph BEFORE anything is written to the
        # database - but the actual code path never called it. A cyclic
        # or malformed graph from the Planner was written straight into
        # `tasks`/`task_dependencies` as-is; every task in the cycle would
        # then simply never become "ready" (each depends on something
        # that can never complete), and the project would eventually
        # report "stalled" with no indication that the real cause was a
        # bad plan. Validating here, with a clear error, converts that
        # into an immediate, diagnosable PlannerOutputError instead.
        try:
            nodes = [
                scheduler.TaskNode(id=t["key"], status=TaskStatus.PENDING, depends_on=tuple(t.get("depends_on", [])))
                for t in proposed
            ]
            scheduler.validate_dag(nodes)
        except (scheduler.CyclicDependencyError, ValueError, KeyError) as e:
            raise PlannerOutputError(f"Planner task decomposition produced an invalid task graph: {e}") from e

        try:
            await task_service.create_tasks_from_plan(self.db, self.project_id, plan.id, proposed)
        except ValueError as e:
            raise PlannerOutputError(f"Planner task decomposition produced an invalid task graph: {e}") from e

        await project_service.set_status(self.db, self.project_id, ProjectStatus.EXECUTING)
        for t in proposed:
            await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.TASK_CREATED, {"title": t.get("title")})

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

        if stalled:
            # FIX (Bug: "stalled projects had no visible Approval row"):
            # this branch sets needs_human=True and routes the graph to
            # request_human_approval, but previously never created an
            # Approval DB row the way handle_failures/analyze_test_failure
            # do. GET /approvals would show nothing pending even though
            # the project's status was NEEDS_APPROVAL, leaving a human
            # with no way to see why, or to act on it, via the API/UI at
            # all. Guarded on "no existing pending approval" so repeated
            # schedule_batch calls while still stalled don't spam rows.
            existing_pending = await approval_service.get_pending_for_project(self.db, self.project_id)
            if not existing_pending:
                reason = "Every remaining task is blocked on a failed dependency; nothing else can be scheduled."
                await approval_service.create_approval(self.db, self.project_id, ApprovalType.REPEATED_FAILURE, reason)
                await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.APPROVAL_REQUESTED, {"reason": reason})

        return {
            "current_batch_ids": ready, "batch_ready": len(ready) > 0, "project_complete": complete,
            "project_stalled": stalled, "needs_human": stalled,
            "human_reason": "Every remaining task is blocked on a failed dependency." if stalled else state.get("human_reason"),
            "iteration": state.get("iteration", 0) + 1,
            "log": log_event(state, f"Scheduled batch of {len(ready)} task(s); {running_count} already running."),
        }

    async def dispatch_batch(self, state: ProjectGraphState) -> dict:
        batch_ids = state.get("current_batch_ids", [])
        for raw_id in batch_ids:
            task_id = uuid.UUID(raw_id)
            await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.TASK_READY, {"task_id": raw_id})
            await self.enqueue_task(task_id)
        return {"log": log_event(state, f"Dispatched {len(batch_ids)} task(s) to the worker pool.")}

    async def await_batch(self, state: ProjectGraphState) -> dict:
        batch_ids = [uuid.UUID(i) for i in state.get("current_batch_ids", [])]
        deadline = asyncio.get_event_loop().time() + self.settings.TASK_BATCH_AWAIT_TIMEOUT_SECONDS
        poll_interval = 1.0

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.NEEDS_APPROVAL, TaskStatus.SKIPPED, TaskStatus.BLOCKED}
        while True:
            await self.db.commit()
            self.db.expire_all()

            tasks = [await task_service.get_task(self.db, tid) for tid in batch_ids]
            if all(t is not None and t.status in terminal for t in tasks):
                break
            if asyncio.get_event_loop().time() >= deadline:
                for t in tasks:
                    if t is not None and t.status == TaskStatus.RUNNING:
                        # FIX (Bug: "force-failed timeouts were
                        # misclassified"): this used to only flip status
                        # to FAILED with no ErrorRecord at all. The next
                        # handle_failures call would then look up "the
                        # latest ErrorRecord for this task", find none,
                        # and fall back to classify_error("") ->
                        # ErrorCategory.UNKNOWN - which decide_recovery
                        # treats as needing Debug-agent escalation, not a
                        # transient retry. A batch-await timeout IS
                        # exactly the transient case
                        # (ErrorCategory.TIMEOUT) the recovery policy
                        # already has a dedicated "retry with backoff"
                        # path for; losing that information at the point
                        # of failure made every such timeout skip
                        # straight past a plain retry.
                        self.db.add(ErrorRecord(
                            task_id=t.id, category=ErrorCategory.TIMEOUT,
                            message=f"Task exceeded the batch await timeout ({self.settings.TASK_BATCH_AWAIT_TIMEOUT_SECONDS}s) and was force-failed.",
                        ))
                        await task_service.mark_failed(self.db, t.id)
                break
            await asyncio.sleep(poll_interval)

        return {"log": log_event(state, f"Batch of {len(batch_ids)} task(s) resolved.")}

    async def evaluate_batch(self, state: ProjectGraphState) -> dict:
        batch_ids = [uuid.UUID(i) for i in state.get("current_batch_ids", [])]
        tasks = [await task_service.get_task(self.db, tid) for tid in batch_ids]
        had_failures = any(t is not None and t.status == TaskStatus.FAILED for t in tasks)
        return {"batch_had_new_failures": had_failures, "log": log_event(state, "Evaluated batch results." + (" Failures detected." if had_failures else ""))}

    async def handle_failures(self, state: ProjectGraphState) -> dict:
        from sqlalchemy import select

        batch_ids = [uuid.UUID(i) for i in state.get("current_batch_ids", [])]
        needs_human = False
        human_reason = None
        for task_id in batch_ids:
            task = await task_service.get_task(self.db, task_id)
            if task is None or task.status != TaskStatus.FAILED:
                continue
            err_result = await self.db.execute(select(ErrorRecord).where(ErrorRecord.task_id == task_id).order_by(ErrorRecord.created_at.desc()))
            latest_error = err_result.scalars().first()
            category = latest_error.category if latest_error else classify_error("")
            # FIX (Bug: "off-by-one on MAX_TASK_RETRIES" / "tier
            # escalation never fires"): decide_recovery's own docstring
            # and tests define attempt_count as "number of attempts
            # ALREADY MADE, including the one that just failed". This
            # call used to pass the raw, not-yet-incremented
            # task.attempt_count (which only counts PRIOR retries, not
            # this failure), so with the documented
            # MAX_TASK_RETRIES=3, a task actually got 4 real execution
            # attempts before human_approval fired, not 3 as the code's
            # own reason string ("after three unsuccessful attempts")
            # claims. Passing attempt_count + 1 here fixes that off-by-
            # one, and (via the matching fix in agent_execution_service)
            # is also what makes model-tier escalation on retry able to
            # fire at all.
            decision = decide_recovery(
                category, attempt_count=task.attempt_count + 1, max_attempts=task.max_attempts,
                backoff_base_seconds=self.settings.RETRY_BACKOFF_BASE_SECONDS, backoff_max_seconds=self.settings.RETRY_BACKOFF_MAX_SECONDS,
            )
            if decision.action == "retry":
                if decision.backoff_seconds:
                    await asyncio.sleep(min(decision.backoff_seconds, 5.0))
                await task_service.reset_for_retry(self.db, task_id, escalate_to_debugger=False)
            elif decision.action == "escalate_to_debugger":
                await task_service.reset_for_retry(self.db, task_id, escalate_to_debugger=True)
            else:
                await task_service.mark_needs_approval(self.db, task_id)
                await approval_service.create_approval(self.db, self.project_id, ApprovalType.REPEATED_FAILURE, decision.reason, task_id=task_id)
                await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.APPROVAL_REQUESTED, {"task_id": str(task_id), "reason": decision.reason})
                needs_human = True
                human_reason = decision.reason

        return {"needs_human": needs_human, "human_reason": human_reason, "log": log_event(state, "Applied failure-recovery decisions to the batch.")}

    async def run_integration_tests(self, state: ProjectGraphState) -> dict:
        await project_service.set_status(self.db, self.project_id, ProjectStatus.TESTING)
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.TESTS_STARTED, {})
        test_run = await test_service.run_integration_tests(self.db, self.project_id, self.settings)
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.TESTS_FINISHED, {"status": test_run.status})
        return {"test_status": "passed" if test_run.status == "passed" else "failed", "log": log_event(state, f"Integration tests: {test_run.status}.")}

    async def analyze_test_failure(self, state: ProjectGraphState) -> dict:
        retry_count = state.get("integration_test_retry_count", 0) + 1
        max_retries = state.get("max_integration_test_retries", self.settings.MAX_TASK_RETRIES)

        if retry_count > max_retries:
            reason = f"Integration tests failed {retry_count - 1} time(s); reached the configured retry limit."
            await approval_service.create_approval(self.db, self.project_id, ApprovalType.REPEATED_FAILURE, reason)
            await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.APPROVAL_REQUESTED, {"reason": reason})
            return {"needs_human": True, "human_reason": reason, "integration_test_retry_count": retry_count, "log": log_event(state, reason)}

        from app.core.constants import TaskType

        active_plan_id = await self._active_plan_id()
        await task_service.create_tasks_from_plan(
            self.db, self.project_id, plan_id=active_plan_id,
            proposed_tasks=[{
                "key": f"integration-fix-{retry_count}", "title": "Fix integration test failures",
                "description": "The integration test suite failed. Investigate and fix the failing tests/code.",
                "task_type": TaskType.BUGFIX.value, "agent_type": AgentType.DEBUGGER.value, "depends_on": [], "priority": 100,
            }],
        )
        return {"needs_human": False, "integration_test_retry_count": retry_count, "log": log_event(state, f"Queued a fix task for integration failures (attempt {retry_count}/{max_retries}).")}

    async def request_human_approval(self, state: ProjectGraphState) -> dict:
        await project_service.set_status(self.db, self.project_id, ProjectStatus.NEEDS_APPROVAL)
        return {"log": log_event(state, f"Paused for human approval: {state.get('human_reason')}")}

    async def finalize_project(self, state: ProjectGraphState) -> dict:
        await project_service.set_status(self.db, self.project_id, ProjectStatus.COMPLETED)
        await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.PROJECT_COMPLETED, {})
        return {"log": log_event(state, "Project finalized.")}

    async def _active_plan_id(self) -> uuid.UUID | None:
        from sqlalchemy import select

        result = await self.db.execute(select(ProjectPlan).where(ProjectPlan.project_id == self.project_id, ProjectPlan.is_active.is_(True)))
        plan = result.scalars().first()
        return plan.id if plan else None

    async def _mark_project_failed(self, exc: Exception) -> None:
        """FIX (systemic bug: ProjectStatus.FAILED was never reachable):
        ProjectStatus.FAILED is defined, tested for (implicitly, via the
        frontend's StatusBadge), and never once assigned anywhere in the
        original codebase. Every graph node that can legitimately fail
        (a crashed DB call, an exhausted planner-JSON-repair loop, an
        invalid task graph) simply let the exception propagate out of
        `ainvoke`, back through run_project_job, where it was logged and
        re-raised - leaving `project.status` stuck at whatever it was
        (usually "planning" or "executing") forever, with nothing in the
        UI ever telling the person who submitted the project that it had
        actually died. This wraps the graph invocation so any unhandled
        exception is captured as a real, visible terminal state before
        being re-raised (so ARQ's own retry/logging behaviour for the job
        itself is unaffected)."""
        try:
            await project_service.set_status(self.db, self.project_id, ProjectStatus.FAILED)
            await event_service.publish_event(self.db, self.redis, self.project_id, ProjectEventType.PROJECT_FAILED, {"reason": str(exc)[:500]})
        except Exception:
            # Best-effort - do not mask the original exception if even
            # recording the failure fails (e.g. a broken session).
            pass

    # -- entrypoints ------------------------------------------------------

    async def run(self) -> ProjectGraphState:
        from app.orchestrator.graph import build_graph

        try:
            app = build_graph(self)
            state = initial_state(str(self.project_id), max_integration_test_retries=self.settings.MAX_TASK_RETRIES)
            return await app.ainvoke(state, config={"recursion_limit": 500})
        except Exception as exc:
            await self._mark_project_failed(exc)
            raise

    async def run_from_decompose(self) -> ProjectGraphState:
        """Entry point used by run_or_resume when a plan exists but task
        decomposition never completed - see
        app/orchestrator/graph.py::build_decompose_resume_graph."""
        from app.orchestrator.graph import build_decompose_resume_graph

        try:
            app = build_decompose_resume_graph(self)
            state = initial_state(str(self.project_id), max_integration_test_retries=self.settings.MAX_TASK_RETRIES)
            return await app.ainvoke(state, config={"recursion_limit": 500})
        except Exception as exc:
            await self._mark_project_failed(exc)
            raise

    async def run_or_resume(self) -> ProjectGraphState:
        from app.orchestrator.graph import build_resume_graph

        plan_id = await self._active_plan_id()
        if plan_id is None:
            return await self.run()

        # FIX (Bug #4 in the report, "The Resume Bug"): this used to be
        #     if plan_id is None: return await self.run()
        #     <always go straight to build_resume_graph from here>
        # A ProjectPlan is created by plan_architecture, which runs
        # BEFORE decompose_tasks. If the worker crashed (or the
        # planner's JSON never parsed, before the repair-loop fix above
        # existed) partway through decompose_tasks, the project was left
        # with an active plan and ZERO tasks. Resuming in that state used
        # to jump straight to schedule_batch, which - given zero tasks -
        # immediately reports "stalled" and routes to
        # request_human_approval with nothing for a human to actually
        # look at or act on. Checking whether any tasks actually exist,
        # and if not, resuming from decomposition instead of scheduling,
        # closes that gap.
        has_tasks = await task_service.project_has_tasks(self.db, self.project_id)
        if not has_tasks:
            return await self.run_from_decompose()

        try:
            app = build_resume_graph(self)
            state = initial_state(str(self.project_id), max_integration_test_retries=self.settings.MAX_TASK_RETRIES)
            return await app.ainvoke(state, config={"recursion_limit": 500})
        except Exception as exc:
            await self._mark_project_failed(exc)
            raise
