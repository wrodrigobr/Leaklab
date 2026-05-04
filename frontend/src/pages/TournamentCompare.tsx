import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { cn } from "@/lib/utils";
import { tournaments as tournamentsApi, TournamentComparison } from "@/lib/api";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
  } catch { return iso.slice(0, 10); }
}

function Delta({ a, b, higherBetter = true, unit = "" }: {
  a: number | null; b: number | null; higherBetter?: boolean; unit?: string;
}) {
  if (a == null || b == null) return null;
  const diff = b - a;
  if (Math.abs(diff) < 0.001) return (
    <span className="inline-flex items-center gap-0.5 font-mono text-[9px] text-muted-foreground">
      <Minus className="size-2.5" />—
    </span>
  );
  const positive = higherBetter ? diff > 0 : diff < 0;
  const sign = diff > 0 ? "+" : "";
  return (
    <span className={cn("inline-flex items-center gap-0.5 font-mono text-[9px] font-bold", positive ? "text-primary" : "text-destructive")}>
      {positive ? <TrendingUp className="size-2.5" /> : <TrendingDown className="size-2.5" />}
      {sign}{diff.toFixed(unit === "pp" ? 1 : 3)}{unit}
    </span>
  );
}

function QualityBar({ value, max = 100 }: { value: number | null; max?: number }) {
  if (value == null) return <span className="text-muted-foreground font-mono text-xs">—</span>;
  const pct = Math.min(100, (value / max) * 100);
  const color = value >= 75 ? "bg-primary" : value >= 60 ? "bg-yellow-400" : "bg-destructive";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs font-bold tabular-nums text-foreground w-10 text-right">
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

export default function TournamentCompare() {
  const [params] = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").filter(Boolean);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [items, setItems] = useState<TournamentComparison[]>([]);
  const [narrative, setNarrative] = useState("");

  useEffect(() => {
    if (ids.length < 2) { setError("Selecione pelo menos 2 torneios."); setLoading(false); return; }
    tournamentsApi.compare(ids)
      .then((r) => { setItems(r.items); setNarrative(r.narrative); })
      .catch((e) => setError(e.message ?? "Erro ao carregar comparativo"))
      .finally(() => setLoading(false));
  }, [params.get("ids")]);

  // Compute best/worst indices for each metric
  function bestIdx(vals: (number | null)[], higherBetter = true) {
    const valid = vals.map((v, i) => ({ v, i })).filter((x) => x.v != null) as { v: number; i: number }[];
    if (!valid.length) return -1;
    return valid.reduce((best, cur) => (higherBetter ? cur.v > best.v : cur.v < best.v) ? cur : best).i;
  }

  const stdBest  = bestIdx(items.map((i) => i.standard_pct));
  const scoreBest = bestIdx(items.map((i) => i.avg_score), false);
  const clearBest = bestIdx(items.map((i) => i.clear_pct), false);

  return (
    <HudLayout eyebrow="Sprint O · FEAT-01" title="Comparativo de Torneios" description="Análise evolutiva lado a lado de qualidade técnica de decisão.">
      <Link
        to="/tournaments"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground hover:text-primary transition-colors"
      >
        <ArrowLeft className="size-3.5" />
        Voltar para Torneios
      </Link>

      {loading && (
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">Carregando comparativo…</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && items.length >= 2 && (
        <div className="space-y-6">

          {/* ── Narrative ───────────────────────────────────────────────────── */}
          {narrative && (
            <div className="rounded-xl border border-primary/20 bg-primary/5 px-5 py-4">
              <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary mb-1.5">
                Análise Comparativa IA
              </p>
              <p className="text-sm leading-relaxed text-foreground">{narrative}</p>
            </div>
          )}

          {/* ── Header cards ────────────────────────────────────────────────── */}
          <div className={cn("grid gap-3", items.length === 2 ? "grid-cols-2" : items.length === 3 ? "grid-cols-3" : "grid-cols-2 md:grid-cols-4")}>
            {items.map((item, idx) => {
              const profit = item.profit;
              return (
                <div key={item.tournament_id} className="rounded-xl border border-border bg-hud-surface p-4 space-y-1">
                  <div className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
                    Torneio {idx + 1} · {formatDate(item.played_at)}
                  </div>
                  <div className="text-sm font-semibold text-foreground leading-snug truncate">
                    {item.tournament_name ?? `#${item.tournament_id}`}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-[10px] text-muted-foreground">{item.site}</span>
                    {item.buy_in != null && (
                      <span className="font-mono text-[10px] text-muted-foreground">${item.buy_in}</span>
                    )}
                    {profit != null && (
                      <span className={cn("font-mono text-[11px] font-bold", profit >= 0 ? "text-primary" : "text-destructive")}>
                        {profit >= 0 ? "+" : ""}${Math.abs(profit).toFixed(0)}
                      </span>
                    )}
                  </div>
                  <div className="font-mono text-[9px] text-muted-foreground">
                    {item.decisions_count ?? 0} decisões · {item.hands_count ?? 0} mãos
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── Quality metrics table ───────────────────────────────────────── */}
          <section className="rounded-xl border border-border overflow-hidden">
            <div className="border-b border-border bg-hud-elevated/40 px-4 py-2">
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Qualidade de Decisão
              </span>
            </div>

            {/* Standard % */}
            <div className="divide-y divide-border/50">
              {[
                {
                  label: "Standard %",
                  sub: "Decisões dentro do padrão — quanto maior, melhor",
                  render: (item: TournamentComparison, idx: number) => (
                    <div className="space-y-1">
                      <QualityBar value={item.standard_pct} />
                      {idx > 0 && <Delta a={items[0].standard_pct} b={item.standard_pct} higherBetter unit="pp" />}
                      {idx === stdBest && <span className="font-mono text-[9px] text-primary font-bold">▲ melhor</span>}
                    </div>
                  ),
                },
                {
                  label: "Avg Score",
                  sub: "Score médio de erro — quanto menor, melhor",
                  render: (item: TournamentComparison, idx: number) => (
                    <div className="space-y-1">
                      <span className={cn("font-mono text-sm font-bold tabular-nums", (item.avg_score ?? 0) < 0.12 ? "text-primary" : (item.avg_score ?? 0) < 0.2 ? "text-yellow-400" : "text-destructive")}>
                        {item.avg_score?.toFixed(4) ?? "—"}
                      </span>
                      {idx > 0 && <Delta a={items[0].avg_score} b={item.avg_score} higherBetter={false} />}
                      {idx === scoreBest && <span className="font-mono text-[9px] text-primary font-bold">▲ melhor</span>}
                    </div>
                  ),
                },
                {
                  label: "Clear Mistakes %",
                  sub: "Erros claros — quanto menor, melhor",
                  render: (item: TournamentComparison, idx: number) => (
                    <div className="space-y-1">
                      <span className={cn("font-mono text-sm font-bold tabular-nums", (item.clear_pct ?? 0) < 5 ? "text-primary" : (item.clear_pct ?? 0) < 15 ? "text-yellow-400" : "text-destructive")}>
                        {item.clear_pct?.toFixed(1) ?? "—"}%
                      </span>
                      {idx > 0 && <Delta a={items[0].clear_pct} b={item.clear_pct} higherBetter={false} unit="pp" />}
                      {idx === clearBest && <span className="font-mono text-[9px] text-primary font-bold">▲ melhor</span>}
                    </div>
                  ),
                },
              ].map(({ label, sub, render }) => (
                <div key={label} className={cn("grid gap-px bg-border", items.length === 2 ? "grid-cols-[180px_1fr_1fr]" : items.length === 3 ? "grid-cols-[180px_1fr_1fr_1fr]" : "grid-cols-[180px_1fr_1fr_1fr_1fr]")}>
                  <div className="bg-hud-surface px-4 py-3">
                    <div className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</div>
                    <div className="font-mono text-[9px] text-muted-foreground/60 mt-0.5 leading-tight">{sub}</div>
                  </div>
                  {items.map((item, idx) => (
                    <div key={item.tournament_id} className="bg-hud-surface px-4 py-3">
                      {render(item, idx)}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </section>

          {/* ── Phase breakdown ─────────────────────────────────────────────── */}
          {items.some((i) => i.phases.length > 0) && (
            <section className="rounded-xl border border-border overflow-hidden">
              <div className="border-b border-border bg-hud-elevated/40 px-4 py-2">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Phase Breakdown (M-Ratio)
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="border-b border-border">
                    <tr>
                      <th className="px-4 py-2 text-left font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Phase</th>
                      {items.map((item, idx) => (
                        <th key={item.tournament_id} className="px-4 py-2 text-right font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                          T{idx + 1} — Avg Score
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {["Deep Stack", "Mid Stack", "Short Stack", "Push/Fold"].map((phase) => (
                      <tr key={phase} className="hover:bg-hud-elevated/20">
                        <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground">{phase}</td>
                        {items.map((item) => {
                          const p = item.phases.find((ph) => ph.phase === phase);
                          return (
                            <td key={item.tournament_id} className="px-4 py-2.5 text-right">
                              {p ? (
                                <span className={cn("font-mono text-[11px] font-bold tabular-nums", p.avg_score < 0.1 ? "text-primary" : p.avg_score < 0.2 ? "text-yellow-400" : "text-destructive")}>
                                  {p.avg_score.toFixed(3)}
                                  <span className="text-muted-foreground font-normal ml-1">({p.n})</span>
                                </span>
                              ) : (
                                <span className="text-muted-foreground font-mono text-[10px]">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* ── Top leaks comparison ────────────────────────────────────────── */}
          {items.some((i) => i.top_leaks.length > 0) && (
            <section className="rounded-xl border border-border overflow-hidden">
              <div className="border-b border-border bg-hud-elevated/40 px-4 py-2">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Top Leaks por Torneio
                </span>
              </div>
              <div className={cn("grid gap-px bg-border", items.length === 2 ? "grid-cols-2" : items.length === 3 ? "grid-cols-3" : "grid-cols-2 md:grid-cols-4")}>
                {items.map((item, idx) => (
                  <div key={item.tournament_id} className="bg-hud-surface px-4 py-3 space-y-2">
                    <div className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">T{idx + 1}</div>
                    {item.top_leaks.slice(0, 4).map(([spot, score, n]) => {
                      const label = spot.replace(/_/g, " ").replace(/\//g, " / ");
                      const isShared = items.some((other, oi) => oi !== idx && other.top_leaks.some(([s]) => s === spot));
                      return (
                        <div key={spot} className="flex items-start justify-between gap-2">
                          <span className={cn("text-[10px] leading-snug", isShared ? "text-yellow-400" : "text-foreground")}>
                            {label}
                          </span>
                          <div className="shrink-0 text-right">
                            <div className={cn("font-mono text-[10px] font-bold tabular-nums", score >= 0.36 ? "text-destructive" : score >= 0.2 ? "text-yellow-400" : "text-primary")}>
                              {score.toFixed(3)}
                            </div>
                            <div className="font-mono text-[9px] text-muted-foreground">{n}×</div>
                          </div>
                        </div>
                      );
                    })}
                    {item.top_leaks.length === 0 && (
                      <p className="text-[10px] text-muted-foreground">Sem leaks recorrentes</p>
                    )}
                  </div>
                ))}
              </div>
              <div className="border-t border-border/40 px-4 py-2">
                <span className="font-mono text-[9px] text-muted-foreground">
                  <span className="text-yellow-400">■</span> Leak presente em múltiplos torneios
                </span>
              </div>
            </section>
          )}

        </div>
      )}
    </HudLayout>
  );
}
