import { ChevronRight, ShieldAlert, AlertTriangle, TrendingDown } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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

const SEVERITY: Record<Severity, { dot: string; badge: string; Icon: typeof ShieldAlert }> = {
  critical: { dot: "bg-destructive", badge: "text-destructive bg-destructive/10 ring-destructive/20", Icon: ShieldAlert },
  moderate: { dot: "bg-yellow-400",  badge: "text-yellow-400 bg-yellow-400/10 ring-yellow-400/20",  Icon: AlertTriangle },
  minor:    { dot: "bg-primary",     badge: "text-primary bg-primary/10 ring-primary/20",             Icon: TrendingDown },
};

const STREET_LABEL: Record<string, string> = {
  preflop: "Preflop",
  flop:    "Flop",
  turn:    "Turn",
  river:   "River",
};

function severity(score: number): Severity {
  if (score >= 0.36) return "critical";
  if (score >= 0.2)  return "moderate";
  return "minor";
}

const FALLBACK: LeakData[] = [
  { spot: "over_aggression_oop_3bet",       n: 24, avg_score: 0.42 },
  { spot: "sb_fold_vs_btn_steal",           n: 18, avg_score: 0.28 },
  { spot: "river_check_call_flush_board",   n: 11, avg_score: 0.21 },
];

export function LeaksPanel({ leaks }: Props) {
  const navigate  = useNavigate();
  const { t } = useTranslation("dashboard");
  const data      = leaks && leaks.length > 0 ? leaks.slice(0, 6) : FALLBACK;
  const isFallback = !leaks || leaks.length === 0;

  function spotLabel(spot: string): string {
    if (spot.includes("/")) {
      const [street, action] = spot.split("/");
      return t("leaks.doing", { street: STREET_LABEL[street] ?? street, action });
    }
    return spot.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  return (
    <section aria-labelledby="leaks-heading" className="rounded-xl border border-border bg-hud-surface overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2
          id="leaks-heading"
          className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground"
        >
          <span className="size-1.5 rounded-full bg-destructive animate-pulse" aria-hidden />
          {t("leaks.title")}
        </h2>
        <span className="font-mono text-[10px] text-muted-foreground">
          {isFallback ? "DEMO" : "IA_CORE v2.1"}
        </span>
      </div>

      <ul className="divide-y divide-border/50">
        {data.map((leak) => {
          const sev = severity(leak.avg_score);
          const { dot, badge, Icon } = SEVERITY[sev];
          const label = spotLabel(leak.spot);
          return (
            <li key={leak.spot} className="flex items-center gap-3 px-4 py-2.5 hover:bg-hud-elevated/40 transition-colors">
              <span className={cn("size-1.5 shrink-0 rounded-full", dot)} aria-hidden />
              <span className="flex-1 text-xs text-foreground leading-tight truncate min-w-0">
                {label}
              </span>
              <span className={cn(
                "shrink-0 inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-bold ring-1",
                badge
              )}>
                <Icon className="size-2.5" aria-hidden />
                {leak.n}×
              </span>
              <button
                onClick={() => navigate(`/study?spot=${encodeURIComponent(leak.spot)}`)}
                className="shrink-0 inline-flex items-center gap-0.5 font-mono text-[10px] font-bold text-primary hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={t("leaks.studyLabel", { spot: label })}
              >
                {t("leaks.study")}
                <ChevronRight className="size-3" aria-hidden />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
