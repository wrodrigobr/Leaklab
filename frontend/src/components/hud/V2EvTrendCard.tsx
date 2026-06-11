import { useTranslation } from "react-i18next";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { EvSummary } from "@/lib/api";

/**
 * V2EvTrendCard — UX-2 onda 1. Evolução do EV perdido/100 por torneio como
 * área com gradiente (linguagem Linear/Vercel): UMA história, sem ruído de
 * eixos pesados. Quanto MENOR a curva, melhor (perdendo menos).
 */
export function V2EvTrendCard({ evSummary }: { evSummary: EvSummary | null }) {
  const { t } = useTranslation("dashboard");
  const pts = (evSummary?.series ?? []).filter((p) => p.ev_per_100 != null);
  if (pts.length < 2) return null;

  const data = pts.map((p, i) => ({ i, name: p.name || `#${p.tournament_id}`, ev: p.ev_per_100 }));

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-baseline justify-between mb-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {t("v2.trendTitle")}
        </div>
        <div className="font-mono text-[9px] text-muted-foreground/70">{t("v2.trendHint")}</div>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
            <defs>
              <linearGradient id="evFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f87171" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#f87171" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1E2A45" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false} width={46}
                   tickFormatter={(v: number) => `−${v}bb`} />
            <Tooltip
              contentStyle={{ background: "#0F1526", border: "1px solid #1E2A45", borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#E3E8EC" }}
              formatter={(v: number) => [`−${v} bb/100`, t("v2.evLabel")]}
            />
            <Area type="monotone" dataKey="ev" stroke="#f87171" strokeWidth={2}
                  fill="url(#evFill)" dot={{ r: 2, fill: "#f87171" }} activeDot={{ r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
