import { useTranslation } from "react-i18next";
import { Clock, Layers, Sunrise, BatteryLow } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import type { SessionContextData, SessionContextBucket } from "@/lib/api";

type GroupKey = "multitabling" | "time_of_day" | "fatigue";

const GROUP_ICON: Record<GroupKey, typeof Clock> = {
  multitabling: Layers,
  time_of_day: Sunrise,
  fatigue: BatteryLow,
};

// menor avg_score = melhor decisão. Destaca melhor (teal) e pior (vermelho) balde do grupo.
function pickExtremes(buckets: SessionContextBucket[]) {
  let best = buckets[0];
  let worst = buckets[0];
  for (const b of buckets) {
    if (b.avg_score < best.avg_score) best = b;
    if (b.avg_score > worst.avg_score) worst = b;
  }
  return { best, worst };
}

function Group({ group, buckets }: { group: GroupKey; buckets: SessionContextBucket[] }) {
  const { t } = useTranslation("dashboard");
  if (buckets.length < 2) return null;

  const { best, worst } = pickExtremes(buckets);
  const maxScore = Math.max(...buckets.map((b) => b.avg_score)) || 1;
  const Icon = GROUP_ICON[group];

  const bucketLabel = (b: string) => {
    if (group === "multitabling")
      return b === "1" ? t("sessionContext.units.tableOne") : `${b} ${t("sessionContext.units.tables")}`;
    if (group === "time_of_day") return t(`sessionContext.tod.${b}`);
    return b; // fadiga já é legível ("0-1h" etc.)
  };

  // insight só quando o pior é notavelmente pior que o melhor (>= 20%)
  const gapPct = best.avg_score > 0 ? Math.round((worst.avg_score / best.avg_score - 1) * 100) : 0;
  const showInsight = worst.bucket !== best.bucket && gapPct >= 20;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        <Icon className="size-3.5 text-primary/80" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {t(`sessionContext.groups.${group}`)}
        </span>
      </div>

      <div className="space-y-1.5">
        {buckets.map((b) => {
          const isBest = b.bucket === best.bucket && showInsight;
          const isWorst = b.bucket === worst.bucket && showInsight;
          const barColor = isBest ? "bg-primary" : isWorst ? "bg-destructive" : "bg-muted-foreground/40";
          const width = Math.max(6, Math.round((b.avg_score / maxScore) * 100));
          return (
            <div key={b.bucket} className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-[11px] text-foreground truncate">
                {bucketLabel(b.bucket)}
              </span>
              <div className="h-1.5 flex-1 rounded-full bg-border overflow-hidden">
                <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${width}%` }} />
              </div>
              <span className="w-9 shrink-0 text-right font-mono text-[10px] text-muted-foreground">
                {t("sessionContext.tournamentsShort", { count: b.tournaments })}
              </span>
            </div>
          );
        })}
      </div>

      {showInsight && (
        <p className="text-[11px] leading-snug text-muted-foreground">
          {t("sessionContext.insight", {
            best: bucketLabel(best.bucket),
            worst: bucketLabel(worst.bucket),
            pct: gapPct,
          })}
        </p>
      )}
    </div>
  );
}

export function SessionContextCard({ data }: { data: SessionContextData }) {
  const { t } = useTranslation("dashboard");

  const groups: GroupKey[] = ["multitabling", "time_of_day", "fatigue"];
  const hasAny = !data.insufficient_data && groups.some((g) => (data[g]?.length ?? 0) >= 2);

  if (!hasAny) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
        <div className="flex items-center gap-1.5 mb-3">
          <Clock className="size-4 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("sessionContext.title")}
          </span>
          <HudTooltip content={t("sessionContext.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {t("sessionContext.noData")}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-hud-surface hud-glare overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-1.5">
          <Clock className="size-4 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("sessionContext.title")}
          </span>
          <HudTooltip content={t("sessionContext.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("sessionContext.decisions", { count: data.sample })}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {groups.map((g) =>
          (data[g]?.length ?? 0) >= 2 ? <Group key={g} group={g} buckets={data[g]} /> : null
        )}
        <p className="border-t border-border/50 pt-2 text-[10px] text-muted-foreground/70">
          {t("sessionContext.footnote")}
        </p>
      </div>
    </div>
  );
}
