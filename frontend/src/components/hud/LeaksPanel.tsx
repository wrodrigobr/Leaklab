import { AlertTriangle, ChevronRight, PlayCircle, ShieldAlert, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

type Severity = "critical" | "moderate" | "minor";

interface Leak {
  id: string;
  signature: string;
  title: string;
  description: string;
  severity: Severity;
  evLoss: string;
}

const LEAKS: Leak[] = [
  {
    id: "1",
    signature: "LVL_82",
    title: "Over-aggression em pots 3-bet OOP",
    description: "C-Bet de 72% em boards molhados quando OOP. EV perdido estimado em -$12.40 / 100 mãos.",
    severity: "critical",
    evLoss: "-12.4 BB/100",
  },
  {
    id: "2",
    signature: "LVL_41",
    title: "SB defendendo pouco vs roubo do BTN",
    description: "Folding 14% acima do equilíbrio contra raises 2.5x do botão. Sugestão: 3-bet polarizado.",
    severity: "moderate",
    evLoss: "-4.8 BB/100",
  },
  {
    id: "3",
    signature: "LVL_19",
    title: "River check-call em flushes pareados",
    description: "Pagando jams demais em boards de flush pareado. Foco em bloqueadores e história da mão.",
    severity: "moderate",
    evLoss: "-3.1 BB/100",
  },
];

const severityStyles: Record<Severity, { border: string; badge: string; label: string; Icon: typeof ShieldAlert }> = {
  critical: {
    border: "border-l-destructive",
    badge: "bg-destructive/10 text-destructive ring-destructive/20",
    label: "Critical",
    Icon: ShieldAlert,
  },
  moderate: {
    border: "border-l-warning",
    badge: "bg-warning/10 text-warning ring-warning/20",
    label: "Moderate",
    Icon: AlertTriangle,
  },
  minor: {
    border: "border-l-primary",
    badge: "bg-primary/10 text-primary ring-primary/20",
    label: "Minor",
    Icon: TrendingDown,
  },
};

export function LeaksPanel() {
  return (
    <section aria-labelledby="leaks-heading" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 id="leaks-heading" className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
          Top leaks detectados
        </h2>
        <span className="font-mono text-[10px] text-muted-foreground">IA_CORE v2.1</span>
      </div>

      <ul className="space-y-3">
        {LEAKS.map((leak) => {
          const s = severityStyles[leak.severity];
          return (
            <li
              key={leak.id}
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
                <span className="font-mono text-[10px] text-muted-foreground">{leak.signature}</span>
              </div>
              <h3 className="text-sm font-semibold leading-tight text-foreground mb-1.5">{leak.title}</h3>
              <p className="text-xs leading-relaxed text-muted-foreground mb-3">{leak.description}</p>
              <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/60">
                <span className="font-mono text-[11px] text-destructive">{leak.evLoss}</span>
                <div className="flex gap-1.5">
                  <button className="inline-flex items-center gap-1 rounded-sm bg-secondary px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <PlayCircle className="size-3" aria-hidden />
                    Replay
                  </button>
                  <button className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    Estudar
                    <ChevronRight className="size-3" aria-hidden />
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
