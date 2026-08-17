import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-brass text-base hover:bg-brass-glow font-medium",
  secondary: "bg-surface-raised text-text-primary border border-border hover:bg-surface-hover",
  ghost: "text-text-secondary hover:text-text-primary hover:bg-surface-hover",
  danger: "bg-status-failure text-base hover:opacity-90 font-medium",
};

export function Button({
  variant = "secondary",
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors disabled:opacity-50 disabled:pointer-events-none",
        VARIANT_CLASSES[variant],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
