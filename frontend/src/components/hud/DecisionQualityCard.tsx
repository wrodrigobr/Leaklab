import { HudTooltip } from "./HudTooltip";

interface Props {
  byLabel?: Record<string, number>;
}

const LABELS = [
  { key: "standard",      label: "Standard",      color: "bg-primary",         text: "text-primary" },
  { key: "marginal",      label: "Marginal",       color: "bg-yellow-500",      text: "text-yellow-500" },
  { key: "small_mistake", label: "Pequeno erro",   color: "bg-orange-500",      text: "text-orange-500" },
  { key: "clear_mistake", label: "Erro claro",     color: "bg-destructive",     text: "text-destructive" },
] as const;

export function DecisionQualityCard({ byLabel }: Props) {
  const total = Object.values(byLabel ?? {}).reduce((s, n) => s + n, 0);

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Qualidade das Decisões
          </span>
          <HudTooltip content="Distribuição de todas as suas decisões por qualidade. Standard = dentro do esperado (score ≤ 0.08). Marginal = aceitável mas subótimo. Erros reduzem seu ROI de longo prazo." />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{total > 0 ? `${total} decisões` : "—"}</span>
      </div>

      {total === 0 ? (
        <p className="text-xs text-muted-foreground">Sem dados suficientes.</p>
      ) : (
        <>
          {/* Stacked bar */}
          <div className="flex h-3 w-full overflow-hidden rounded-full gap-px mb-4">
            {LABELS.map(({ key, color }) => {
              const n = byLabel?.[key] ?? 0;
              const pct = total > 0 ? (n / total) * 100 : 0;
              if (pct === 0) return null;
              return (
                <div
                  key={key}
                  className={`${color} transition-all`}
                  style={{ width: `${pct}%` }}
                  title={`${pct.toFixed(1)}%`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            {LABELS.map(({ key, label, text }) => {
              const n = byLabel?.[key] ?? 0;
              const pct = total > 0 ? (n / total) * 100 : 0;
              return (
                <div key={key} className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground truncate">{label}</span>
                  <span className={`font-mono text-[11px] font-bold tabular-nums ${text}`}>
                    {pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
