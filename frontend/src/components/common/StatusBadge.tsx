import { cn } from "@/lib/utils";
import { taskStatusLabel } from "@/lib/utils";
import type { TaskStatus } from "@/types/api";

const STYLES: Record<string, { dot: string; text: string; pulse?: boolean }> = {
  pending: { dot: "bg-status-pending", text: "text-text-secondary" },
  ready: { dot: "bg-signal", text: "text-signal" },
  running: { dot: "bg-signal", text: "text-signal", pulse: true },
  blocked: { dot: "bg-status-blocked", text: "text-status-blocked" },
  completed: { dot: "bg-status-success", text: "text-status-success" },
  failed: { dot: "bg-status-failure", text: "text-status-failure" },
  needs_approval: { dot: "bg-brass", text: "text-brass", pulse: true },
  skipped: { dot: "bg-text-tertiary", text: "text-text-tertiary" },
};

export function StatusBadge({ status, className }: { status: TaskStatus | string; className?: string }) {
  const style = STYLES[status] ?? STYLES.pending;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium font-mono", style.text, className)}>
      <span
        className={cn("h-1.5 w-1.5 rounded-full", style.dot, style.pulse && "animate-pulse-signal")}
        aria-hidden="true"
      />
      {taskStatusLabel(status)}
    </span>
  );
}
