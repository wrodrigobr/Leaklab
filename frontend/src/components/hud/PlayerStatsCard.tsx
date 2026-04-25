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
  soon?: true;
}

const ROW1: StatDef[] = [
  {
    key: "vpip",
    label: "VPIP",
    unit: "%",
    range: { min: 12, max: 22, label: "12–22%" },
    tooltip: "Voluntarily Put money In Pot — % de mãos em que o jogador entrou voluntariamente (call/raise pré-flop). MTT ideal: 12–22%. Abaixo de 12% = muito tight; acima de 25% = muito loose.",
  },
  {
    key: "pfr",
    label: "PFR",
    unit: "%",
    range: { min: 9, max: 18, label: "9–18%" },
    tooltip: "PreFlop Raise — % de mãos em que o jogador abriu ou re-raised pré-flop. MTT ideal: 9–18%. PFR próximo ao VPIP indica jogo agressivo; diferença grande indica passividade.",
  },
  {
    key: "af",
    label: "AF",
    unit: "x",
    range: { min: 2.0, max: 4.0, label: "2.0–4.0x" },
    tooltip: "Aggression Factor — razão entre ações agressivas (bet/raise) e passivas (call) no pós-flop. MTT ideal: 2.0–4.0x. Abaixo de 1.5 = passivo demais; acima de 6 = overaggressive.",
  },
  {
    key: "flop_bet_pct",
    label: "Flop Bet",
    unit: "%",
    range: { min: 40, max: 65, label: "40–65%" },
    tooltip: "Frequência de aposta no flop (bet/raise/jam como % das decisões no flop). Inclui c-bets e raises. MTT ideal: 40–65% dependendo da posição e range.",
  },
];

const ROW2: StatDef[] = [
  {
    key: "three_bet",
    label: "3BET",
    unit: "%",
    range: { min: 4, max: 8, label: "4–8%" },
    tooltip: "% de mãos em que o jogador fez 3-bet pré-flop. MTT ideal: 4–8%. Requer rastreamento da sequência de apostas dentro da mão — disponível em versão futura.",
    soon: true,
  },
  {
    key: "fold_to_3bet",
    label: "Fold to 3BET",
    unit: "%",
    range: { min: 55, max: 72, label: "55–72%" },
    tooltip: "% de vezes que deu fold após levar um 3-bet. MTT ideal: 55–72%. Requer rastreamento da sequência de apostas — disponível em versão futura.",
    soon: true,
  },
  {
    key: "wtsd",
    label: "WTSD",
    unit: "%",
    range: { min: 25, max: 35, label: "25–35%" },
    tooltip: "Went To ShowDown — % das mãos que viram o flop e chegaram ao showdown. MTT ideal: 25–35%. Requer rastreamento de showdowns — disponível em versão futura.",
    soon: true,
  },
  {
    key: "w_at_sd",
    label: "W$SD",
    unit: "%",
    range: { min: 50, max: 60, label: "50–60%" },
    tooltip: "Won money at ShowDown — % de showdowns vencidos. Meta: > 50% para ser +EV nos confrontos. Requer rastreamento de showdowns — disponível em versão futura.",
    soon: true,
  },
];

type Status = "ok" | "warn" | "danger" | "na";

function getStatus(value: number | null, range: StatDef["range"], soon?: true): Status {
  if (soon || value === null) return "na";
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
  na:     "text-muted-foreground/25",
};

const BAR_COLORS: Record<Status, string> = {
  ok:     "bg-primary",
  warn:   "bg-yellow-400",
  danger: "bg-destructive",
  na:     "bg-transparent",
};

function StatCell({ def, value, compact }: { def: StatDef; value: number | null; compact?: boolean }) {
  const status = getStatus(value, def.range, def.soon);
  const { min, max } = def.range;
  const margin = (max - min) * 0.35;
  const lo = min - margin;
  const hi = max + margin;

  const fill = value !== null && !def.soon
    ? Math.max(0, Math.min(100, ((value - lo) / (hi - lo)) * 100))
    : 0;
  const minPct = ((min - lo) / (hi - lo)) * 100;
  const maxPct = ((max - lo) / (hi - lo)) * 100;

  const displayValue = value !== null && !def.soon
    ? def.unit === "x" ? `${value.toFixed(1)}x` : `${value.toFixed(1)}%`
    : "—";

  return (
    <div className={cn(
      "flex flex-col gap-2 px-6 border-r border-border/60 last:border-0",
      compact ? "py-3" : "py-4"
    )}>
      <div className="flex items-center gap-1.5">
        <span className={cn(
          "font-mono text-[10px] font-bold uppercase tracking-widest-2",
          def.soon ? "text-muted-foreground/40" : "text-muted-foreground"
        )}>
          {def.label}
        </span>
        <HudTooltip content={def.tooltip} />
      </div>

      <div className="flex items-baseline gap-2">
        <span className={cn("font-mono font-bold tabular-nums leading-none", compact ? "text-lg" : "text-2xl", STATUS_COLORS[status])}>
          {displayValue}
        </span>
        {def.soon && (
          <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/40">
            em breve
          </span>
        )}
      </div>

      <div className="relative h-0.5 w-full rounded-full bg-border/40 overflow-hidden">
        {/* Ideal range zone */}
        <span
          className={cn("absolute top-0 h-full rounded-full", def.soon ? "bg-border/30" : "bg-primary/20")}
          style={{ left: `${minPct}%`, width: `${maxPct - minPct}%` }}
        />
        {/* Actual fill */}
        {!def.soon && value !== null && (
          <span
            className={cn("absolute top-0 left-0 h-full rounded-full transition-all", BAR_COLORS[status])}
            style={{ width: `${fill}%` }}
          />
        )}
      </div>

      <span className={cn(
        "font-mono text-[9px] uppercase tracking-widest",
        def.soon ? "text-muted-foreground/30" : "text-muted-foreground/60"
      )}>
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

      {!stats || stats.total_hands === 0 ? (
        <p className="px-6 py-5 text-xs text-muted-foreground text-center">
          Importe torneios para calcular seu perfil de jogo.
        </p>
      ) : (
        <>
          {/* Row 1 — computed stats */}
          <div className="grid grid-cols-2 divide-x divide-border md:grid-cols-4">
            {ROW1.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} />
            ))}
          </div>

          {/* Row 2 — upcoming stats */}
          <div className="grid grid-cols-2 divide-x divide-border/60 border-t border-border/60 md:grid-cols-4">
            {ROW2.map((def) => (
              <StatCell key={String(def.key)} def={def} value={null} compact />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
