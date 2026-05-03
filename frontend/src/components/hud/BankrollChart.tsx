import { useMemo } from "react";
import { useTranslation } from "react-i18next";

interface EvolutionPoint {
  profit: number | null;
  imported_at: string;
}

interface Props {
  evolution?: EvolutionPoint[];
}

const DEMO_POINTS = [120, 95, 140, 110, 180, 165, 220, 250, 240, 310, 330, 380, 420, 460, 510, 540, 600, 640, 690, 720, 760, 820, 880, 940];

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

export function BankrollChart({ evolution }: Props) {
  const { t } = useTranslation("dashboard");

  const { path, area, max, min, isDemo } = useMemo(() => {
    if (evolution && evolution.length >= 2) {
      let running = 0;
      const pts = evolution.map((e) => {
        running += e.profit ?? 0;
        return running;
      });
      return { ...buildPath(pts), isDemo: false };
    }
    return { ...buildPath(DEMO_POINTS), isDemo: true };
  }, [evolution]);

  const periods = [
    { key: "p1m", label: t("bankroll.p1m") },
    { key: "p3m", label: t("bankroll.p3m") },
    { key: "p1y", label: t("bankroll.p1y") },
    { key: "pAll", label: t("bankroll.pAll") },
  ];

  return (
    <section
      aria-labelledby="bankroll-heading"
      className="rounded-xl border border-border bg-hud-surface overflow-hidden"
    >
      <header className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h2 id="bankroll-heading" className="text-sm font-semibold text-foreground">
            {t("bankroll.title")}
          </h2>
          <p className="font-mono text-[11px] text-muted-foreground">
            {isDemo ? t("bankroll.demo") : t("bankroll.lastN", { n: evolution!.length })}
          </p>
        </div>
        <div className="flex gap-1">
          {periods.map(({ key, label }, i) => (
            <button
              key={key}
              className={`rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                i === 1
                  ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      <div className="relative px-5 pb-5 pt-6">
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
      </div>
    </section>
  );
}
