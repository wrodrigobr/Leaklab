import { HudTooltip } from "./HudTooltip";
import { cn } from "@/lib/utils";
import type { GtoAlignmentMatrixData } from "@/lib/api";

interface Props {
  data?: GtoAlignmentMatrixData | null;
}

const STREET_LABEL: Record<string, string> = {
  preflop: "Preflop",
  flop:    "Flop",
  turn:    "Turn",
  river:   "River",
};

const MIN_RELIABLE = 20;   // n < 20 → IC alto, atenua célula
const MIN_DISPLAY  = 3;    // n < 3  → não calcula (sem dado)

function alignedColor(pct: number | null, n: number): { bg: string; text: string } {
  if (pct == null || n < MIN_DISPLAY) return { bg: "bg-muted/10", text: "text-muted-foreground/50" };
  // Gradient: vermelho < 50% → âmbar 50-70 → verde claro 70-85 → emerald > 85
  if (pct >= 85) return { bg: "bg-emerald-500/20", text: "text-emerald-300" };
  if (pct >= 70) return { bg: "bg-emerald-500/10", text: "text-emerald-400" };
  if (pct >= 55) return { bg: "bg-amber-500/15",   text: "text-amber-300"  };
  if (pct >= 40) return { bg: "bg-orange-500/15",  text: "text-orange-300" };
  return                 { bg: "bg-red-500/20",     text: "text-red-300"    };
}

export function GtoAlignmentMatrixCard({ data }: Props) {
  if (!data || data.cells.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-2">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          Heatmap Posição × Street
        </span>
        <p className="text-xs text-muted-foreground">Sem dados suficientes.</p>
      </div>
    );
  }

  const { positions, streets, cells } = data;
  const cellMap = new Map<string, typeof cells[number]>();
  cells.forEach(c => cellMap.set(`${c.position}|${c.street}`, c));

  // Volume total p/ decidir se mostra avisos
  const hasAnyLow = cells.some(c => c.with_gto > 0 && c.with_gto < MIN_RELIABLE);

  return (
    <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary" aria-hidden />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            GTO Alignment · Posição × Street
          </span>
          <HudTooltip content="Matriz de aderência GTO por posição e street. Verde = alinhado com solver; vermelho = leak. Células atenuadas têm < 20 decisões (intervalo de confiança alto)." />
        </div>
        {hasAnyLow && (
          <span className="font-mono text-[9px] text-amber-400/70" title="Células com n < 20 têm IC alto, interpretar com cautela">
            algumas células com amostra baixa
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/60">
              <th className="px-3 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground"></th>
              {streets.map(s => (
                <th key={s} className="px-3 py-2 text-center font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {STREET_LABEL[s] ?? s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map(pos => (
              <tr key={pos} className="border-b border-border/30 last:border-0">
                <td className="px-3 py-2 font-mono text-[11px] font-bold text-foreground/80">{pos}</td>
                {streets.map(s => {
                  const cell = cellMap.get(`${pos}|${s}`);
                  const aligned = cell?.aligned_pct ?? null;
                  const n = cell?.with_gto ?? 0;
                  const { bg, text } = alignedColor(aligned, n);
                  const isLow = n > 0 && n < MIN_RELIABLE;
                  const isEmpty = n < MIN_DISPLAY;
                  const tooltip = isEmpty
                    ? `${pos} ${STREET_LABEL[s] ?? s}: sem dados (${n} decisões)`
                    : `${pos} ${STREET_LABEL[s] ?? s}: ${aligned?.toFixed(1)}% aligned · ${n} decisões${isLow ? " (amostra baixa)" : ""}${cell?.critical_pct != null ? ` · ${cell.critical_pct.toFixed(1)}% critical` : ""}`;
                  return (
                    <td
                      key={s}
                      className={cn(
                        "px-3 py-2 text-center font-mono cursor-help transition-opacity",
                        bg,
                        isLow && "opacity-60",
                        isEmpty && "opacity-30",
                      )}
                      title={tooltip}
                    >
                      {isEmpty ? (
                        <span className="text-[10px] text-muted-foreground/40">—</span>
                      ) : (
                        <div className="flex flex-col items-center gap-0.5">
                          <span className={cn("text-[11px] font-bold tabular-nums", text)}>
                            {aligned!.toFixed(0)}%
                          </span>
                          <span className="text-[8px] text-muted-foreground/70 tabular-nums">
                            n={n}
                          </span>
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-border/40 px-4 py-2 flex items-center gap-3 flex-wrap font-mono text-[9px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-emerald-500/20" />≥ 70%
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-amber-500/15" />55–70%
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-orange-500/15" />40–55%
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-sm bg-red-500/20" />&lt; 40%
        </span>
        <span className="ml-auto opacity-70">Células com n &lt; {MIN_RELIABLE} são atenuadas (amostra baixa).</span>
      </div>
    </div>
  );
}
