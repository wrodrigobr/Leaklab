import { useTranslation } from "react-i18next";
import {
  RadarChart, Radar, PolarAngleAxis, PolarGrid,
  ResponsiveContainer, Tooltip,
} from "recharts";
import { HudTooltip } from "./HudTooltip";
import type { PlayerDnaResponse } from "@/lib/api";

interface Props {
  data: PlayerDnaResponse | null;
}

const ARCHETYPE_COLORS: Record<string, string> = {
  TAG:               "text-primary border-primary/30 bg-primary/10",
  LAG:               "text-orange-400 border-orange-400/30 bg-orange-400/10",
  Nit:               "text-blue-400 border-blue-400/30 bg-blue-400/10",
  "Calling Station": "text-red-400 border-red-400/30 bg-red-400/10",
  Balanced:          "text-violet-400 border-violet-400/30 bg-violet-400/10",
};

const ARCHETYPE_DOT: Record<string, string> = {
  TAG:               "bg-primary",
  LAG:               "bg-orange-400",
  Nit:               "bg-blue-400",
  "Calling Station": "bg-red-400",
  Balanced:          "bg-violet-400",
};

export function PlayerDnaCard({ data }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data?.dna) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
        <div className="mb-3 flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("dna.title")}
          </span>
          <HudTooltip content={t("dna.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground">{t("dna.noData")}</p>
      </div>
    );
  }

  const { dna, sample_size } = data;
  const archetype = dna.archetype;

  const chartData = [
    { metric: t("dna.axes.aggression"), value: Math.round(dna.aggression_index) },
    { metric: t("dna.axes.foldFreq"),   value: Math.round(dna.fold_frequency) },
    { metric: t("dna.axes.threeBet"),   value: Math.min(100, Math.round(dna.three_bet_pct * 6)) },
    { metric: t("dna.axes.positional"), value: Math.round(dna.positional_awareness) },
    { metric: t("dna.axes.discipline"), value: Math.round(dna.discipline) },
  ];

  const stats = [
    { label: t("dna.axes.aggression"), value: `${dna.aggression_index.toFixed(1)}%` },
    { label: t("dna.axes.foldFreq"),   value: `${dna.fold_frequency.toFixed(1)}%` },
    { label: t("dna.axes.threeBet"),   value: `${dna.three_bet_pct.toFixed(1)}%` },
    { label: t("dna.axes.positional"), value: `${dna.positional_awareness.toFixed(0)}` },
    { label: t("dna.axes.discipline"), value: `${dna.discipline.toFixed(1)}%` },
    ...(dna.icm_awareness != null
      ? [{ label: t("dna.axes.icm"), value: `${dna.icm_awareness.toFixed(0)}` }]
      : []),
  ];

  const dotColor  = ARCHETYPE_DOT[archetype]  ?? "bg-primary";
  const badgeColor = ARCHETYPE_COLORS[archetype] ?? ARCHETYPE_COLORS.TAG;

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("dna.title")}
          </span>
          <HudTooltip content={t("dna.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("dna.sampleSize", { n: sample_size.toLocaleString() })}
        </span>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        {/* Radar chart */}
        <div className="h-[200px] w-full sm:w-[200px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={chartData} outerRadius="65%" margin={{ top: 15, right: 35, bottom: 20, left: 35 }}>
              <PolarGrid stroke="hsl(var(--border))" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 9, fontFamily: "monospace" }}
              />
              <Radar
                dataKey="value"
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary))"
                fillOpacity={0.15}
                strokeWidth={1.5}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--background))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "11px",
                  fontFamily: "monospace",
                }}
                formatter={(v: number) => [`${v}`, ""]}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Archetype + stats */}
        <div className="flex-1 space-y-3">
          <div>
            <p className="mb-1 font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
              {t("dna.archetype")}
            </p>
            <div className="flex items-center gap-2">
              <span className={`size-1.5 rounded-full ${dotColor}`} />
              <span className={`rounded-full border px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wide ${badgeColor}`}>
                {t(`dna.archetypes.${archetype}`, { defaultValue: archetype })}
              </span>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground line-clamp-2">
              {t(`dna.archetypeDesc.${archetype}`, { defaultValue: "" })}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-border/50 pt-3">
            {stats.map(({ label, value }) => (
              <div key={label} className="flex justify-between gap-2">
                <span className="font-mono text-[9px] uppercase text-muted-foreground">
                  {label}
                </span>
                <span className="font-mono text-[11px] font-semibold text-foreground">
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
