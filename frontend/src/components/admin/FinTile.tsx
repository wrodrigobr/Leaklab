import { cn } from "@/lib/utils";

// Flat hairline tile used across the Finance cockpit. Resolves the
// KpiTile/FinTile duplication: Finance uses FinTile everywhere.
export function FinTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "primary" | "warning" | "danger";
}) {
  return (
    <div className="bg-hud-surface p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 font-mono text-2xl font-light tabular-nums",
          accent === "primary"
            ? "text-primary"
            : accent === "warning"
            ? "text-warning"
            : accent === "danger"
            ? "text-destructive"
            : "text-foreground"
        )}
      >
        {value}
      </div>
      {sub && <div className="font-mono text-[10px] text-muted-foreground/70">{sub}</div>}
    </div>
  );
}
