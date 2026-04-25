import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

interface PlayerStats {
  total_hands: number;
  vpip: number | null;
  pfr: number | null;
  af: number | null;
  flop_bet_pct: number | null;
  fold_to_3bet: number | null;
  wtsd: number | null;
  three_bet: number | null;
  w_at_sd: number | null;
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

// Row 1 — 4 fully computed stats
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

// Row 2 — 2 derived + 2 upcoming
const ROW2: StatDef[] = [
  {
    key: "fold_to_3bet",
    label: "Fold to 3BET",
    unit: "%",
    range: { min: 55, max: 72, label: "55–72%" },
    tooltip: "% de vezes que deu fold após abrir e enfrentar um 3-bet pré-flop. MTT ideal: 55–72%. Calculado a partir do padrão raise→fold em decisões pré-flop.",
  },
  {
    key: "wtsd",
    label: "WTSD",
    unit: "%",
    range: { min: 25, max: 35, label: "25–35%" },
    tooltip: "Went to Deep Streets — % de mãos que viram flop e chegaram a ter decisão no river. Aproximação de WTSD (showdown data não disponível). MTT ideal: 25–35%.",
  },
  {
    key: "three_bet",
    label: "3BET",
    unit: "%",
    range: { min: 4, max: 8, label: "4–8%" },
    tooltip: "3-Bet% — % de mãos em que o hero re-raised pré-flop (quando já havia um raise antes). MTT ideal: 4–8%. Abaixo de 3% = muito passivo; acima de 10% = overaggressive pré-flop.",
  },
  {
    key: "w_at_sd",
    label: "W$SD",
    unit: "%",
    range: { min: 50, max: 60, label: "50–60%" },
    tooltip: "Won money at ShowDown — % de showdowns vencidos. Meta: > 50% para ser +EV nos confrontos. Calculado a partir das mãos que chegaram ao showdown no hand history.",
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
  na:     "text-muted-foreground/50",
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
      "flex flex-col gap-2 px-5 border-r border-border/60 last:border-0",
      compact ? "py-3" : "py-4"
    )}>
      <div className="flex items-center gap-1.5">
        <span className={cn(
          "font-mono text-[10px] font-bold uppercase tracking-widest-2",
          def.soon ? "text-muted-foreground/60" : "text-muted-foreground"
        )}>
          {def.label}
        </span>
        <HudTooltip content={def.tooltip} />
      </div>

      <div className="flex items-baseline gap-2">
        <span className={cn(
          "font-mono font-bold tabular-nums leading-none",
          compact ? "text-xl" : "text-2xl",
          STATUS_COLORS[status]
        )}>
          {displayValue}
        </span>
        {def.soon && (
          <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">
            em breve
          </span>
        )}
      </div>

      <div className="relative h-0.5 w-full rounded-full bg-border/40 overflow-hidden">
        <span
          className={cn("absolute top-0 h-full rounded-full", def.soon ? "bg-border/30" : "bg-primary/20")}
          style={{ left: `${minPct}%`, width: `${maxPct - minPct}%` }}
        />
        {!def.soon && value !== null && (
          <span
            className={cn("absolute top-0 left-0 h-full rounded-full transition-all", BAR_COLORS[status])}
            style={{ width: `${fill}%` }}
          />
        )}
      </div>

      <span className={cn(
        "font-mono text-[9px] uppercase tracking-widest",
        def.soon ? "text-muted-foreground/50" : "text-muted-foreground/60"
      )}>
        Ref MTT {def.range.label}
      </span>
    </div>
  );
}

export function PlayerStatsCard({ stats }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface shadow-elevated">
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Player HUD Stats
          </span>
          <HudTooltip content="Indicadores táticos do seu perfil de jogo. Row 1: VPIP, PFR, AF, Flop Bet — calculados diretamente. Row 2: Fold to 3BET e WTSD (aproximados), 3BET e W$SD (em breve)." />
        </div>
        <span className="font-mono text-[10px] text-primary">
          {stats && stats.total_hands > 0 ? `${stats.total_hands} mãos` : "sem dados"}
        </span>
      </div>

      {!stats || stats.total_hands === 0 ? (
        <p className="px-6 py-5 text-xs text-muted-foreground text-center">
          Importe torneios para calcular seu perfil de jogo.
        </p>
      ) : (
        <>
          {/* Row 1 — 4 computed stats */}
          <div className="grid grid-cols-2 divide-x divide-border md:grid-cols-4">
            {ROW1.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} />
            ))}
          </div>

          {/* Row 2 — 2 derived + 2 upcoming */}
          <div className="grid grid-cols-2 divide-x divide-border/60 border-t border-border/60 md:grid-cols-4">
            {ROW2.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} compact />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
