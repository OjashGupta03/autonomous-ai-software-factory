import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Approval,
  FileMeta,
  FileRead,
  NaiveVsOptimizedComparison,
  Project,
  ProjectMetrics,
  ProjectSummary,
  TaskDetail,
  TaskGraphResponse,
  TaskRead,
  TestRunRead,
} from "@/types/api";

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => api.get<ProjectSummary[]>("/projects"),
    refetchInterval: 15_000,
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => api.get<Project>(`/projects/${projectId}`),
    enabled: Boolean(projectId),
    refetchInterval: 5_000,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      requirement: string;
      preferred_stack?: Record<string, unknown>;
      token_budget?: number;
    }) => api.post<Project>("/projects", payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useStartProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => api.post(`/projects/${projectId}/start`),
    onSuccess: (_data, projectId) => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "tasks"] });
    },
  });
}

export function useTaskGraph(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "task-graph"],
    queryFn: () => api.get<TaskGraphResponse>(`/projects/${projectId}/tasks/graph`),
    enabled: Boolean(projectId),
    refetchInterval: 4_000,
  });
}

export function useTasks(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "tasks"],
    queryFn: () => api.get<TaskRead[]>(`/projects/${projectId}/tasks`),
    enabled: Boolean(projectId),
    refetchInterval: 5_000,
  });
}

export function useTaskDetail(projectId: string | undefined, taskId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "tasks", taskId],
    queryFn: () => api.get<TaskDetail>(`/projects/${projectId}/tasks/${taskId}`),
    enabled: Boolean(projectId) && Boolean(taskId),
  });
}

export function useProjectMetrics(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "metrics"],
    queryFn: () => api.get<ProjectMetrics>(`/projects/${projectId}/metrics`),
    enabled: Boolean(projectId),
    refetchInterval: 6_000,
  });
}

export function useNaiveComparison(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "metrics", "comparison"],
    queryFn: () => api.get<NaiveVsOptimizedComparison>(`/projects/${projectId}/metrics/comparison`),
    enabled: Boolean(projectId),
    refetchInterval: 10_000,
  });
}

export function useApprovals(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "approvals"],
    queryFn: () => api.get<Approval[]>(`/projects/${projectId}/approvals`),
    enabled: Boolean(projectId),
    refetchInterval: 5_000,
  });
}

export function useDecideApproval(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalId, decision, note }: { approvalId: string; decision: string; note?: string }) =>
      api.post<Approval>(`/projects/${projectId}/approvals/${approvalId}/decide`, { decision, note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "approvals"] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "tasks"] });
    },
  });
}

export function useFiles(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "files"],
    queryFn: () => api.get<FileMeta[]>(`/projects/${projectId}/files`),
    enabled: Boolean(projectId),
    refetchInterval: 6_000,
  });
}

export function useFileContent(projectId: string | undefined, path: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "files", "content", path],
    queryFn: () => api.get<FileRead>(`/projects/${projectId}/files/content?path=${encodeURIComponent(path!)}`),
    enabled: Boolean(projectId) && Boolean(path),
  });
}

export function useTestRuns(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "tests"],
    queryFn: () => api.get<TestRunRead[]>(`/projects/${projectId}/tests`),
    enabled: Boolean(projectId),
    refetchInterval: 8_000,
  });
}
