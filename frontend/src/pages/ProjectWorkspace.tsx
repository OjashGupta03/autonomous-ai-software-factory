import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Network, Activity, BarChart3, Download } from "lucide-react";
import { useProject, useTaskGraph, useTasks } from "@/api/hooks";
import { TaskGraphView } from "@/components/TaskGraph/TaskGraphView";
import { LiveActivityFeed } from "@/components/AgentActivity/LiveActivityFeed";
import { TaskDetailPanel } from "@/components/Metrics/TaskDetailPanel";
import { ApprovalPanel } from "@/components/Approvals/ApprovalPanel";
import { FileViewer } from "@/components/FileViewer/FileViewer";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useProjectEvents } from "@/hooks/useProjectEvents";
import { cn } from "@/lib/utils";

type CenterTab = "graph" | "activity" | "files";

export function ProjectWorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>();
  
  // Keep SSE connection open at the page level so queries invalidate 
  // even if the Activity feed tab isn't currently active.
  useProjectEvents(projectId);
  
  const { data: project } = useProject(projectId);
  const { data: taskGraph } = useTaskGraph(projectId);
  const { data: tasks } = useTasks(projectId);
  const [selectedTaskId, setSelectedTaskId] = useState<string | undefined>();
  const [centerTab, setCenterTab] = useState<CenterTab>("graph");

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle shrink-0">
        <h1 className="font-display text-sm font-medium text-text-primary truncate">{project?.name}</h1>
        {project && <StatusBadge status={project.status} />}
        <span className="text-text-tertiary text-xs font-mono ml-auto">
          {tasks?.filter((t) => t.status === "completed").length ?? 0}/{tasks?.length ?? 0} tasks
        </span>
        <Link
          to={`/projects/${projectId}/analytics`}
          className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-brass transition-colors"
        >
          <BarChart3 size={13} />
          Analytics
        </Link>
        <button
          onClick={async () => {
            try {
              const token = localStorage.getItem("factory_access_token");
              const response = await fetch(`/api/v1/projects/${projectId}/download`, {
                headers: { Authorization: `Bearer ${token}` }
              });
              if (!response.ok) throw new Error("Download failed");
              const blob = await response.blob();
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `${project?.name || "project"}.zip`;
              document.body.appendChild(a);
              a.click();
              window.URL.revokeObjectURL(url);
              a.remove();
            } catch (e) {
              console.error(e);
              alert("Error downloading project.");
            }
          }}
          className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-brass transition-colors ml-2"
        >
          <Download size={13} />
          Download ZIP
        </button>
      </div>

      <div className="flex-1 min-h-0 grid grid-cols-[220px_1fr_320px]">
        {/* Left: task tree */}
        <div className="border-r border-border-subtle overflow-y-auto scrollbar-factory">
          <TaskList tasks={tasks ?? []} selectedTaskId={selectedTaskId} onSelect={setSelectedTaskId} />
        </div>

        {/* Center: live execution view */}
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border-subtle shrink-0">
            <TabButton active={centerTab === "graph"} onClick={() => setCenterTab("graph")}>
              <Network size={13} /> Task graph
            </TabButton>
            <TabButton active={centerTab === "activity"} onClick={() => setCenterTab("activity")}>
              <Activity size={13} /> Activity
            </TabButton>
            <TabButton active={centerTab === "files"} onClick={() => setCenterTab("files")}>
              Files
            </TabButton>
          </div>
          <div className="flex-1 min-h-0">
            {centerTab === "graph" && (
              <TaskGraphView
                nodes={taskGraph?.nodes ?? []}
                onSelectTask={setSelectedTaskId}
                selectedTaskId={selectedTaskId}
              />
            )}
            {centerTab === "activity" && <LiveActivityFeed projectId={projectId} />}
            {centerTab === "files" && <FileViewer projectId={projectId} />}
          </div>
        </div>

        {/* Right: approvals + selected task detail */}
        <div className="border-l border-border-subtle overflow-y-auto scrollbar-factory flex flex-col">
          <ApprovalPanel projectId={projectId} />
          <TaskDetailPanel projectId={projectId} taskId={selectedTaskId} />
        </div>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors",
        active ? "bg-surface-hover text-text-primary" : "text-text-tertiary hover:text-text-secondary"
      )}
    >
      {children}
    </button>
  );
}

function TaskList({
  tasks,
  selectedTaskId,
  onSelect,
}: {
  tasks: { id: string; title: string; status: string }[];
  selectedTaskId?: string;
  onSelect: (id: string) => void;
}) {
  if (tasks.length === 0) {
    return <p className="text-text-tertiary text-xs p-3">No tasks yet.</p>;
  }
  return (
    <ul className="py-1">
      {tasks.map((task) => (
        <li key={task.id}>
          <button
            onClick={() => onSelect(task.id)}
            className={cn(
              "w-full text-left px-3 py-2 flex flex-col gap-1 transition-colors border-l-2",
              selectedTaskId === task.id
                ? "bg-surface-hover border-l-signal"
                : "border-l-transparent hover:bg-surface-hover/50"
            )}
          >
            <span className="text-xs text-text-primary truncate">{task.title}</span>
            <StatusBadge status={task.status} />
          </button>
        </li>
      ))}
    </ul>
  );
}
