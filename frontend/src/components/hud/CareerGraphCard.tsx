import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { TrendingUp, TrendingDown, Minus, Target, AlertCircle, ChevronRight } from "lucide-react";
import { CareerProjection, CareerMilestone, metrics, EloResponse } from "@/lib/api";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";
import { cn } from "@/lib/utils";
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

interface Props {
  data: CareerProjection;
}

export function CareerGraphCard({ data }: Props) {
  const { t, i18n } = useTranslation("dashboard");
  const [elo, setElo] = useState<EloResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    metrics.elo().then((r) => { if (!cancelled) setElo(r); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (data.insufficient_data) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-2">
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
    <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
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
                    {elo.next_band.elo_to_go.toFixed(0)} pra {elo.next_band.label}
                  </span>
                </div>
              )}
            </div>
          </div>
          <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground/60 transition-colors shrink-0" />
        </Link>
      )}

      <div className="p-4 space-y-4">
        {/* Sparkline */}
        {data.series_history && data.series_history.length > 1 && (
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
        )}

        {/* Current + Next */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-background p-3 space-y-1.5">
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.currentLevel")}</p>
            <p className={cn("font-mono text-sm font-bold", colorCls)}>{levelName}</p>
            <p className="font-mono text-[10px] text-muted-foreground">{data.current_avg?.toFixed(1)}%</p>
            {data.level_progress !== undefined && data.next_milestone && (
              <>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all duration-700", PROGRESS_COLOR[slug] ?? "bg-primary")}
                    style={{ width: `${Math.round(data.level_progress * 100)}%` }}
                  />
                </div>
                <p className="font-mono text-[9px] text-muted-foreground/70">
                  {Math.round(data.level_progress * 100)}% {t("career.progressToNext", {
                    next: t(`level.names.${data.next_milestone.level_slug}`, { defaultValue: data.next_milestone.level_name }),
                  })}
                </p>
              </>
            )}
            <p className="font-mono text-[9px] text-muted-foreground/50">{t("career.currentWindow")}</p>
          </div>
          {nm && nm.reachable ? (
            <div className="rounded-lg border border-border bg-background p-3 space-y-1">
              <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.nextLevel")}</p>
              <p className={cn("font-mono text-sm font-bold", MILESTONE_COLOR[nm.level_slug] ?? "text-primary")}>
                {t(`level.names.${nm.level_slug}`, { defaultValue: nm.level_name })}
              </p>
              <p className="font-mono text-[10px] text-muted-foreground">
                {nm.months_needed! > 0
                  ? t("career.monthsAway", { n: nm.months_needed })
                  : t("career.already")}
              </p>
              {nm.estimated_date && nm.months_needed! > 0 && (
                <p className="font-mono text-[9px] text-muted-foreground">
                  {t("career.estimatedDate", { date: formatDate(nm.estimated_date) })}
                </p>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-background p-3 space-y-1">
              <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("career.nextLevel")}</p>
              <p className="font-mono text-xs text-muted-foreground">{t("career.notReachable")}</p>
            </div>
          )}
        </div>

        {/* Milestones timeline */}
        {data.milestones && data.milestones.length > 0 && (
          <div className="space-y-1.5">
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground flex items-center gap-1">
              <TrendingUp className="size-3" /> {t("career.milestones")}
            </p>
            <div className="space-y-1">
              {data.milestones.slice(0, 4).map((m) => {
                const Icon = LEVEL_ICONS[m.level_name];
                const mColor = MILESTONE_COLOR[m.level_slug] ?? "text-muted-foreground";
                const mName = t(`level.names.${m.level_slug}`, { defaultValue: m.level_name });
                return (
                  <div key={m.level_slug} className="flex items-center justify-between text-[11px]">
                    <span className={cn("flex items-center gap-1.5 font-mono font-semibold", mColor)}>
                      {Icon && <Icon size={11} />}
                      {mName}
                      <span className="text-muted-foreground font-normal">({m.threshold}%)</span>
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {!m.reachable
                        ? t("career.notReachable").split(" — ")[0]
                        : m.months_needed === 0
                        ? t("career.already")
                        : t("career.monthsAway", { n: m.months_needed })}
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
                  <span className="text-foreground truncate">{lk.spot}</span>
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 ml-2">{lk.n}×</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* LLM Narrative */}
        {data.narrative && (
          <div className="border-t border-border pt-3">
            <AiText size="xs">{data.narrative}</AiText>
          </div>
        )}
      </div>
    </div>
  );
}
