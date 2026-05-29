import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Award, TrendingUp, TrendingDown, Minus, BookOpen } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { metrics, EloResponse, EloCurveResponse, EloCurvePoint } from "@/lib/api";
import { cn } from "@/lib/utils";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";

const STREET_LABEL: Record<string, string> = {
  preflop: "Preflop",
  flop:    "Flop",
  turn:    "Turn",
  river:   "River",
};

export default function Rating() {
  const { t } = useTranslation("dashboard");
  const [data, setData] = useState<EloResponse | null>(null);
  const [curve, setCurve] = useState<EloCurveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([metrics.elo(), metrics.eloCurve().catch(() => null)])
      .then(([elo, c]) => { setData(elo); setCurve(c); })
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <HudLayout
      eyebrow={t("elo.page.eyebrow")}
      title={t("elo.page.title")}
      description={t("elo.page.description")}
    >
      {loading && (
        <div className="py-12 text-center font-mono text-sm text-muted-foreground">
          {t("elo.page.loading")}
        </div>
      )}
      {error && (
        <div className="py-12 text-center text-sm text-destructive">
          {error}
        </div>
      )}
      {data && <RatingBody data={data} curve={curve} />}
    </HudLayout>
  );
}

function RatingBody({ data, curve }: { data: EloResponse; curve: EloCurveResponse | null }) {
  const { t } = useTranslation("dashboard");
  const { overall, by_street, total_decisions, delta_7d, bands, history, no_data, next_band, peak_elo } = data;
  const bandName = (label: string) => t(`elo.bands.${label}`, { defaultValue: label });

  return (
    <div className="space-y-6 max-w-4xl">

      {/* Hero — ELO atual */}
      <div className="rounded-2xl border border-border/40 bg-card/60 p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              <Award className="size-3" />
              {data.window_tournaments
                ? t("elo.page.recentFormWindow", { n: data.window_tournaments })
                : t("elo.page.recentForm")}
            </div>
            <div className="flex items-center gap-3">
              {(() => { const I = LEVEL_ICONS[overall.band_label]; return I ? <I size={40} className="shrink-0" /> : null; })()}
              <span className="font-mono text-5xl font-bold tabular-nums leading-none"
                    style={{ color: overall.band_color }}>
                {overall.elo.toFixed(0)}
              </span>
              <span className="font-mono text-base font-semibold"
                    style={{ color: overall.band_color }}>
                {bandName(overall.band_label)}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-4 flex-wrap text-xs font-mono text-muted-foreground">
              <span>{t("elo.page.decisionsGto", { n: total_decisions.toLocaleString() })}</span>
              {!no_data && <DeltaBadge delta={delta_7d} />}
              {peak_elo != null && (
                <span className="text-muted-foreground/80">{t("elo.page.peak", { n: peak_elo.toFixed(0) })}</span>
              )}
              {!!data.decay_applied && data.decay_applied > 0 && (
                <span
                  className="text-amber-400/80"
                  title={t("elo.inactiveTip", { pts: data.decay_applied.toFixed(0), weeks: Math.round(data.weeks_inactive ?? 0) })}
                >
                  {t("elo.inactiveLong", { pts: data.decay_applied.toFixed(0) })}
                </span>
              )}
            </div>

            {/* Progresso até o próximo nível */}
            {next_band && (
              <div className="mt-3 max-w-sm space-y-1">
                <div className="h-1.5 rounded-full bg-muted/20 overflow-hidden">
                  <div className="h-full rounded-full transition-all"
                       style={{ width: `${next_band.progress * 100}%`, background: overall.band_color }} />
                </div>
                <div className="font-mono text-[10px] text-muted-foreground">
                  {t("elo.page.toNextBand", {
                    pts: next_band.elo_to_go.toFixed(0),
                    icon: next_band.icon,
                    band: bandName(next_band.label),
                  })}
                </div>
              </div>
            )}
          </div>

          <Link
            to="/docs/rating"
            className="inline-flex items-center gap-1.5 text-xs font-mono text-primary hover:underline shrink-0"
          >
            <BookOpen className="size-3.5" /> {t("elo.page.howItWorks")}
          </Link>
        </div>
      </div>

      {/* Breakdown por street */}
      {Object.keys(by_street).length > 0 && (
        <section className="space-y-2">
          <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {t("elo.page.byStreet")}
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
                  <div className="flex items-center gap-1 font-mono text-[9px]"
                       style={{ color: b.band_color }}>
                    {(() => { const I = LEVEL_ICONS[b.band_label]; return I ? <I size={11} /> : null; })()}
                    {bandName(b.band_label)}
                  </div>
                  <div className="font-mono text-[9px] text-muted-foreground mt-0.5">
                    {t("elo.page.decs", { n: b.n_decisions })}
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
          {t("elo.page.bandsTitle")}
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
                  {(() => { const I = LEVEL_ICONS[b.label]; return I ? <I size={16} className="shrink-0" /> : null; })()}
                  <span className="font-mono text-sm font-semibold"
                        style={{ color: b.color }}>
                    {bandName(b.label)}
                  </span>
                  {isCurrent && (
                    <span className="font-mono text-[9px] uppercase text-foreground/70 ml-2">
                      {t("elo.page.youAreHere")}
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

      {/* Curvas de ELO — histórico (all-time) e forma recente */}
      {curve && curve.all_time.length >= 2 && (
        <section className="space-y-2">
          <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {t("elo.page.evolution")}
          </h3>
          <div className="rounded-xl border border-border/40 bg-card/40 p-4 space-y-1">
            <div className="font-mono text-[10px] text-muted-foreground">
              {t("elo.page.historicCurve", { n: curve.all_time.length })}
            </div>
            <EloCurveChart points={curve.all_time} color={overall.band_color} />
          </div>
          {curve.recent.length >= 2 && (
            <div className="rounded-xl border border-border/40 bg-card/40 p-4 space-y-1">
              <div className="font-mono text-[10px] text-muted-foreground">
                {t("elo.page.recentCurve", { n: curve.window_tournaments })}
              </div>
              <EloCurveChart points={curve.recent} color={overall.band_color} />
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number | null }) {
  const { t } = useTranslation("dashboard");
  const Icon = delta == null ? Minus : delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
  const color = delta == null || delta === 0
    ? "text-muted-foreground"
    : delta > 0 ? "text-emerald-400" : "text-red-400";
  return (
    <span className={cn("flex items-center gap-1", color)}>
      <Icon className="size-3" />
      {delta == null
        ? t("elo.page.noDelta")
        : t("elo.page.deltaDays", { val: `${delta > 0 ? "+" : ""}${delta.toFixed(1)}` })}
    </span>
  );
}

function EloCurveChart({ points, color }: { points: EloCurvePoint[]; color: string }) {
  const { t } = useTranslation("dashboard");
  if (points.length < 2) return null;
  const values = points.map((p) => p.elo);
  const min = Math.min(...values);
  const max = Math.max(...values);
  // padding do range pra curva não colar nas bordas
  const pad = Math.max(20, (max - min) * 0.15);
  const lo = min - pad, hi = max + pad;
  const range = Math.max(1, hi - lo);
  const W = 800, H = 140, padY = 10;
  const stepX = W / (points.length - 1);
  const yOf = (v: number) => padY + (1 - (v - lo) / range) * (H - 2 * padY);
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(1)},${yOf(p.elo).toFixed(1)}`).join(" ");
  const area = `${line} L ${W},${H} L 0,${H} Z`;
  const last = points[points.length - 1];
  const gradId = `elo-area-${Math.round(min)}-${points.length}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36" preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.20" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {/* ponto final */}
      <circle cx={(W).toFixed(1)} cy={yOf(last.elo).toFixed(1)} r="3" fill={color} />
      <text x="6" y="16" fontFamily="monospace" fontSize="11" fill="rgba(255,255,255,0.45)">
        {t("elo.page.chartMax", { n: max.toFixed(0) })}
      </text>
      <text x="6" y={H - 6} fontFamily="monospace" fontSize="11" fill="rgba(255,255,255,0.45)">
        {t("elo.page.chartMin", { n: min.toFixed(0) })}
      </text>
    </svg>
  );
}
