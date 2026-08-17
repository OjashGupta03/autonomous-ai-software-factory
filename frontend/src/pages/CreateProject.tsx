import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useCreateProject, useStartProject } from "@/api/hooks";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

const EXAMPLE = "Build a URL shortening SaaS with authentication, PostgreSQL, analytics and a React dashboard.";

export function CreateProjectPage() {
  const navigate = useNavigate();
  const createProject = useCreateProject();
  const startProject = useStartProject();

  const [name, setName] = useState("");
  const [requirement, setRequirement] = useState("");
  const [tokenBudget, setTokenBudget] = useState(500_000);
  const [preferredStack, setPreferredStack] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const project = await createProject.mutateAsync({
      name,
      requirement,
      token_budget: tokenBudget,
      preferred_stack: preferredStack ? { notes: preferredStack } : undefined,
    });
    await startProject.mutateAsync(project.id);
    navigate(`/projects/${project.id}`);
  }

  const isSubmitting = createProject.isPending || startProject.isPending;

  return (
    <div className="h-full overflow-y-auto scrollbar-factory">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <h1 className="font-display text-2xl font-semibold text-text-primary mb-1">New project</h1>
        <p className="text-text-secondary text-sm mb-6">
          One requirement in plain language. The Planner agent handles architecture and task decomposition from here.
        </p>

        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-text-secondary">Project name</span>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="URL Shortener SaaS"
                className="bg-base border border-border rounded px-3 py-2 text-text-primary focus:border-signal outline-none"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-text-secondary">Requirement</span>
              <textarea
                required
                minLength={10}
                rows={5}
                value={requirement}
                onChange={(e) => setRequirement(e.target.value)}
                placeholder={EXAMPLE}
                className="bg-base border border-border rounded px-3 py-2 text-text-primary focus:border-signal outline-none resize-none font-mono text-sm leading-relaxed"
              />
              <button
                type="button"
                onClick={() => setRequirement(EXAMPLE)}
                className="text-text-tertiary hover:text-signal text-xs text-left w-fit"
              >
                Use example requirement
              </button>
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-text-secondary">Preferred stack / constraints (optional)</span>
              <input
                value={preferredStack}
                onChange={(e) => setPreferredStack(e.target.value)}
                placeholder="e.g. must use Stripe for billing"
                className="bg-base border border-border rounded px-3 py-2 text-text-primary focus:border-signal outline-none"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-text-secondary">Token budget</span>
              <input
                type="number"
                min={10_000}
                step={10_000}
                value={tokenBudget}
                onChange={(e) => setTokenBudget(Number(e.target.value))}
                className="bg-base border border-border rounded px-3 py-2 text-text-primary focus:border-signal outline-none w-48 font-mono"
              />
              <span className="text-text-tertiary text-xs">
                The orchestrator escalates for approval before exceeding this.
              </span>
            </label>

            {createProject.isError && (
              <p className="text-status-failure text-sm">
                {createProject.error instanceof Error ? createProject.error.message : "Something went wrong."}
              </p>
            )}

            <Button type="submit" variant="primary" disabled={isSubmitting} className="justify-center">
              {isSubmitting ? "Starting..." : "Create and start building"}
              {!isSubmitting && <ArrowRight size={16} />}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
