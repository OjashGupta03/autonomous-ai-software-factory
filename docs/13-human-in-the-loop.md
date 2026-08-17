# 13 - Human in the Loop

## When the system stops and asks

An `Approval` row (status `pending`) is created, and the current project's orchestrator
run ends at `request_human_approval` (a terminal node - see
[03-agentic-workflow.md](03-agentic-workflow.md)), in exactly these cases:

- A task has failed `MAX_TASK_RETRIES` times (`failure_recovery.decide_recovery` returns
  `human_approval`) - `ApprovalType.REPEATED_FAILURE`.
- Integration tests have failed and been auto-fixed `MAX_TASK_RETRIES` times without
  passing (`ProjectRunner.analyze_test_failure`) - also `REPEATED_FAILURE`.
- The scheduler finds the project stalled - every remaining task `BLOCKED` on a failure,
  nothing running, nothing ready (`scheduler.is_stalled`) - see
  [05-task-dag.md](05-task-dag.md).

The `ApprovalType` enum also defines categories for destructive DB changes, external
deployment, sensitive config changes, suspicious package installs, and high-cost model
escalation (`Settings.HIGH_COST_ESCALATION_USD`) - the schema supports gating these the
same way; this repository's orchestrator currently exercises the repeated-failure and
stalled-project paths end to end, and the others are available for a deployment to wire
up additional checkpoints against the same `Approval` mechanism without new schema.

## What a human sees and can do

`GET /projects/{id}/approvals` (pending only) and `POST /approvals/{id}/decide` with a
decision of `approved`, `rejected`, or `modified`, plus an optional note - matching the
"Approve / Reject / Retry / Modify instruction" set from the project brief (`approved`
covers "retry as-is"; `modified` covers "retry with a modified instruction" via the note
field, which becomes part of the task's context on the next attempt).

Approving or modifying resets the task's status to `pending` (fresh attempt) and enqueues
`run_project_job`, which resumes via `ProjectRunner.run_or_resume()` - see
[04-orchestrator.md](04-orchestrator.md#resuming-after-a-human-decision). Rejecting
leaves the task in its failed state; the project stays paused.

## Frontend

`ApprovalPanel` (`frontend/src/components/Approvals/`) renders every pending approval with
its reason and three actions, and is shown unconditionally at the top of the workspace's
right panel whenever any exist - it is not something a user has to go looking for.
