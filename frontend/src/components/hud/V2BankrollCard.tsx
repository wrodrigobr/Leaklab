import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { metrics } from "@/lib/api";

/**
 * V2BankrollCard — UX-2 onda 3. Versão V2 do BankrollChart: lucro acumulado em
 * AreaChart recharts com gradiente teal — espelho financeiro do V2EvTrendCard
 * (vermelho = EV perdido; teal = resultado). Sem modo demo: sem dados, some
 * (masonry fecha o vão). Clássico segue com o card antigo.
 */
const PERIODS = [
  { key: "1M",  days: 30 },
  { key: "3M",  days: 90 },
  { key: "1Y",  days: 365 },
  { key: "ALL", days: 3650 },
] as const;
type PeriodKey = (typeof PERIODS)[number]["key"];

export function V2BankrollCard() {
  const { t } = useTranslation("dashboard");
  const [period, setPeriod] = useState<PeriodKey>("3M");
  const days = PERIODS.find((p) => p.key === period)!.days;

  const { data } = useQuery({
    queryKey: ["bankroll-evolution", days],
    queryFn: () => metrics.evolution(days),
    staleTime: 30_000,
  });

  const pts = useMemo(() => {
    const evolution = data?.evolution ?? [];
    let running = 0;
    return evolution.map((e, i) => {
      running += e.profit ?? 0;
      return { i, name: `#${i + 1}`, profit: Math.round(running * 100) / 100 };
    });
  }, [data]);

  if (pts.length < 2) return null;

  const last = pts[pts.length - 1].profit;
  const up = last >= 0;
  const stroke = up ? "#2DD4BF" : "#f87171";

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-baseline justify-between mb-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {t("bankroll.title")}
          </span>
          <span className={`font-mono text-sm font-bold tabular-nums ${up ? "text-teal-300" : "text-red-400"}`}>
            {up ? "+" : "−"}${Math.abs(last).toFixed(2)}
          </span>
        </div>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`rounded px-1.5 py-0.5 font-mono text-[9px] uppercase transition-colors ${
                period === p.key
                  ? "bg-teal-400/15 text-teal-300 ring-1 ring-teal-400/30"
                  : "text-muted-foreground/60 hover:text-foreground"
              }`}
            >
              {p.key === "ALL" ? t("bankroll.pAll") : p.key}
            </button>
          ))}
        </div>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={pts} margin={{ top: 6, right: 6, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id="bankFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.3} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1E2A45" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false} width={52}
                   tickFormatter={(v: number) => `$${v}`} />
            <Tooltip
              contentStyle={{ background: "#0F1526", border: "1px solid #1E2A45", borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#E3E8EC" }}
              formatter={(v: number) => [`$${v.toFixed(2)}`, t("v2.bankSeries")]}
            />
            <Area type="monotone" dataKey="profit" stroke={stroke} strokeWidth={2}
                  fill="url(#bankFill)" dot={{ r: 2, fill: stroke }} activeDot={{ r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
