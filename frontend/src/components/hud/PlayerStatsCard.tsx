import { Activity } from "lucide-react";
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
  unit: "%" | "x" | "";
  range: { min: number; max: number; label: string };
  tooltip: string;
  unavailable?: boolean;
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
      "PreFlop Raise — % de mãos em que o jogador abriu ou 3-betou pré-flop. MTT ideal: 9–18%. PFR próximo ao VPIP indica jogo agressivo; diferença grande indica passividade.",
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
  {
    key: "three_bet",
    label: "3BET",
    unit: "%",
    range: { min: 4, max: 8, label: "4–8%" },
    tooltip:
      "% de mãos em que o jogador fez 3-bet pré-flop. MTT ideal: 4–8%. Requer rastreamento de sequência de apostas — disponível em versão futura.",
    unavailable: true,
  },
  {
    key: "fold_to_3bet",
    label: "Fold to 3BET",
    unit: "%",
    range: { min: 55, max: 72, label: "55–72%" },
    tooltip:
      "% de vezes que deu fold após levar um 3-bet. MTT ideal: 55–72%. Requer rastreamento de sequência de apostas — disponível em versão futura.",
    unavailable: true,
  },
  {
    key: "wtsd",
    label: "WTSD",
    unit: "%",
    range: { min: 25, max: 35, label: "25–35%" },
    tooltip:
      "Went To ShowDown — % das mãos que viram o flop e chegaram ao showdown. MTT ideal: 25–35%. Requer rastreamento de showdowns — disponível em versão futura.",
    unavailable: true,
  },
  {
    key: "w_at_sd",
    label: "W$SD",
    unit: "%",
    range: { min: 50, max: 60, label: "50–60%" },
    tooltip:
      "Won money at ShowDown — % de showdowns vencidos. Meta: > 50% para ser +EV nos confrontos. Requer rastreamento de showdowns — disponível em versão futura.",
    unavailable: true,
  },
];

type Status = "ok" | "warn" | "danger" | "na";

function getStatus(value: number | null, def: StatDef): Status {
  if (def.unavailable || value === null) return "na";
  const { min, max } = def.range;
  if (value >= min && value <= max) return "ok";
  const margin = (max - min) * 0.35;
  if (value >= min - margin && value <= max + margin) return "warn";
  return "danger";
}

const STATUS_STYLES: Record<Status, { value: string; dot: string; bar: string }> = {
  ok:     { value: "text-primary",     dot: "bg-primary",     bar: "bg-primary" },
  warn:   { value: "text-yellow-400",  dot: "bg-yellow-400",  bar: "bg-yellow-400" },
  danger: { value: "text-destructive", dot: "bg-destructive", bar: "bg-destructive" },
  na:     { value: "text-muted-foreground/40", dot: "bg-border", bar: "bg-border" },
};

function StatRow({ def, value }: { def: StatDef; value: number | null }) {
  const status = getStatus(value, def);
  const styles = STATUS_STYLES[status];
  const { min, max } = def.range;

  const displayValue =
    value !== null
      ? def.unit === "x"
        ? `${value.toFixed(1)}x`
        : `${value.toFixed(1)}%`
      : "—";

  // Bar fill: 0–100 mapped over [min - margin, max + margin] range
  const margin = (max - min) * 0.35;
  const lo = min - margin;
  const hi = max + margin;
  const fill =
    value !== null && !def.unavailable
      ? Math.max(0, Math.min(100, ((value - lo) / (hi - lo)) * 100))
      : 0;

  // Range zone markers
  const minPct = ((min - lo) / (hi - lo)) * 100;
  const maxPct = ((max - lo) / (hi - lo)) * 100;

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
      {/* Label + range */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span
          className={cn(
            "size-1.5 shrink-0 rounded-full",
            def.unavailable ? "bg-border" : styles.dot
          )}
          aria-hidden
        />
        <span className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground truncate">
          {def.label}
        </span>
        <HudTooltip content={def.tooltip} />
      </div>

      {/* Value */}
      <span
        className={cn(
          "font-mono text-sm font-bold tabular-nums text-right",
          def.unavailable ? "text-muted-foreground/40" : styles.value
        )}
      >
        {displayValue}
      </span>

      {/* Progress bar + range label spanning both columns */}
      <div className="col-span-2 space-y-0.5">
        <div className="relative h-1 w-full rounded-full bg-border/60 overflow-hidden">
          {/* Ideal range highlight */}
          <span
            className="absolute top-0 h-full bg-primary/15 rounded-full"
            style={{ left: `${minPct}%`, width: `${maxPct - minPct}%` }}
          />
          {/* Actual fill */}
          {!def.unavailable && value !== null && (
            <span
              className={cn("absolute top-0 left-0 h-full rounded-full transition-all", styles.bar)}
              style={{ width: `${fill}%` }}
            />
          )}
        </div>
        <div className="flex justify-between">
          <span className="font-mono text-[9px] text-muted-foreground/50 uppercase tracking-widest">
            {def.unavailable ? "Em breve" : `Ref ${def.range.label}`}
          </span>
        </div>
      </div>
    </div>
  );
}

export function PlayerStatsCard({ stats }: Props) {
  const hasData = stats && stats.total_hands > 0;

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="size-4 text-primary" aria-hidden />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Player HUD Stats
          </span>
          <HudTooltip content="Indicadores táticos do seu perfil de jogo. Estatísticas calculadas com base nas decisões registradas. Stats marcados como 'Em breve' requerem dados adicionais de histórico." />
        </div>
        <span className="font-mono text-[10px] text-primary">
          {hasData ? `${stats.total_hands} mãos` : "sem dados"}
        </span>
      </div>

      {!hasData ? (
        <p className="text-xs text-muted-foreground text-center py-6">
          Importe torneios para calcular seu perfil de jogo.
        </p>
      ) : (
        <div className="space-y-4">
          {STAT_DEFS.map((def) => (
            <StatRow
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
