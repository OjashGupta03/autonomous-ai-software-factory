import { Link } from "react-router-dom";
import { Plus, Boxes } from "lucide-react";
import { useProjects } from "@/api/hooks";
import { Card } from "@/components/common/Card";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/common/Button";
import { formatCost, formatTokens, formatRelativeTime } from "@/lib/utils";

export function DashboardPage() {
  const { data: projects, isLoading } = useProjects();

  return (
    <div className="h-full overflow-y-auto scrollbar-factory">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-display text-2xl font-semibold text-text-primary">Projects</h1>
            <p className="text-text-secondary text-sm mt-1">
              Hand the factory a requirement; watch it plan, build, test, and fix itself.
            </p>
          </div>
          <Link to="/new">
            <Button variant="primary">
              <Plus size={16} />
              New project
            </Button>
          </Link>
        </div>

        {isLoading && <p className="text-text-tertiary text-sm">Loading projects...</p>}

        {!isLoading && projects && projects.length === 0 && (
          <Card className="p-10 flex flex-col items-center gap-3 text-center">
            <Boxes size={32} className="text-text-tertiary" />
            <p className="text-text-primary font-medium">No projects yet</p>
            <p className="text-text-secondary text-sm max-w-sm">
              Describe what you want built - the Planner agent turns it into an architecture, a task graph, and a
              running build.
            </p>
            <Link to="/new">
              <Button variant="primary" className="mt-2">
                <Plus size={16} />
                Start a project
              </Button>
            </Link>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects?.map((project) => (
            <Link key={project.id} to={`/projects/${project.id}`}>
              <Card className="p-4 h-full flex flex-col gap-3 hover:border-signal/50 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-medium text-text-primary leading-snug">{project.name}</h2>
                  <StatusBadge status={project.status} />
                </div>

                <div className="flex-1" />

                <div className="grid grid-cols-3 gap-2 pt-3 border-t border-border-subtle text-xs">
                  <Stat label="Tasks" value={`${project.tasks_completed}/${project.tasks_total || 0}`} />
                  <Stat label="Tokens" value={formatTokens(project.total_tokens)} />
                  <Stat label="Cost" value={formatCost(project.total_cost_usd)} />
                </div>
                <p className="text-text-tertiary text-xs font-mono">{formatRelativeTime(project.updated_at)}</p>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-text-tertiary uppercase tracking-wide">{label}</span>
      <span className="text-text-primary font-mono font-medium">{value}</span>
    </div>
  );
}
