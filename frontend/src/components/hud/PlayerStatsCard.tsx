import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

interface PlayerStats {
  total_hands: number;
  vpip: number | null;
  pfr: number | null;
  af: number | null;
  cbet_pct: number | null;
  fold_to_3bet: number | null;
  wtsd: number | null;
  three_bet: number | null;
  w_at_sd: number | null;
  fold_to_flop_bet: number | null;
  bb_defense: number | null;
  steal_pct: number | null;
  open_limp_pct: number | null;
  flags?: Record<string, StatFlag>;
}

// Flag direcional vindo do backend (fonte única STAT_REFERENCES, gateado por amostra).
interface StatFlag {
  band: "below" | "healthy" | "above" | "low_sample";
  flag: string | null;            // tendência curta (nit/loose/station…) — só above/below
  healthy?: [number, number];     // faixa saudável corrigida
}

interface Props {
  stats?: PlayerStats | null;
  v2?: boolean;
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
    key: "cbet_pct",
    label: "C-Bet",
    unit: "%",
    range: { min: 50, max: 75, label: "50–75%" },
    tooltip: "Continuation Bet — % de vezes que apostou no flop como agressor pré-flop (opener/raiser). Denominador: mãos em que abriu ou 3-betou pré e viu o flop. MTT ideal: 50–75%.",
  },
];

// Row 3 — defense & positional stats
const ROW3: StatDef[] = [
  {
    key: "fold_to_flop_bet",
    label: "Fold vs Bet",
    unit: "%",
    range: { min: 40, max: 55, label: "40–55%" },
    tooltip: "Fold to Flop Bet — proxy para Fold to C-Bet. % de vezes que deu fold no flop ao enfrentar uma aposta. MTT ideal: 40–55%. Acima de 65% = passivo demais (desiste muito cedo); abaixo de 35% = too sticky (chama sem equity suficiente).",
  },
  {
    key: "bb_defense",
    label: "BB Defense",
    unit: "%",
    range: { min: 35, max: 55, label: "35–55%" },
    tooltip: "BB Defense Rate — % de vezes que defendeu a Big Blind (call ou 3-bet) ao enfrentar uma abertura pré-flop. MTT ideal: 35–55%. Abaixo de 30% = folda BB em excesso, dando fold equity gratuita aos opponents.",
  },
  {
    key: "steal_pct",
    label: "Steal",
    unit: "%",
    range: { min: 25, max: 45, label: "25–45%" },
    tooltip: "Steal% — % de vezes que abriu (raise/shove) do BTN, CO ou SB quando a ação chegou sem aposta anterior. MTT ideal: 25–45%. Abaixo de 20% = perde vantagem posicional e deixa equity no pote; acima de 50% = overaggression exploitável.",
  },
  {
    key: "open_limp_pct",
    label: "Open Limp",
    unit: "%",
    range: { min: 0, max: 5, label: "0–5%" },
    tooltip: "Open Limp% — % de vezes que entrou no pote com call (sem raise em frente) de posição non-BB. MTT ideal: 0–5%. Limp preflop remove fold equity, cria potes multiway fora de posição e é exploitável por qualquer squeeze do BTN/BB. Acima de 8% = leak sério.",
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
    tooltip: "3-Bet% — das vezes em que ENFRENTOU um open pré-flop (oportunidades de 3-bet), % em que o hero re-raised. Denominador = mãos enfrentando um raise, não todas as mãos. MTT ideal: 4–8%. Abaixo de 3% = muito passivo; acima de 10% = overaggressive pré-flop.",
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

function StatCell({ def, value, flag, compact }: { def: StatDef; value: number | null; flag?: StatFlag; compact?: boolean }) {
  const { t } = useTranslation("dashboard");
  // Flag do backend (refs MTT corrigidas + gate de amostra) tem prioridade sobre o range
  // inline. above/below = tendência (warn, direcional — não "danger"); healthy = ok.
  const status: Status = flag
    ? (flag.band === "healthy" ? "ok" : flag.band === "low_sample" ? "na" : "warn")
    : getStatus(value, def.range, def.soon);
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
        {flag && flag.flag && (flag.band === "above" || flag.band === "below") && (
          <span className="font-mono text-[9px] font-bold uppercase tracking-wide text-yellow-400" title="Tendência direcional vs referência MTT">
            {flag.band === "above" ? "↑" : "↓"} {flag.flag}
          </span>
        )}
        {def.soon && (
          <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">
            {t("playerStats.soon")}
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
        {t("playerStats.refMtt", { range: flag?.healthy ? `${flag.healthy[0]}–${flag.healthy[1]}${def.unit === "x" ? "x" : "%"}` : def.range.label })}
      </span>
    </div>
  );
}

// Confiança estatistica baseada em volume:
// - < 200 mãos: IC > ±10pp em VPIP/PFR — numero ainda nao se estabilizou
// - 200-1000: IC tipico ±5pp — diretional, nao definitivo
// - >= 1000: IC < ±3pp — confiavel para benchmarking
function sampleConfidence(n: number): { level: "low" | "medium" | "high"; label: string; tooltip: string } {
  if (n < 200) return {
    level: "low",
    label: "Amostra baixa",
    tooltip: `${n} mãos — intervalo de confiança alto (>±10pp em VPIP/PFR). Com pouca amostra os números são DIRECIONAIS: indicam a tendência (mais tight/loose/passivo), não valores exatos — ±alguns pontos não mudam o read. Mire 200+ mãos pra leitura confiável; 1000+ pra benchmarking.`,
  };
  if (n < 1000) return {
    level: "medium",
    label: "Amostra média",
    tooltip: `${n} mãos — IC típico ±5pp. Tendências confiáveis mas valores absolutos ainda flutuam. Atingir 1000+ mãos pra benchmarking firme.`,
  };
  return {
    level: "high",
    label: "Amostra robusta",
    tooltip: `${n} mãos — IC < ±3pp. Números estatisticamente confiáveis para comparação com referências.`,
  };
}

const CONFIDENCE_CLS: Record<"low" | "medium" | "high", string> = {
  low:    "bg-amber-500/10 text-amber-300 ring-amber-500/30",
  medium: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
  high:   "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
};

export function PlayerStatsCard({ stats, v2 = false }: Props) {
  const { t } = useTranslation("dashboard");
  const conf = stats && stats.total_hands > 0 ? sampleConfidence(stats.total_hands) : null;
  return (
    <div className={v2
      ? "overflow-hidden rounded-xl ring-1 ring-border bg-card/60"
      : "overflow-hidden rounded-xl border border-border bg-hud-surface shadow-elevated"}>
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Player HUD Stats
          </span>
          <HudTooltip content="Indicadores táticos do seu perfil de jogo. Row 1: VPIP, PFR, AF, C-Bet. Row 2: Fold to 3BET, WTSD, 3BET%, W$SD. Row 3: Fold vs Flop Bet (proxy FtCB), BB Defense, Steal%, Open Limp%." />
        </div>
        <div className="flex items-center gap-2">
          {conf && (
            <span
              className={cn(
                "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide ring-1 cursor-help",
                CONFIDENCE_CLS[conf.level]
              )}
              title={conf.tooltip}
            >
              {conf.label}
            </span>
          )}
          <span className="font-mono text-[10px] text-primary">
            {stats && stats.total_hands > 0 ? t("playerStats.hands", { n: stats.total_hands }) : t("playerStats.noStats")}
          </span>
        </div>
      </div>

      {!stats || stats.total_hands === 0 ? (
        <p className="px-6 py-5 text-xs text-muted-foreground text-center">
          {t("playerStats.noData")}
        </p>
      ) : (
        <>
          {/* Row 1 — 4 computed stats */}
          <div className="grid grid-cols-2 divide-x divide-border md:grid-cols-4">
            {ROW1.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} flag={stats.flags?.[def.key as string]} />
            ))}
          </div>

          {/* Row 2 — fold to 3bet, wtsd, 3bet, w$sd */}
          <div className="grid grid-cols-2 divide-x divide-border/60 border-t border-border/60 md:grid-cols-4">
            {ROW2.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} flag={stats.flags?.[def.key as string]} compact />
            ))}
          </div>

          {/* Row 3 — defense & positional stats */}
          <div className="grid grid-cols-2 divide-x divide-border/40 border-t border-border/40 md:grid-cols-4">
            {ROW3.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} flag={stats.flags?.[def.key as string]} compact />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
