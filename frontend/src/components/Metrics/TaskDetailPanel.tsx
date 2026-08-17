import { Clock, Coins, FileCode, AlertCircle } from "lucide-react";
import { useTaskDetail } from "@/api/hooks";
import { StatusBadge } from "@/components/common/StatusBadge";
import { formatCost, formatTokens } from "@/lib/utils";

export function TaskDetailPanel({
  projectId,
  taskId,
}: {
  projectId: string | undefined;
  taskId: string | undefined;
}) {
  const { data: task } = useTaskDetail(projectId, taskId);

  if (!taskId) {
    return (
      <div className="h-full flex items-center justify-center text-text-tertiary text-sm text-center px-6">
        Select a task in the graph or list to see its details, tools used, and token usage.
      </div>
    );
  }

  if (!task) return <div className="p-4 text-text-tertiary text-sm">Loading...</div>;

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto scrollbar-factory h-full">
      <div>
        <p className="text-xs text-text-tertiary font-mono uppercase tracking-wide mb-1">{task.task_type}</p>
        <h3 className="text-text-primary font-medium leading-snug">{task.title}</h3>
        <div className="mt-2">
          <StatusBadge status={task.status} />
        </div>
      </div>

      <p className="text-sm text-text-secondary leading-relaxed">{task.description}</p>

      <div className="grid grid-cols-2 gap-3 py-3 border-y border-border-subtle">
        <DetailStat icon={<Coins size={13} />} label="Tokens" value={formatTokens(task.tokens_used)} />
        <DetailStat icon={<Coins size={13} />} label="Cost" value={formatCost(task.cost_usd)} />
        <DetailStat icon={<Clock size={13} />} label="Attempts" value={`${task.attempt_count}/${task.max_attempts}`} />
        <DetailStat icon={<FileCode size={13} />} label="Files" value={String(task.files_modified.length)} />
      </div>

      {task.files_modified.length > 0 && (
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1.5">Files modified</p>
          <ul className="flex flex-col gap-1">
            {task.files_modified.map((path) => (
              <li key={path} className="text-xs font-mono text-text-secondary truncate">
                {path}
              </li>
            ))}
          </ul>
        </div>
      )}

      {task.latest_error && (
        <div className="bg-status-failure/10 border border-status-failure/30 rounded p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertCircle size={13} className="text-status-failure" />
            <span className="text-xs text-status-failure font-medium uppercase tracking-wide">Latest error</span>
          </div>
          <p className="text-xs text-text-secondary font-mono leading-relaxed">{task.latest_error}</p>
        </div>
      )}
    </div>
  );
}

function DetailStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="flex items-center gap-1 text-text-tertiary text-xs">
        {icon}
        {label}
      </span>
      <span className="text-text-primary font-mono text-sm font-medium">{value}</span>
    </div>
  );
}
