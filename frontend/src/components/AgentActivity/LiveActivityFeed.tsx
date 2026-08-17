import { useEffect, useRef } from "react";
import { Radio } from "lucide-react";
import { useProjectEvents } from "@/hooks/useProjectEvents";
import { cn, formatRelativeTime } from "@/lib/utils";

const EVENT_LABEL: Record<string, string> = {
  planner_started: "Planner started",
  plan_ready: "Architecture plan ready",
  task_created: "Task created",
  task_ready: "Task ready",
  agent_started: "Agent started",
  tool_called: "Tool called",
  file_modified: "File modified",
  task_succeeded: "Task succeeded",
  task_failed: "Task failed",
  tests_started: "Tests started",
  tests_finished: "Tests finished",
  approval_requested: "Approval requested",
  approval_resolved: "Approval resolved",
  project_completed: "Project completed",
  project_failed: "Project failed",
};

const EVENT_COLOR: Record<string, string> = {
  task_succeeded: "text-status-success",
  project_completed: "text-status-success",
  task_failed: "text-status-failure",
  project_failed: "text-status-failure",
  approval_requested: "text-brass",
  agent_started: "text-signal",
  tool_called: "text-text-secondary",
};

export function LiveActivityFeed({ projectId }: { projectId: string | undefined }) {
  const { events, connected } = useProjectEvents(projectId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle shrink-0">
        <Radio size={13} className={cn(connected ? "text-signal animate-pulse-signal" : "text-text-tertiary")} />
        <span className="text-xs text-text-tertiary uppercase tracking-wide font-medium">
          {connected ? "Live" : "Disconnected"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-factory px-3 py-2 flex flex-col gap-1.5">
        {events.length === 0 && (
          <p className="text-text-tertiary text-sm py-4 text-center">Waiting for activity...</p>
        )}
        {events.map((event, i) => (
          <div key={event.id ?? i} className="text-xs font-mono flex items-start gap-2 leading-relaxed">
            <span className="text-text-tertiary shrink-0 w-14">{formatRelativeTime(event.created_at)}</span>
            <span className={cn("flex-1", EVENT_COLOR[event.event_type] ?? "text-text-secondary")}>
              {EVENT_LABEL[event.event_type] ?? event.event_type}
              {typeof event.payload?.title === "string" && (
                <span className="text-text-tertiary"> - {event.payload.title}</span>
              )}
              {typeof event.payload?.summary === "string" && (
                <span className="text-text-tertiary block truncate">{event.payload.summary}</span>
              )}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
