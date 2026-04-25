import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

interface StreetStat {
  n: number;
  avg_score: number;
  standard_rate: number;
}

interface Props {
  byStreet?: Record<string, StreetStat>;
}

const STREETS = [
  { key: "preflop", label: "Preflop" },
  { key: "flop",    label: "Flop" },
  { key: "turn",    label: "Turn" },
  { key: "river",   label: "River" },
];

function rateColor(rate: number) {
  if (rate >= 0.80) return "bg-primary";
  if (rate >= 0.65) return "bg-yellow-500";
  if (rate >= 0.50) return "bg-orange-500";
  return "bg-destructive";
}

function rateText(rate: number) {
  if (rate >= 0.80) return "text-primary";
  if (rate >= 0.65) return "text-yellow-500";
  if (rate >= 0.50) return "text-orange-500";
  return "text-destructive";
}

export function StreetBreakdown({ byStreet }: Props) {
  const hasData = byStreet && Object.keys(byStreet).length > 0;

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5">
      <div className="flex items-center gap-1.5 mb-4">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          Performance por Rua
        </span>
        <HudTooltip content="Taxa de decisões standard (score ≤ 0.08) em cada rua do jogo. Ruas em laranja ou vermelho indicam onde seus leaks se concentram." />
      </div>

      {!hasData ? (
        <p className="text-xs text-muted-foreground">Sem dados suficientes.</p>
      ) : (
        <div className="space-y-3">
          {STREETS.map(({ key, label }) => {
            const s = byStreet?.[key];
            if (!s) return (
              <div key={key} className="flex items-center gap-3">
                <span className="w-14 font-mono text-[10px] text-muted-foreground/50">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-border" />
                <span className="w-10 text-right font-mono text-[10px] text-muted-foreground/40">—</span>
              </div>
            );
            const pct = s.standard_rate * 100;
            return (
              <div key={key} className="flex items-center gap-3">
                <span className="w-14 font-mono text-[10px] text-muted-foreground shrink-0">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all", rateColor(s.standard_rate))}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={cn("w-12 text-right font-mono text-[11px] font-bold tabular-nums", rateText(s.standard_rate))}>
                    {pct.toFixed(0)}%
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground/50">({s.n})</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
