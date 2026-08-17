import { cn } from "@/lib/utils";

export function MetricStat({
  label,
  value,
  sublabel,
  accent,
  className,
}: {
  label: string;
  value: string;
  sublabel?: string;
  accent?: "brass" | "signal" | "success" | "failure";
  className?: string;
}) {
  const accentClass = {
    brass: "text-brass",
    signal: "text-signal",
    success: "text-status-success",
    failure: "text-status-failure",
  }[accent ?? "brass"];

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-xs uppercase tracking-wider text-text-tertiary font-medium">{label}</span>
      <span className={cn("font-display text-2xl font-semibold tabular-nums animate-tick-in", accentClass)}>
        {value}
      </span>
      {sublabel && <span className="text-xs text-text-secondary font-mono">{sublabel}</span>}
    </div>
  );
}
