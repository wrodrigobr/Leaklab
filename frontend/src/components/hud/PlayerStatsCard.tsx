import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

interface PlayerStats {
  total_hands: number;
  vpip: number | null;
  pfr: number | null;
  af: number | null;
  flop_bet_pct: number | null;
  three_bet: null;
  fold_to_3bet: null;
  wtsd: null;
  w_at_sd: null;
}

interface Props {
  stats?: PlayerStats | null;
}

interface StatDef {
  key: keyof PlayerStats;
  label: string;
  unit: "%" | "x";
  range: { min: number; max: number; label: string };
  tooltip: string;
}

const STAT_DEFS: StatDef[] = [
  {
    key: "vpip",
    label: "VPIP",
    unit: "%",
    range: { min: 12, max: 22, label: "12–22%" },
    tooltip:
      "Voluntarily Put money In Pot — % de mãos em que o jogador entrou voluntariamente (call/raise pré-flop). MTT ideal: 12–22%. Abaixo de 12% = muito tight; acima de 25% = muito loose.",
  },
  {
    key: "pfr",
    label: "PFR",
    unit: "%",
    range: { min: 9, max: 18, label: "9–18%" },
    tooltip:
      "PreFlop Raise — % de mãos em que o jogador abriu ou re-raised pré-flop. MTT ideal: 9–18%. PFR próximo ao VPIP indica jogo agressivo; diferença grande indica passividade.",
  },
  {
    key: "af",
    label: "AF",
    unit: "x",
    range: { min: 2.0, max: 4.0, label: "2.0–4.0x" },
    tooltip:
      "Aggression Factor — razão entre ações agressivas (bet/raise) e passivas (call) no pós-flop. MTT ideal: 2.0–4.0x. Abaixo de 1.5 = passivo demais; acima de 6 = overaggressive.",
  },
  {
    key: "flop_bet_pct",
    label: "Flop Bet",
    unit: "%",
    range: { min: 40, max: 65, label: "40–65%" },
    tooltip:
      "Frequência de aposta no flop (bet/raise/jam como % das decisões no flop). Inclui c-bets e raises. MTT ideal: 40–65% dependendo da posição e range.",
  },
];

type Status = "ok" | "warn" | "danger" | "na";

function getStatus(value: number | null, range: StatDef["range"]): Status {
  if (value === null) return "na";
  const { min, max } = range;
  if (value >= min && value <= max) return "ok";
  const margin = (max - min) * 0.35;
  if (value >= min - margin && value <= max + margin) return "warn";
  return "danger";
}

const STATUS_COLORS: Record<Status, string> = {
  ok:     "text-primary",
  warn:   "text-yellow-400",
  danger: "text-destructive",
  na:     "text-muted-foreground/40",
};

const BAR_COLORS: Record<Status, string> = {
  ok:     "bg-primary",
  warn:   "bg-yellow-400",
  danger: "bg-destructive",
  na:     "bg-border",
};

function StatCell({ def, value }: { def: StatDef; value: number | null }) {
  const status = getStatus(value, def.range);
  const { min, max } = def.range;
  const margin = (max - min) * 0.35;
  const lo = min - margin;
  const hi = max + margin;

  const fill =
    value !== null
      ? Math.max(0, Math.min(100, ((value - lo) / (hi - lo)) * 100))
      : 0;
  const minPct = ((min - lo) / (hi - lo)) * 100;
  const maxPct = ((max - lo) / (hi - lo)) * 100;

  const displayValue =
    value !== null
      ? def.unit === "x"
        ? `${value.toFixed(1)}x`
        : `${value.toFixed(1)}%`
      : "—";

  return (
    <div className="flex flex-col gap-2 px-6 py-4 border-r border-border last:border-0">
      {/* Label row */}
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {def.label}
        </span>
        <HudTooltip content={def.tooltip} />
      </div>

      {/* Value */}
      <span className={cn("font-mono text-2xl font-bold tabular-nums leading-none", STATUS_COLORS[status])}>
        {displayValue}
      </span>

      {/* Bar */}
      <div className="relative h-1 w-full rounded-full bg-border/60 overflow-hidden">
        <span
          className="absolute top-0 h-full rounded-full bg-primary/15"
          style={{ left: `${minPct}%`, width: `${maxPct - minPct}%` }}
        />
        {value !== null && (
          <span
            className={cn("absolute top-0 left-0 h-full rounded-full transition-all", BAR_COLORS[status])}
            style={{ width: `${fill}%` }}
          />
        )}
      </div>

      {/* Range label */}
      <span className="font-mono text-[9px] text-muted-foreground/60 uppercase tracking-widest">
        Ref MTT {def.range.label}
      </span>
    </div>
  );
}

export function PlayerStatsCard({ stats }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface shadow-elevated">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Player HUD Stats
          </span>
          <HudTooltip content="Indicadores táticos do seu perfil de jogo calculados a partir das decisões registradas. Comparados com referências de jogadores regulares em MTTs." />
        </div>
        <span className="font-mono text-[10px] text-primary">
          {stats && stats.total_hands > 0 ? `${stats.total_hands} mãos analisadas` : "sem dados"}
        </span>
      </div>

      {/* Cells */}
      {!stats || stats.total_hands === 0 ? (
        <p className="px-6 py-5 text-xs text-muted-foreground text-center">
          Importe torneios para calcular seu perfil de jogo.
        </p>
      ) : (
        <div className="grid grid-cols-2 divide-x divide-border md:grid-cols-4">
          {STAT_DEFS.map((def) => (
            <StatCell
              key={String(def.key)}
              def={def}
              value={stats[def.key] as number | null}
            />
          ))}
        </div>
      )}
    </div>
  );
}
