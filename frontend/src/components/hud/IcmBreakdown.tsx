import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

interface IcmStat {
  n: number;
  avg_score: number;
  standard_rate: number;
}

interface Props {
  icm?: Record<string, IcmStat>;
}

const ICM_ORDER = ["high", "medium", "low", "none"];
const ICM_LABEL: Record<string, string> = {
  high:   "Alta pressão",
  medium: "Média",
  low:    "Baixa",
  none:   "Sem ICM",
};

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

export function IcmBreakdown({ icm }: Props) {
  const rows = ICM_ORDER
    .filter((k) => icm?.[k])
    .map((k) => ({ key: k, label: ICM_LABEL[k] ?? k, ...icm![k] }));

  const extras = Object.keys(icm ?? {})
    .filter((k) => !ICM_ORDER.includes(k))
    .map((k) => ({ key: k, label: k, ...icm![k] }));

  const all = [...rows, ...extras];

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5">
      <div className="flex items-center gap-1.5 mb-4">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          Pressão ICM
        </span>
        <HudTooltip content="ICM (Independent Chip Model) mede o valor monetário dos chips em MTT. Sob alta pressão (bubble, FT), erros custam muito mais do que o valor nominal dos chips. Compare sua performance em cada nível para identificar se você joga bem ou mal sob pressão." />
      </div>

      {all.length === 0 ? (
        <p className="text-xs text-muted-foreground">Sem dados de ICM disponíveis.</p>
      ) : (
        <div className="space-y-2.5">
          {all.map(({ key, label, standard_rate, n }) => {
            const pct = standard_rate * 100;
            return (
              <div key={key} className="flex items-center gap-3">
                <span className="w-20 font-mono text-[10px] text-muted-foreground shrink-0 leading-tight">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all", rateColor(standard_rate))}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={cn("w-12 text-right font-mono text-[11px] font-bold tabular-nums", rateText(standard_rate))}>
                    {pct.toFixed(0)}%
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground/50">({n})</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
