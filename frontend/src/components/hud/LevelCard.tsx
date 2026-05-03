import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { TrendingUp, ChevronRight, AlertCircle } from "lucide-react";
import { PlayerLevel } from "@/lib/api";
import { cn } from "@/lib/utils";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";

const LEVEL_COLOR: Record<string, string> = {
  "Iniciante": "text-muted-foreground border-muted-foreground/30 bg-muted-foreground/5",
  "Estudante": "text-blue-400 border-blue-400/30 bg-blue-400/5",
  "Grinder":   "text-amber-400 border-amber-400/30 bg-amber-400/5",
  "Regular":   "text-emerald-400 border-emerald-400/30 bg-emerald-400/5",
  "Sólido":    "text-primary border-primary/30 bg-primary/5",
  "Expert":    "text-violet-400 border-violet-400/30 bg-violet-400/5",
  "Elite":     "text-amber-300 border-amber-300/30 bg-amber-300/5",
};

const PROGRESS_COLOR: Record<string, string> = {
  "Iniciante": "bg-muted-foreground",
  "Estudante": "bg-blue-400",
  "Grinder":   "bg-amber-400",
  "Regular":   "bg-emerald-400",
  "Sólido":    "bg-primary",
  "Expert":    "bg-violet-400",
  "Elite":     "bg-amber-300",
};

interface Props {
  data: PlayerLevel;
  showStudyLink?: boolean;
  compact?: boolean;
}

export function LevelCard({ data, showStudyLink = true, compact = false }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data.level) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-2">
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
          <TrendingUp className="size-3" /> {t("level.title")}
        </p>
        <p className="text-xs text-muted-foreground">
          {t("level.noData")}
        </p>
      </div>
    );
  }

  const colorCls    = LEVEL_COLOR[data.level] ?? "text-primary border-primary/30 bg-primary/5";
  const progressCls = PROGRESS_COLOR[data.level] ?? "bg-primary";
  const pct         = Math.round(data.progress * 100);

  return (
    <div className={cn("rounded-xl border bg-hud-surface", compact ? "p-4" : "p-5", "space-y-4")}>
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
          <TrendingUp className="size-3" /> {t("level.title")}
        </p>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("level.tournament", { count: data.tournament_count })}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className={cn("rounded-xl border px-3 py-2.5 text-center min-w-[72px] flex flex-col items-center gap-1", colorCls)}>
          {(() => { const Icon = LEVEL_ICONS[data.level]; return Icon ? <Icon size={22} /> : null; })()}
          <p className={cn("font-mono text-[10px] font-bold uppercase tracking-wider", colorCls.split(" ")[0])}>
            {data.level}
          </p>
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs font-bold text-foreground">{data.standard_pct.toFixed(1)}%</span>
            {data.next_level && (
              <span className="font-mono text-[10px] text-muted-foreground flex items-center gap-1">
                {(() => { const Icon = LEVEL_ICONS[data.next_level]; return Icon ? <Icon size={11} /> : null; })()}
                {t("level.nextAt", { next: data.next_level, pct: data.next_pct })}
              </span>
            )}
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all duration-700", progressCls)}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="font-mono text-[10px] text-muted-foreground">
            {data.next_level
              ? t("level.progress", { pct, next: data.next_level })
              : t("level.maxLevel")}
          </p>
        </div>
      </div>

      {!compact && data.top_blocking_leaks.length > 0 && (
        <div className="space-y-1.5">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1">
            <AlertCircle className="size-3" /> {t("level.blockingLeaks")}
          </p>
          <ul className="space-y-1">
            {data.top_blocking_leaks.map((lk) => (
              <li key={lk.spot} className="flex items-center justify-between text-xs">
                <span className="text-foreground truncate">{lk.spot}</span>
                <span className="font-mono text-[10px] text-muted-foreground shrink-0 ml-2">{lk.n}x</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showStudyLink && data.next_level && (
        <Link
          to="/study"
          className="flex items-center justify-between w-full rounded-md border border-border bg-background px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
        >
          <span>{t("level.studyLink")}</span>
          <ChevronRight className="size-3.5 shrink-0" />
        </Link>
      )}
    </div>
  );
}
