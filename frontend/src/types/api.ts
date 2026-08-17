// Mirrors backend/app/schemas/*.py. Kept as one file since the surface
// is small enough that hunting across many files would cost more than
// it saves - see docs/16-frontend.md.

export type ProjectStatus =
  | "draft" | "planning" | "executing" | "testing" | "needs_approval" | "completed" | "failed";

export type TaskStatus =
  | "pending" | "ready" | "running" | "blocked" | "completed" | "failed" | "needs_approval" | "skipped";

export type TaskType =
  | "scaffold" | "install_dependencies" | "format_lint" | "schema_design"
  | "backend_implementation" | "frontend_implementation" | "integration"
  | "test_authoring" | "bugfix" | "documentation" | "review";

export type AgentType = "planner" | "coder" | "reviewer" | "debugger" | "tester" | "documenter";
export type ModelTier = "deterministic" | "cheap" | "coding" | "reasoning" | "fallback";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "modified";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  preferred_stack: Record<string, unknown> | null;
  token_budget: number;
  current_iteration: number;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary extends Project {
  tasks_total: number;
  tasks_completed: number;
  tasks_failed: number;
  total_cost_usd: number;
  total_tokens: number;
  llm_calls: number;
}

export interface TaskRead {
  id: string;
  project_id: string;
  plan_id: string | null;
  title: string;
  description: string;
  task_type: TaskType;
  assigned_agent_type: AgentType | null;
  status: TaskStatus;
  priority: number;
  attempt_count: number;
  max_attempts: number;
  started_at: string | null;
  completed_at: string | null;
  depends_on: string[];
  created_at: string;
  updated_at: string;
}

export interface TaskDetail extends TaskRead {
  files_modified: string[];
  latest_error: string | null;
  tokens_used: number;
  cost_usd: number;
}

export interface TaskGraphNode {
  id: string;
  title: string;
  status: TaskStatus;
  task_type: TaskType;
  depends_on: string[];
}

export interface TaskGraphResponse {
  project_id: string;
  nodes: TaskGraphNode[];
}

export interface AgentRunRead {
  id: string;
  task_id: string;
  agent_id: string | null;
  status: string;
  model_tier: ModelTier | null;
  model_used: string | null;
  decision_summary: string | null;
  output_summary: string | null;
  tokens_input: number;
  tokens_output: number;
  cost_usd: number;
  cache_hit: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface ModelUsageAggregate {
  model: string;
  provider: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface ProjectMetrics {
  project_id: string;
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  tasks_completed: number;
  tasks_total: number;
  retries: number;
  cache_hits: number;
  parallel_tasks_peak: number;
  by_model: ModelUsageAggregate[];
}

export interface NaiveVsOptimizedComparison {
  project_id: string;
  naive_llm_calls: number;
  naive_tokens: number;
  optimized_llm_calls: number;
  optimized_tokens: number;
  tokens_saved: number;
  tokens_saved_pct: number;
  calls_saved: number;
  calls_saved_pct: number;
}

export interface Approval {
  id: string;
  project_id: string;
  task_id: string | null;
  approval_type: string;
  status: ApprovalStatus;
  requested_reason: string;
  decision_note: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface FileMeta {
  id: string;
  project_id: string;
  path: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface FileRead extends FileMeta {
  content: string;
}

export interface ProjectEventPayload {
  id?: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface TestResultRead {
  id: string;
  test_name: string;
  status: "pass" | "fail" | "error";
  duration_ms: number;
  message: string | null;
}

export interface TestRunRead {
  id: string;
  project_id: string;
  task_id: string | null;
  trigger: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  results: TestResultRead[];
  created_at: string;
}
