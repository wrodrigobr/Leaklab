import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus, ChevronRight, Award } from "lucide-react";
import { metrics, EloResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";

/**
 * EloRatingCard — exibe ELO atual do jogador no Index dashboard.
 * Mostra: ELO overall + banda + delta 7d + link pra página /rating.
 */
export function EloRatingCard() {
  const [data, setData] = useState<EloResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    metrics.elo()
      .then((r) => { if (!cancelled) setData(r); })
      .catch((e) => { if (!cancelled) setError(String(e?.message ?? e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-2">
        <div className="h-3 w-24 bg-muted/40 rounded animate-pulse" />
        <div className="h-8 w-32 bg-muted/40 rounded animate-pulse" />
      </div>
    );
  }
  if (error || !data) return null;

  const { overall, delta_7d, total_decisions, no_data } = data;
  const TrendIcon = delta_7d == null
    ? Minus
    : delta_7d > 0 ? TrendingUp : delta_7d < 0 ? TrendingDown : Minus;
  const trendColor = delta_7d == null || delta_7d === 0
    ? "text-muted-foreground"
    : delta_7d > 0 ? "text-emerald-400" : "text-red-400";

  return (
    <Link
      to="/rating"
      className={cn(
        "block rounded-xl border border-border/40 bg-card/60 p-4 transition-colors",
        "hover:bg-card/80 hover:border-border/70 group"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 flex-1 min-w-0">
          <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            <Award className="size-3" />
            Rating ELO
          </div>
          <div className="flex items-center gap-2">
            {(() => { const I = LEVEL_ICONS[overall.band_label]; return I ? <I size={22} className="shrink-0" /> : null; })()}
            <span className="font-mono text-3xl font-bold tabular-nums leading-none"
                  style={{ color: overall.band_color }}>
              {overall.elo.toFixed(0)}
            </span>
            <span className="font-mono text-[11px] font-semibold"
                  style={{ color: overall.band_color }}>
              {overall.band_label}
            </span>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
            <span>{total_decisions.toLocaleString()} decisões</span>
            {!no_data && (
              <span className={cn("flex items-center gap-0.5", trendColor)}>
                <TrendIcon className="size-3" />
                {delta_7d == null ? "—" : `${delta_7d > 0 ? "+" : ""}${delta_7d.toFixed(1)} (7d)`}
              </span>
            )}
          </div>
          {/* Progresso até o próximo nível */}
          {data.next_band && (
            <div className="pt-1 space-y-0.5">
              <div className="h-1 rounded-full bg-muted/20 overflow-hidden">
                <div className="h-full rounded-full transition-all"
                     style={{ width: `${data.next_band.progress * 100}%`, background: overall.band_color }} />
              </div>
              <div className="font-mono text-[9px] text-muted-foreground">
                {data.next_band.elo_to_go.toFixed(0)} pra {data.next_band.label}
              </div>
            </div>
          )}
        </div>
        <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground/60 transition-colors" />
      </div>
    </Link>
  );
}
