import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Award, TrendingUp, TrendingDown, Minus, BookOpen } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { metrics, EloResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

const STREET_LABEL: Record<string, string> = {
  preflop: "Preflop",
  flop:    "Flop",
  turn:    "Turn",
  river:   "River",
};

export default function Rating() {
  const [data, setData] = useState<EloResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    metrics.elo()
      .then(setData)
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <HudLayout
      eyebrow="Métrica do jogador"
      title="Rating ELO"
      description="Sistema de rating baseado em ELO adaptado para poker. Cada decisão é uma 'partida' contra o solver GTO."
    >
      {loading && (
        <div className="py-12 text-center font-mono text-sm text-muted-foreground">
          Carregando…
        </div>
      )}
      {error && (
        <div className="py-12 text-center text-sm text-destructive">
          {error}
        </div>
      )}
      {data && <RatingBody data={data} />}
    </HudLayout>
  );
}

function RatingBody({ data }: { data: EloResponse }) {
  const { overall, by_street, total_decisions, delta_7d, bands, history, no_data } = data;

  return (
    <div className="space-y-6 max-w-4xl">

      {/* Hero — ELO atual */}
      <div className="rounded-2xl border border-border/40 bg-card/60 p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              <Award className="size-3" />
              ELO atual
            </div>
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-5xl font-bold tabular-nums"
                    style={{ color: overall.band_color }}>
                {overall.elo.toFixed(0)}
              </span>
              <span className="font-mono text-base font-semibold"
                    style={{ color: overall.band_color }}>
                {overall.band_label}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-4 text-xs font-mono text-muted-foreground">
              <span>{total_decisions.toLocaleString()} decisões processadas</span>
              {!no_data && <DeltaBadge delta={delta_7d} />}
            </div>
          </div>

          <Link
            to="/docs/rating"
            className="inline-flex items-center gap-1.5 text-xs font-mono text-primary hover:underline shrink-0"
          >
            <BookOpen className="size-3.5" /> Como funciona
          </Link>
        </div>
      </div>

      {/* Breakdown por street */}
      {Object.keys(by_street).length > 0 && (
        <section className="space-y-2">
          <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Por street
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {(["preflop","flop","turn","river"] as const).map((st) => {
              const b = by_street[st];
              if (!b) return null;
              return (
                <div key={st}
                     className="rounded-lg border border-border/40 bg-card/40 p-3">
                  <div className="font-mono text-[9px] uppercase text-muted-foreground">
                    {STREET_LABEL[st]}
                  </div>
                  <div className="font-mono text-xl font-bold tabular-nums"
                       style={{ color: b.band_color }}>
                    {b.elo.toFixed(0)}
                  </div>
                  <div className="font-mono text-[9px]"
                       style={{ color: b.band_color }}>
                    {b.band_label}
                  </div>
                  <div className="font-mono text-[9px] text-muted-foreground mt-0.5">
                    {b.n_decisions} decs
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Bandas */}
      <section className="space-y-2">
        <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          Bandas de rating
        </h3>
        <div className="rounded-xl border border-border/40 bg-card/40 overflow-hidden">
          {bands.map((b, i) => {
            const isCurrent = overall.elo >= b.threshold &&
              (i === bands.length - 1 || overall.elo < bands[i + 1].threshold);
            const next = bands[i + 1];
            const rangeStr = next ? `${b.threshold} – ${next.threshold - 1}` : `${b.threshold}+`;
            return (
              <div key={b.label}
                   className={cn(
                     "flex items-center justify-between px-4 py-2 border-t border-border/30 first:border-t-0",
                     isCurrent && "bg-foreground/5"
                   )}>
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full" style={{ background: b.color }} />
                  <span className="font-mono text-sm font-semibold"
                        style={{ color: b.color }}>
                    {b.label}
                  </span>
                  {isCurrent && (
                    <span className="font-mono text-[9px] uppercase text-foreground/70 ml-2">
                      ← você está aqui
                    </span>
                  )}
                </div>
                <span className="font-mono text-xs text-muted-foreground tabular-nums">
                  {rangeStr}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Gráfico histórico (sparkline simples) */}
      {history.length >= 2 && (
        <section className="space-y-2">
          <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Evolução
          </h3>
          <div className="rounded-xl border border-border/40 bg-card/40 p-4">
            <Sparkline history={history} color={overall.band_color} />
            <div className="flex items-center justify-between mt-2 font-mono text-[10px] text-muted-foreground">
              <span>{history[history.length - 1]?.calculated_at?.slice(0, 10)}</span>
              <span>{history[0]?.calculated_at?.slice(0, 10)}</span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number | null }) {
  const Icon = delta == null ? Minus : delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
  const color = delta == null || delta === 0
    ? "text-muted-foreground"
    : delta > 0 ? "text-emerald-400" : "text-red-400";
  return (
    <span className={cn("flex items-center gap-1", color)}>
      <Icon className="size-3" />
      {delta == null ? "sem histórico de 7d" : `${delta > 0 ? "+" : ""}${delta.toFixed(1)} nos últimos 7 dias`}
    </span>
  );
}

function Sparkline({
  history, color,
}: {
  history: EloResponse["history"];
  color: string;
}) {
  // history vem mais novo primeiro; pra plot temporal, inverter
  const points = [...history].reverse();
  if (points.length < 2) return null;
  const values = points.map((p) => p.elo_overall);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1, max - min);
  const W = 800, H = 120, padY = 8;
  const stepX = W / (points.length - 1);
  const yOf = (v: number) => padY + (1 - (v - min) / range) * (H - 2 * padY);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(1)},${yOf(p.elo_overall).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-32" preserveAspectRatio="none">
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <text x="4" y="14" fontFamily="monospace" fontSize="10" fill="rgba(255,255,255,0.4)">
        max {max.toFixed(0)}
      </text>
      <text x="4" y={H - 4} fontFamily="monospace" fontSize="10" fill="rgba(255,255,255,0.4)">
        min {min.toFixed(0)}
      </text>
    </svg>
  );
}
