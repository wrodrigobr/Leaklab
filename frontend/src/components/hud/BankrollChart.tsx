import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { metrics } from "@/lib/api";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

const DEMO_POINTS = [120, 95, 140, 110, 180, 165, 220, 250, 240, 310, 330, 380, 420, 460, 510, 540, 600, 640, 690, 720, 760, 820, 880, 940];

const PERIODS = [
  { key: "1W" as const, days: 7   },
  { key: "1M" as const, days: 30  },
  { key: "6M" as const, days: 180 },
  { key: "1Y" as const, days: 365 },
  { key: "ALL" as const, days: 3650 },
] as const;

type PeriodKey = typeof PERIODS[number]["key"];

/** Rótulo de data do eixo X: dia/mês em janelas curtas, mês/ano em janelas longas. */
function fmtAxisDate(s: string | null, days: number, locale: string): string {
  if (!s) return "";
  try {
    const d = new Date(s);
    return days <= 31
      ? d.toLocaleDateString(locale, { day: "2-digit", month: "short" })
      : d.toLocaleDateString(locale, { month: "short", year: "2-digit" });
  } catch {
    return "";
  }
}

function buildPath(points: number[]) {
  const w = 100;
  const h = 100;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const stepX = w / (points.length - 1);
  const pts = points.map((p, i) => {
    const x = i * stepX;
    const y = h - ((p - min) / range) * h * 0.85 - 5;
    return [x, y] as const;
  });
  const path = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
  const area = `${path} L ${w} ${h} L 0 ${h} Z`;
  return { path, area, max, min };
}

export function BankrollChart() {
  const { t, i18n } = useTranslation("dashboard");
  const [period, setPeriod] = useState<PeriodKey>("6M");

  const days = PERIODS.find((p) => p.key === period)!.days;

  const { data, isFetching } = useQuery({
    queryKey: ["bankroll-evolution", days],
    queryFn: () => metrics.evolution(days),
    staleTime: 30_000,
  });

  const evolution = data?.evolution;

  const { path, area, max, min, isDemo, ticks } = useMemo(() => {
    const w = 100, h = 100;
    if (evolution && evolution.length >= 2) {
      // Linha PROPORCIONAL AO TEMPO (x = data de jogo), não por índice — assim o eixo X reflete
      // a evolução real ao longo dos dias/meses, com resolução adaptada ao filtro.
      let running = 0;
      const raw = evolution
        .map((e) => ({ t: e.played_at ? new Date(e.played_at).getTime() : NaN, v: (running += e.profit ?? 0) }))
        .filter((p) => !Number.isNaN(p.t));
      if (raw.length >= 2) {
        const t0 = raw[0].t, t1 = raw[raw.length - 1].t, span = (t1 - t0) || 1;
        const vs = raw.map((p) => p.v);
        const max = Math.max(...vs), min = Math.min(...vs), range = (max - min) || 1;
        const pts = raw.map((p) => {
          const x = ((p.t - t0) / span) * w;
          const y = h - ((p.v - min) / range) * h * 0.85 - 5;
          return [x, y] as const;
        });
        const path = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
        const area = `${path} L ${w} ${h} L 0 ${h} Z`;
        // Ticks adaptativos: ~1 por dia em 7d; ~6 marcos nos demais (formato dia/mês ou mês/ano).
        const spanDays = span / 86_400_000;
        const n = days <= 7 ? Math.max(2, Math.min(7, Math.round(spanDays) + 1)) : 6;
        const ticks = Array.from({ length: n }, (_, i) =>
          fmtAxisDate(new Date(t0 + (span * i) / (n - 1)).toISOString(), days, i18n.language));
        return { path, area, max, min, isDemo: false, ticks };
      }
    }
    return { ...buildPath(DEMO_POINTS), isDemo: true, ticks: [] as string[] };
  }, [evolution, days, i18n.language]);

  const periodLabels: Record<PeriodKey, string> = {
    "1W": t("bankroll.p1w"),
    "1M": t("bankroll.p1m"),
    "6M": t("bankroll.p6m"),
    "1Y": t("bankroll.p1y"),
    "ALL": t("bankroll.pAll"),
  };

  return (
    <section
      aria-labelledby="bankroll-heading"
      className="rounded-xl border border-border bg-hud-surface overflow-hidden"
    >
      <header className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h2 id="bankroll-heading" className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            {t("bankroll.title")}
            <HudTooltip content={t("bankroll.tooltip")} />
          </h2>
          <p className="font-mono text-[11px] text-muted-foreground">
            {isDemo
              ? t("bankroll.demo")
              : t("bankroll.lastN", { n: evolution!.length })}
          </p>
        </div>
        <div className="flex gap-1">
          {PERIODS.map(({ key }) => (
            <button
              key={key}
              onClick={() => setPeriod(key)}
              className={cn(
                "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                period === key
                  ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              {periodLabels[key]}
            </button>
          ))}
        </div>
      </header>

      <div className="relative px-5 pb-5 pt-6">
        {isFetching && (
          <div className="absolute inset-0 flex items-center justify-center bg-hud-surface/60 z-10">
            <Loader2 className="size-4 animate-spin text-primary" />
          </div>
        )}

        <div className="absolute left-5 top-6 font-mono text-[10px] text-muted-foreground">
          {max >= 0 ? "+" : ""}${Math.round(max).toLocaleString()}
        </div>
        <div className="absolute bottom-5 left-5 font-mono text-[10px] text-muted-foreground">
          {min >= 0 ? "+" : ""}${Math.round(min).toLocaleString()}
        </div>

        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="h-56 w-full"
          role="img"
          aria-label={t("bankroll.ariaLabel")}
        >
          <defs>
            <linearGradient id="bankrollFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.4" />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
            </linearGradient>
            <pattern id="hudGrid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="hsl(var(--border))" strokeWidth="0.2" />
            </pattern>
          </defs>
          <rect width="100" height="100" fill="url(#hudGrid)" />
          <path d={area} fill="url(#bankrollFill)" />
          <path
            d={path}
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="0.6"
            vectorEffect="non-scaling-stroke"
          />
        </svg>

        {/* Eixo X: marcos de data adaptados ao filtro (diário em 7d, mês/ano em janelas longas).
            Ticks igualmente espaçados no TEMPO = igualmente espaçados no X (linha é tempo-proporcional). */}
        {!isDemo && ticks.length >= 2 && (
          <div className="mt-2 flex justify-between px-1 font-mono text-[9px] text-muted-foreground/70">
            {ticks.map((label, i) => (
              <span key={i}>{label}</span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
