import { useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useNaiveComparison, useProjectMetrics } from "@/api/hooks";
import { Card, CardHeader } from "@/components/common/Card";
import { MetricStat } from "@/components/common/MetricStat";
import { formatCost, formatTokens } from "@/lib/utils";

const CHART_COLORS = ["#E8A33D", "#3DDBD9", "#5FBD8A", "#C77D4F", "#8B93A7"];

export function CostAnalyticsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: metrics } = useProjectMetrics(projectId);
  const { data: comparison } = useNaiveComparison(projectId);

  return (
    <div className="h-full overflow-y-auto scrollbar-factory">
      <div className="max-w-5xl mx-auto px-6 py-8 flex flex-col gap-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text-primary">Cost & token analytics</h1>
          <p className="text-text-secondary text-sm mt-1">
            Where tokens went, and what the cost-aware orchestrator saved versus a naive pipeline.
          </p>
        </div>

        {metrics && (
          <Card className="p-5 grid grid-cols-2 md:grid-cols-4 gap-6">
            <MetricStat label="LLM calls" value={String(metrics.llm_calls)} accent="signal" />
            <MetricStat label="Total tokens" value={formatTokens(metrics.total_tokens)} accent="brass" />
            <MetricStat label="Estimated cost" value={formatCost(metrics.estimated_cost_usd)} accent="brass" />
            <MetricStat
              label="Tasks completed"
              value={`${metrics.tasks_completed}/${metrics.tasks_total}`}
              accent="success"
            />
            <MetricStat label="Retries" value={String(metrics.retries)} />
            <MetricStat label="Cache hits" value={String(metrics.cache_hits)} accent="signal" />
            <MetricStat label="Input tokens" value={formatTokens(metrics.input_tokens)} />
            <MetricStat label="Output tokens" value={formatTokens(metrics.output_tokens)} />
          </Card>
        )}

        {comparison && (
          <Card>
            <CardHeader>
              <h2 className="text-sm font-medium text-text-primary">Naive vs. optimized workflow</h2>
              <span className="text-status-success text-sm font-mono font-medium">
                {comparison.tokens_saved_pct}% tokens saved
              </span>
            </CardHeader>
            <div className="p-4">
              <p className="text-text-tertiary text-xs mb-4 leading-relaxed">
                The naive figure is a documented <em>estimate</em> of what a pipeline that called every agent for
                every task, replaying full history each time, would have cost - it is not a run that actually
                happened. See docs/07-token-optimization.md.
              </p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={[
                    { name: "LLM calls", naive: comparison.naive_llm_calls, optimized: comparison.optimized_llm_calls },
                    {
                      name: "Tokens (thousands)",
                      naive: Math.round(comparison.naive_tokens / 1000),
                      optimized: Math.round(comparison.optimized_tokens / 1000),
                    },
                  ]}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1A1F2B" horizontal={false} />
                  <XAxis type="number" stroke="#5B6478" fontSize={12} />
                  <YAxis type="category" dataKey="name" stroke="#5B6478" fontSize={12} width={110} />
                  <Tooltip
                    contentStyle={{ background: "#171C25", border: "1px solid #232937", borderRadius: 4, fontSize: 12 }}
                  />
                  <Bar dataKey="naive" fill="#5B6478" name="Naive (estimated)" radius={[0, 3, 3, 0]} />
                  <Bar dataKey="optimized" fill="#E8A33D" name="Optimized (actual)" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}

        {metrics && metrics.by_model.length > 0 && (
          <Card>
            <CardHeader>
              <h2 className="text-sm font-medium text-text-primary">Cost by model</h2>
            </CardHeader>
            <div className="p-4 grid grid-cols-2 gap-4 items-center">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={metrics.by_model}
                    dataKey="cost_usd"
                    nameKey="model"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                  >
                    {metrics.by_model.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#171C25", border: "1px solid #232937", borderRadius: 4, fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <ul className="flex flex-col gap-2">
                {metrics.by_model.map((m, i) => (
                  <li key={m.model} className="flex items-center gap-2 text-xs">
                    <span
                      className="h-2.5 w-2.5 rounded-full shrink-0"
                      style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
                    />
                    <span className="text-text-primary font-mono">{m.model}</span>
                    <span className="text-text-tertiary ml-auto">{m.calls} calls</span>
                    <span className="text-text-secondary font-mono w-16 text-right">{formatCost(m.cost_usd)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
