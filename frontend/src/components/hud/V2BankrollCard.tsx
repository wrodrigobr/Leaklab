import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { metrics } from "@/lib/api";

/**
 * V2BankrollCard — lucro acumulado num AreaChart recharts, com eixo X TEMPORAL (data de jogo) e
 * resolução adaptada ao filtro: ~diário em 7d, mês/ano em janelas longas. Sem modo demo: sem dados, some.
 */
const PERIODS = [
  { key: "1W"  as const, days: 7,    label: "7d" },
  { key: "1M"  as const, days: 30,   label: "30d" },
  { key: "6M"  as const, days: 180,  label: "6M" },
  { key: "1Y"  as const, days: 365,  label: "1A" },
  { key: "ALL" as const, days: 3650, label: "Tudo" },
] as const;
type PeriodKey = (typeof PERIODS)[number]["key"];

function fmtDate(t: number, days: number, locale: string): string {
  try {
    const d = new Date(t);
    return days <= 31
      ? d.toLocaleDateString(locale, { day: "2-digit", month: "short" })
      : d.toLocaleDateString(locale, { month: "short", year: "2-digit" });
  } catch {
    return "";
  }
}

export function V2BankrollCard() {
  const { t, i18n } = useTranslation("dashboard");
  const [period, setPeriod] = useState<PeriodKey>("6M");
  const [mode, setMode] = useState<"time" | "tournament">("time");  // eixo X por tempo ou por torneio
  const days = PERIODS.find((p) => p.key === period)!.days;

  const { data } = useQuery({
    queryKey: ["bankroll-evolution", days],
    queryFn: () => metrics.evolution(days),
    staleTime: 30_000,
  });

  const { pts, ticks } = useMemo(() => {
    const evolution = data?.evolution ?? [];
    let running = 0;
    // x = data de JOGO (played_at) no modo tempo, ou índice do torneio no modo torneio. Pontos sem
    // data ficam de fora do plot, mas seu lucro entra no acumulado.
    const pts = evolution
      .map((e) => ({ t: e.played_at ? new Date(e.played_at).getTime() : NaN, profit: Math.round((running += e.profit ?? 0) * 100) / 100 }))
      .filter((p) => !Number.isNaN(p.t))
      .map((p, idx) => ({ ...p, i: idx, name: `#${idx + 1}` }));
    let ticks: number[] = [];
    if (pts.length >= 2) {
      const t0 = pts[0].t, t1 = pts[pts.length - 1].t, span = (t1 - t0) || 1;
      const spanDays = span / 86_400_000;
      const n = days <= 7 ? Math.max(2, Math.min(7, Math.round(spanDays) + 1)) : 6;
      ticks = Array.from({ length: n }, (_, i) => Math.round(t0 + (span * i) / (n - 1)));
    }
    return { pts, ticks };
  }, [data, days]);

  // Só some de vez quando NÃO há histórico nenhum (período "ALL" com <2 torneios).
  if (pts.length < 2 && period === "ALL") return null;

  const hasData = pts.length >= 2;
  const last = hasData ? pts[pts.length - 1].profit : 0;
  const up = last >= 0;
  const stroke = up ? "#2DD4BF" : "#f87171";

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-baseline justify-between mb-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {t("bankroll.title")}
          </span>
          {hasData && (
            <span className={`font-mono text-sm font-bold tabular-nums ${up ? "text-teal-300" : "text-red-400"}`}>
              {up ? "+" : "−"}${Math.abs(last).toFixed(2)}
            </span>
          )}
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
              {p.label}
            </button>
          ))}
        </div>
      </div>
      {hasData && (
        <div className="mb-1.5 flex gap-1">
          {(["time", "tournament"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide transition-colors ${
                mode === m ? "bg-secondary text-foreground" : "text-muted-foreground/50 hover:text-muted-foreground"
              }`}
            >
              {m === "time" ? t("bankroll.byTime") : t("bankroll.byTournament")}
            </button>
          ))}
        </div>
      )}
      <div className="h-44">
        {!hasData ? (
          <div className="flex h-full items-center justify-center">
            <p className="max-w-[220px] text-center text-[11px] text-muted-foreground/70">
              {t("bankroll.emptyPeriod")}
            </p>
          </div>
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={pts} margin={{ top: 6, right: 6, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id="bankFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.3} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1E2A45" strokeDasharray="3 6" vertical={false} />
            {mode === "time" ? (
              <XAxis
                dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
                ticks={ticks} tickFormatter={(v: number) => fmtDate(v, days, i18n.language)}
                tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false}
              />
            ) : (
              <XAxis
                dataKey="i" type="number" domain={["dataMin", "dataMax"]}
                tickFormatter={(v: number) => `#${v + 1}`} interval="preserveStartEnd"
                tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false}
              />
            )}
            <YAxis tick={{ fontSize: 9, fill: "#8B96A8" }} tickLine={false} axisLine={false} width={52}
                   tickFormatter={(v: number) => `$${v}`} />
            <Tooltip
              contentStyle={{ background: "#0F1526", border: "1px solid #1E2A45", borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#E3E8EC" }}
              labelFormatter={(v: number) => mode === "time" ? fmtDate(v, days, i18n.language) : `#${v + 1}`}
              formatter={(v: number) => [`$${v.toFixed(2)}`, t("v2.bankSeries")]}
            />
            <Area type="monotone" dataKey="profit" stroke={stroke} strokeWidth={2}
                  fill="url(#bankFill)" dot={{ r: 2, fill: stroke }} activeDot={{ r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
