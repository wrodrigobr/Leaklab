import { AlertTriangle, ChevronRight, ShieldAlert, TrendingDown } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";

type Severity = "critical" | "moderate" | "minor";

interface LeakData {
  spot: string;
  n: number;
  avg_score: number;
}

interface Props {
  leaks?: LeakData[];
}

const severityStyles: Record<
  Severity,
  { border: string; badge: string; label: string; Icon: typeof ShieldAlert }
> = {
  critical: {
    border: "border-l-destructive",
    badge: "bg-destructive/10 text-destructive ring-destructive/20",
    label: "Crítico",
    Icon: ShieldAlert,
  },
  moderate: {
    border: "border-l-warning",
    badge: "bg-warning/10 text-warning ring-warning/20",
    label: "Moderado",
    Icon: AlertTriangle,
  },
  minor: {
    border: "border-l-primary",
    badge: "bg-primary/10 text-primary ring-primary/20",
    label: "Leve",
    Icon: TrendingDown,
  },
};

function spotLabel(spot: string): string {
  return spot.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function severity(score: number): Severity {
  if (score >= 0.36) return "critical";
  if (score >= 0.2) return "moderate";
  return "minor";
}

const FALLBACK: LeakData[] = [
  { spot: "over_aggression_oop_3bet", n: 24, avg_score: 0.42 },
  { spot: "sb_fold_vs_btn_steal", n: 18, avg_score: 0.28 },
  { spot: "river_check_call_flush_board", n: 11, avg_score: 0.21 },
];

export function LeaksPanel({ leaks }: Props) {
  const navigate = useNavigate();
  const data = leaks && leaks.length > 0 ? leaks.slice(0, 5) : FALLBACK;
  const isFallback = !leaks || leaks.length === 0;

  return (
    <section aria-labelledby="leaks-heading" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2
          id="leaks-heading"
          className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground"
        >
          <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
          Top leaks detectados
        </h2>
        <span className="font-mono text-[10px] text-muted-foreground">
          {isFallback ? "DEMO" : "IA_CORE v2.1"}
        </span>
      </div>

      <ul className="space-y-3">
        {data.map((leak) => {
          const sev = severity(leak.avg_score);
          const s = severityStyles[sev];
          return (
            <li
              key={leak.spot}
              className={cn(
                "rounded-md border border-border bg-hud-surface p-4 border-l-2 transition-colors hover:bg-hud-elevated",
                s.border
              )}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1",
                    s.badge
                  )}
                >
                  <s.Icon className="size-3" aria-hidden />
                  {s.label}
                </span>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {leak.n}× • score {leak.avg_score.toFixed(3)}
                </span>
              </div>
              <h3 className="text-sm font-semibold leading-tight text-foreground mb-1.5">
                {spotLabel(leak.spot)}
              </h3>
              <p className="text-xs leading-relaxed text-muted-foreground mb-3">
                {leak.n} decisões com erro médio de {(leak.avg_score * 100).toFixed(1)} pontos.
              </p>
              <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/60">
                <span className="font-mono text-[11px] text-destructive">
                  score: {leak.avg_score.toFixed(3)}
                </span>
                <button
                  onClick={() => navigate(`/study?spot=${encodeURIComponent(leak.spot)}`)}
                  className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Estudar
                  <ChevronRight className="size-3" aria-hidden />
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
