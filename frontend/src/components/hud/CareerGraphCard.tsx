import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { TrendingUp, TrendingDown, Minus, Target, AlertCircle, ChevronRight } from "lucide-react";
import { CareerProjection, CareerMilestone, metrics, EloResponse, EloCurveResponse } from "@/lib/api";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";
import { cn, formatAction } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";
import { AiText } from "@/components/ui/AiText";

const LEVEL_SLUG: Record<string, string> = {
  "Iniciante": "beginner",
  "Estudante": "student",
  "Grinder":   "grinder",
  "Regular":   "regular",
  "Sólido":    "solid",
  "Expert":    "expert",
  "Elite":     "elite",
};

const MILESTONE_COLOR: Record<string, string> = {
  beginner: "text-muted-foreground",
  student:  "text-blue-400",
  grinder:  "text-amber-400",
  regular:  "text-emerald-400",
  solid:    "text-primary",
  expert:   "text-violet-400",
  elite:    "text-amber-300",
};

const PROGRESS_COLOR: Record<string, string> = {
  beginner: "bg-muted-foreground",
  student:  "bg-blue-400",
  grinder:  "bg-amber-400",
  regular:  "bg-emerald-400",
  solid:    "bg-primary",
  expert:   "bg-violet-400",
  elite:    "bg-amber-300",
};

function Sparkline({ history, projection }: { history: number[]; projection: number[] }) {
  const all    = [...history, ...projection];
  const W      = 260;
  const H      = 52;
  const min    = Math.min(...all, 0);
  const max    = Math.max(...all, 100);
  const range  = max - min || 1;
  const total  = all.length;
  const stepX  = W / (total - 1);

  const toCoord = (v: number, i: number) => ({
    x: i * stepX,
    y: H - ((v - min) / range) * H * 0.9 - H * 0.05,
  });

  const histCoords = history.map((v, i) => toCoord(v, i));
  const projCoords = projection.map((v, i) => toCoord(v, history.length - 1 + i));

  const histPath = useMemo(() => {
    if (histCoords.length < 2) return "";
    return histCoords
      .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
      .join(" ");
  }, [histCoords]);

  const projPath = useMemo(() => {
    if (projCoords.length < 2) return "";
    return projCoords
      .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
      .join(" ");
  }, [projCoords]);

  // Area fill for history
  const areaPath = useMemo(() => {
    if (histCoords.length < 2) return "";
    const line = histCoords
      .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
      .join(" ");
    const last = histCoords[histCoords.length - 1];
    const first = histCoords[0];
    return `${line} L ${last.x} ${H} L ${first.x} ${H} Z`;
  }, [histCoords, H]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 52 }} aria-hidden>
      {/* Gradient area */}
      <defs>
        <linearGradient id="cg-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="hsl(var(--primary))" stopOpacity="0.18" />
          <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#cg-area)" />
      {/* Historical line */}
      {histPath && (
        <path d={histPath} fill="none" stroke="hsl(var(--primary))" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      )}
      {/* Projected line — dashed */}
      {projPath && (
        <path d={projPath} fill="none" stroke="hsl(var(--primary))" strokeWidth={1.2} strokeDasharray="3 3" strokeLinecap="round" strokeOpacity={0.55} />
      )}
      {/* Current point */}
      {histCoords.length > 0 && (() => {
        const last = histCoords[histCoords.length - 1];
        return <circle cx={last.x} cy={last.y} r={2.5} fill="hsl(var(--primary))" />;
      })()}
    </svg>
  );
}

// Deriva a banda/nível pra um ELO arbitrário usando a lista de bands da API.
function bandForElo(eloVal: number, bands: EloResponse["bands"]) {
  let chosen = bands[0];
  for (const b of bands) if (eloVal >= b.threshold) chosen = b;
  return chosen; // { threshold, icon, label, color }
}

function EloMiniCurve({ points, color }: { points: number[]; color: string }) {
  if (points.length < 2) return null;
  const min = Math.min(...points), max = Math.max(...points);
  const pad = Math.max(15, (max - min) * 0.15);
  const lo = min - pad, hi = max + pad;
  const range = Math.max(1, hi - lo);
  const W = 260, H = 52, padY = 6;
  const stepX = W / (points.length - 1);
  const yOf = (v: number) => padY + (1 - (v - lo) / range) * (H - 2 * padY);
  const line = points.map((v, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(1)} ${yOf(v).toFixed(1)}`).join(" ");
  const area = `${line} L ${W} ${H} L 0 ${H} Z`;
  const gid = `cg-elo-${points.length}-${Math.round(min)}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 52 }} aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.20" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={W} cy={yOf(points[points.length - 1])} r={2.5} fill={color} />
    </svg>
  );
}

interface Props {
  data: CareerProjection;
  hideNarrative?: boolean;
  v2?: boolean;
}

export function CareerGraphCard({ data, hideNarrative = false, v2 = false }: Props) {
  const { t, i18n } = useTranslation("dashboard");
  const [elo, setElo] = useState<EloResponse | null>(null);
  const [curve, setCurve] = useState<EloCurveResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    metrics.elo().then((r) => { if (!cancelled) setElo(r); }).catch(() => {});
    metrics.eloCurve().then((r) => { if (!cancelled) setCurve(r); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (data.insufficient_data) {
    return (
      <div className={v2 ? "rounded-xl ring-1 ring-border bg-card/60 p-5 space-y-2" : "rounded-xl border border-border bg-hud-surface p-5 space-y-2"}>
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
          <Target className="size-3" /> {t("career.eyebrow")}
        </p>
        <p className="text-xs text-muted-foreground">{t("career.noData")}</p>
      </div>
    );
  }

  const slug     = LEVEL_SLUG[data.current_level!] ?? "beginner";
  const colorCls = MILESTONE_COLOR[slug] ?? "text-primary";
  const slope    = data.slope_per_tournament ?? 0;
  const nm       = data.next_milestone;

  const TrendIcon = slope > 0.05 ? TrendingUp : slope < -0.05 ? TrendingDown : Minus;
  const trendLabel =
    slope > 0.05 ? t("career.improving", { v: slope.toFixed(2) }) :
    slope < -0.05 ? t("career.declining") :
    t("career.stagnant");

  const levelName = t(`level.names.${slug}`, { defaultValue: data.current_level });

  const formatDate = (iso?: string) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleDateString(i18n.language, { month: "short", year: "numeric" });
    } catch {
      return iso;
    }
  };

  const EloIcon = elo ? LEVEL_ICONS[elo.overall.band_label] : null;

  return (
    <div className={v2 ? "rounded-xl ring-1 ring-border bg-card/60 overflow-hidden" : "rounded-xl border border-border bg-hud-surface overflow-hidden"}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          <Target className="size-3" aria-hidden />
          {t("career.title")}
          <HudTooltip content={t("career.tooltip")} />
        </h2>
        <span className={cn("flex items-center gap-1 font-mono text-[10px]", slope > 0.05 ? "text-emerald-400" : slope < -0.05 ? "text-destructive" : "text-muted-foreground")}>
          <TrendIcon className="size-3" />
          {trendLabel}
        </span>
      </div>

      {/* Rating ELO em destaque — clicável pra página completa */}
      {elo && (
        <Link to="/rating"
              className="flex items-center justify-between gap-3 px-4 py-3 border-b border-border bg-background/40 hover:bg-background/70 transition-colors group">
          <div className="flex items-center gap-3 min-w-0">
            {EloIcon && <EloIcon size={28} className="shrink-0" />}
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold tabular-nums leading-none"
                      style={{ color: elo.overall.band_color }}>
                  {elo.overall.elo.toFixed(0)}
                </span>
                <span className="font-mono text-xs font-semibold"
                      style={{ color: elo.overall.band_color }}>
                  {elo.overall.band_label}
                </span>
                <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">ELO</span>
              </div>
              {elo.next_band && (
                <div className="mt-1 flex items-center gap-2">
                  <div className="h-1 w-24 rounded-full bg-muted/20 overflow-hidden">
                    <div className="h-full rounded-full"
                         style={{ width: `${elo.next_band.progress * 100}%`, background: elo.overall.band_color }} />
                  </div>
                  <span className="font-mono text-[9px] text-muted-foreground">
                    {t("career.toNext", { n: elo.next_band.elo_to_go.toFixed(0), band: elo.next_band.label })}
                  </span>
                </div>
              )}
            </div>
          </div>
          <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground/60 transition-colors shrink-0" />
        </Link>
      )}

      <div className="p-4 space-y-4">
        {/* Mini-curva de ELO (forma recente) */}
        {curve && curve.recent.length > 1 ? (
          <div className="space-y-1">
            <EloMiniCurve points={curve.recent.map(p => p.elo)} color={elo?.overall.band_color ?? "hsl(var(--primary))"} />
            <span className="font-mono text-[9px] text-muted-foreground">
              {t("career.recentRating")}
              {v2 && curve.recent.length > 1 && (
                <span className="ml-2 tabular-nums text-foreground/70">
                  {curve.recent[0].elo.toFixed(0)} → {curve.recent[curve.recent.length - 1].elo.toFixed(0)}
                </span>
              )}
            </span>
          </div>
        ) : data.series_history && data.series_history.length > 1 ? (
          <div className="space-y-1">
            <Sparkline
              history={data.series_history}
              projection={data.series_projection ?? []}
            />
            <div className="flex items-center justify-between">
              <span className="font-mono text-[9px] text-muted-foreground">
                {t("career.analyzedCount", { n: data.tournament_count })}
              </span>
              <span className="flex items-center gap-1 font-mono text-[9px] text-muted-foreground">
                <span className="inline-block w-4 border-t border-dashed border-muted-foreground/40" />
                {t("career.projection")}
              </span>
            </div>
          </div>
        ) : null}

        {/* Histórico (all-time) vs Forma recente (25t) — ambos ELO */}
        {elo && curve && curve.all_time.length > 0 ? (() => {
          const allTimeElo = curve.all_time[curve.all_time.length - 1].elo;
          const allBand = bandForElo(allTimeElo, elo.bands);
          const AllIcon = LEVEL_ICONS[allBand.label];
          const recBand = elo.overall;
          const RecIcon = LEVEL_ICONS[recBand.band_label];
          // V2: o bloco hero do topo JÁ É a forma recente (mesmo número + mesma
          // barra) — repetir num box é duplicação. Vira uma linha compacta só com
          // o histórico + delta da forma vs ele. Clássico mantém os dois boxes.
          if (v2) {
            const delta = Math.round(recBand.elo - allTimeElo);
            return (
              <div className="flex items-center justify-between gap-3 rounded-lg ring-1 ring-border/60 bg-background/40 px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground shrink-0">
                    {t("career.allTime")}
                  </span>
                  {AllIcon && <AllIcon size={14} className="shrink-0" />}
                  <span className="font-mono text-sm font-bold tabular-nums" style={{ color: allBand.color }}>
                    {allTimeElo.toFixed(0)}
                  </span>
                  <span className="font-mono text-[10px]" style={{ color: allBand.color }}>{allBand.label}</span>
                </div>
                <span className={`font-mono text-[10px] font-bold tabular-nums shrink-0 ${
                  delta >= 0 ? "text-emerald-400" : "text-red-400"
                }`}>
                  {t("v2.careerDelta", { delta: `${delta >= 0 ? "+" : ""}${delta}` })}
                </span>
              </div>
            );
          }
          return (
            <div className="grid grid-cols-2 gap-3">
              {/* Histórico */}
              <div className="rounded-lg border border-border bg-background p-3 space-y-1.5">
                <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.allTime")}</p>
                <div className="flex items-center gap-1.5">
                  {AllIcon && <AllIcon size={16} className="shrink-0" />}
                  <span className="font-mono text-sm font-bold" style={{ color: allBand.color }}>{allBand.label}</span>
                </div>
                <p className="font-mono text-lg font-bold tabular-nums" style={{ color: allBand.color }}>
                  {allTimeElo.toFixed(0)} <span className="text-[9px] text-muted-foreground font-normal">ELO</span>
                </p>
                <p className="font-mono text-[9px] text-muted-foreground/60">{t("career.allTimeRating")}</p>
              </div>
              {/* Forma recente */}
              <div className="rounded-lg border border-border bg-background p-3 space-y-1.5">
                <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.recentForm")}</p>
                <div className="flex items-center gap-1.5">
                  {RecIcon && <RecIcon size={16} className="shrink-0" />}
                  <span className="font-mono text-sm font-bold" style={{ color: recBand.band_color }}>{recBand.band_label}</span>
                </div>
                <p className="font-mono text-lg font-bold tabular-nums" style={{ color: recBand.band_color }}>
                  {recBand.elo.toFixed(0)} <span className="text-[9px] text-muted-foreground font-normal">ELO</span>
                </p>
                {elo.next_band ? (
                  <>
                    <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700"
                           style={{ width: `${elo.next_band.progress * 100}%`, background: recBand.band_color }} />
                    </div>
                    <p className="font-mono text-[9px] text-muted-foreground/70">
                      {t("career.toNext", { n: elo.next_band.elo_to_go.toFixed(0), band: elo.next_band.label })}
                    </p>
                  </>
                ) : (
                  <p className="font-mono text-[9px] text-muted-foreground/60">{t("career.recentRating")}</p>
                )}
              </div>
            </div>
          );
        })() : (
          /* Fallback %-based enquanto ELO/curva não carregam */
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-background p-3 space-y-1.5">
              <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.currentLevel")}</p>
              <p className={cn("font-mono text-sm font-bold", colorCls)}>{levelName}</p>
              <p className="font-mono text-[10px] text-muted-foreground">{data.current_avg?.toFixed(0)} ELO</p>
            </div>
            {nm && nm.reachable && (
              <div className="rounded-lg border border-border bg-background p-3 space-y-1">
                <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.nextLevel")}</p>
                <p className={cn("font-mono text-sm font-bold", MILESTONE_COLOR[nm.level_slug] ?? "text-primary")}>
                  {t(`level.names.${nm.level_slug}`, { defaultValue: nm.level_name })}
                </p>
                {nm.estimated_date && nm.months_needed! > 0 && (
                  <p className="font-mono text-[9px] text-muted-foreground">
                    {t("career.estimatedDate", { date: formatDate(nm.estimated_date) })}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Milestones timeline */}
        {data.milestones && data.milestones.length > 0 && (
          <div className="space-y-1.5">
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground flex items-center gap-1">
              <TrendingUp className="size-3" /> {t("career.milestones")}
            </p>
            <div className={v2 ? "relative" : "space-y-1"}>
              {/* V2: ESCADA — linha vertical conectando as bands; ● alcançado,
                  ◉ próximo (anel na cor), ○ futuro/fora de alcance. */}
              {v2 && <span className="absolute left-[5px] top-2 bottom-2 w-px bg-border/60" aria-hidden />}
              {data.milestones.slice(0, 4).map((m) => {
                const Icon = LEVEL_ICONS[m.level_name];
                const mColor = MILESTONE_COLOR[m.level_slug] ?? "text-muted-foreground";
                const mName = t(`level.names.${m.level_slug}`, { defaultValue: m.level_name });
                const status = !m.reachable
                  ? t("career.notReachable")
                  : m.months_needed === 0
                  ? t("career.already")
                  : t("career.monthsAway", { n: m.months_needed });
                if (!v2) {
                  return (
                    <div key={m.level_slug} className="flex items-center justify-between text-[11px]">
                      <span className={cn("flex items-center gap-1.5 font-mono font-semibold", mColor)}>
                        {Icon && <Icon size={11} />}
                        {mName}
                        <span className="text-muted-foreground font-normal">({m.threshold} ELO)</span>
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">{status}</span>
                    </div>
                  );
                }
                const reached = m.reachable && m.months_needed === 0;
                const isNext  = m.reachable && (m.months_needed ?? 0) > 0
                  && data.milestones!.slice(0, 4).find(x => x.reachable && (x.months_needed ?? 0) > 0)?.level_slug === m.level_slug;
                return (
                  <div key={m.level_slug} className="relative flex items-center justify-between gap-2 py-1 pl-5 text-[11px]">
                    <span
                      aria-hidden
                      className={cn(
                        "absolute left-0 top-1/2 -translate-y-1/2 size-[11px] rounded-full border-2",
                        reached ? "bg-current border-current" : isNext ? "bg-background border-current" : "bg-background border-border",
                        reached || isNext ? mColor : "text-border"
                      )}
                    />
                    <span className={cn(
                      "flex items-center gap-1.5 font-mono font-semibold min-w-0",
                      m.reachable ? mColor : "text-muted-foreground/50"
                    )}>
                      {Icon && <Icon size={11} />}
                      <span className="truncate">{mName}</span>
                      <span className="text-muted-foreground font-normal shrink-0">({m.threshold})</span>
                    </span>
                    <span className={cn(
                      "font-mono text-[10px] tabular-nums shrink-0",
                      reached ? "text-emerald-400" : isNext ? "text-foreground/80" : "text-muted-foreground/60"
                    )}>
                      {reached ? "✓ " : isNext ? "≈ " : ""}{status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Blocking leaks */}
        {data.blocking_leaks && data.blocking_leaks.length > 0 && (
          <div className="space-y-1.5">
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground flex items-center gap-1">
              <AlertCircle className="size-3" /> {t("career.blockingLeaks")}
            </p>
            <ul className="space-y-0.5">
              {data.blocking_leaks.map((lk) => (
                <li key={lk.spot} className="flex items-center justify-between text-[11px]">
                  <span className="text-foreground truncate">{(() => {
                    if (!v2) return lk.spot;
                    const [st, act] = lk.spot.split("/");
                    return st && act
                      ? t("v2.causalSpot", { action: formatAction(act), street: st })
                      : lk.spot;
                  })()}</span>
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 ml-2">{lk.n}×</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* LLM Narrative */}
        {data.narrative && !hideNarrative && (
          <div className="border-t border-border pt-3">
            <AiText size="xs">{data.narrative}</AiText>
          </div>
        )}
      </div>
    </div>
  );
}
