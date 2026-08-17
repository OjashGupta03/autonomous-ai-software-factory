import { Handle, Position } from "@xyflow/react";
import { cn } from "@/lib/utils";
import type { TaskGraphNode } from "@/types/api";

const STATUS_BORDER: Record<string, string> = {
  pending: "border-l-status-pending",
  ready: "border-l-signal",
  running: "border-l-signal shadow-glow shadow-signal/40",
  blocked: "border-l-status-blocked",
  completed: "border-l-status-success",
  failed: "border-l-status-failure shadow-glow shadow-status-failure/30",
  needs_approval: "border-l-brass shadow-glow shadow-brass/30",
  skipped: "border-l-text-tertiary",
};

export interface TaskNodeData {
  label: string;
  status: string;
  taskType: string;
  [key: string]: unknown;
}

export function TaskGraphNodeCard({ data, selected }: { data: TaskNodeData; selected?: boolean }) {
  return (
    <div
      className={cn(
        "w-56 bg-surface-raised border border-border border-l-4 rounded px-3 py-2.5 text-left transition-shadow",
        STATUS_BORDER[data.status] ?? STATUS_BORDER.pending,
        selected && "outline outline-2 outline-signal",
        data.status === "running" && "animate-pulse-signal"
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-border !border-none !w-1.5 !h-1.5" />
      <p className="text-xs text-text-tertiary font-mono uppercase tracking-wide mb-1">{data.taskType}</p>
      <p className="text-sm text-text-primary font-medium leading-snug line-clamp-2">{data.label}</p>
      <Handle type="source" position={Position.Right} className="!bg-border !border-none !w-1.5 !h-1.5" />
    </div>
  );
}
