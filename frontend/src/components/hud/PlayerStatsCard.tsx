import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";
import type { PositionStatRef } from "@/lib/api";

/** Tradutor injetado nas funcoes de modulo (fora da arvore do React, sem `useTranslation`). */
type Traduz = (chave: string, opcoes?: Record<string, unknown>) => string;

interface PlayerStats {
  total_hands: number;
  vpip: number | null;
  pfr: number | null;
  af: number | null;
  cbet_pct: number | null;
  cbet_ip?: number | null;
  cbet_oop?: number | null;
  cbet_ip_opp?: number;
  cbet_oop_opp?: number;
  cbet_ip_ref?: SolverRef | null;
  cbet_oop_ref?: SolverRef | null;
  cbet_ip_cobertura?: number;
  cbet_oop_cobertura?: number;
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

/** Referencia do solver nos proprios spots (AY-23): P20-P80 da frequencia de aposta da range. */
type SolverRef = PositionStatRef;

// Flag direcional vindo do backend (fonte única STAT_REFERENCES, gateado por amostra).
interface StatFlag {
  band: "below" | "healthy" | "above" | "low_sample";
  flag: string | null;            // tendência curta (nit/loose/station…), só above/below
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
  /** chave em `docs:hud_defs.*`: a MESMA definicao e formula que a pagina /docs mostra */
  def: string;
  soon?: true;
}

// C-Bet IP/OOP (07/09): os 60-75 / 45-60 que chegaram a entrar nao tinham fonte, e o dono duvidou
// com razao. A referencia e a do solver nos PROPRIOS spots do jogador (AY-23), que vem do backend
// com a cobertura; sem ela, numero e amostra, sem cor.

// Row 1 — 4 fully computed stats
const ROW1: StatDef[] = [
  {
    key: "vpip",
    label: "VPIP",
    unit: "%",
    range: { min: 12, max: 22, label: "12–22%" },
    def: "vpip",
  },
  {
    key: "pfr",
    label: "PFR",
    unit: "%",
    range: { min: 9, max: 18, label: "9–18%" },
    def: "pfr",
  },
  {
    key: "af",
    label: "AF",
    unit: "x",
    range: { min: 2.0, max: 4.0, label: "2.0–4.0x" },
    def: "af",
  },
  {
    key: "cbet_pct",
    label: "C-Bet",
    unit: "%",
    range: { min: 50, max: 75, label: "50–75%" },
    def: "cbet",
  },
];

// Row 3 — defense & positional stats
const ROW3: StatDef[] = [
  {
    key: "fold_to_flop_bet",
    label: "Fold vs Bet",
    unit: "%",
    range: { min: 40, max: 55, label: "40–55%" },
    def: "fold_to_flop_bet",
  },
  {
    key: "bb_defense",
    label: "BB Defense",
    unit: "%",
    range: { min: 35, max: 55, label: "35–55%" },
    def: "bb_defense",
  },
  {
    key: "steal_pct",
    label: "Steal",
    unit: "%",
    range: { min: 25, max: 45, label: "25–45%" },
    def: "steal",
  },
  {
    key: "open_limp_pct",
    label: "Open Limp",
    unit: "%",
    range: { min: 0, max: 5, label: "0–5%" },
    def: "open_limp",
  },
];

// Row 2 — 2 derived + 2 upcoming
const ROW2: StatDef[] = [
  {
    key: "fold_to_3bet",
    label: "Fold to 3BET",
    unit: "%",
    range: { min: 55, max: 72, label: "55–72%" },
    def: "fold_to_3bet",
  },
  {
    key: "wtsd",
    label: "WTSD",
    unit: "%",
    range: { min: 25, max: 35, label: "25–35%" },
    def: "wtsd",
  },
  {
    key: "three_bet",
    label: "3BET",
    unit: "%",
    range: { min: 4, max: 8, label: "4–8%" },
    def: "three_bet",
  },
  {
    key: "w_at_sd",
    label: "W$SD",
    unit: "%",
    range: { min: 50, max: 60, label: "50–60%" },
    def: "w_at_sd",
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

function StatCell({ def, value, flag, compact, stats }: { def: StatDef; value: number | null; flag?: StatFlag; compact?: boolean; stats?: PlayerStats | null }) {
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
  const refLabel = flag?.healthy ? `${flag.healthy[0]}–${flag.healthy[1]}${def.unit === "x" ? "x" : "%"}` : def.range.label;

  /* Tooltip estruturado para TODOS os stats (dono, 07/09: "o mesmo padrao do C-Bet"), no
     formato do perfil por posicao: cabecalho, a definicao, a formula, e as linhas "Voce" e
     "Ref MTT" com o numero a direita. Definicao e formula vem de `docs:hud_defs`, a MESMA
     fonte da pagina /docs (regra 5: uma definicao, dois consumidores). O C-Bet acrescenta
     IP / OOP com a amostra (AY-19); heads-up no flop, multiway fica fora dos dois. */
  const tooltip = (
    <div className="w-[260px]" data-testid={`tooltip-${def.key}`}>
      <div className="mb-2 font-mono text-[9px] uppercase tracking-widest text-primary">{def.label}</div>
      <p className="text-[11px] leading-snug text-muted-foreground">{t(`docs:hud_defs.${def.def}.def`)}</p>
      <div className="my-2 h-px bg-border" />
      <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">{t("playerStats.tip.formula")}</div>
      <p className="mt-0.5 font-mono text-[10px] leading-snug text-foreground/90">{t(`docs:hud_defs.${def.def}.formula`)}</p>
      <div className="my-2 h-px bg-border" />
      <div className="flex items-baseline justify-between gap-3 py-0.5">
        <span className="text-[11px] text-muted-foreground">{t("playerStats.tip.you")}</span>
        <b className={cn("font-mono text-xs tabular-nums", STATUS_COLORS[status])}>{displayValue}</b>
      </div>
      <div className="flex items-baseline justify-between gap-3 py-0.5">
        <span className="text-[11px] text-muted-foreground">{t("playerStats.tip.ref")}</span>
        <span className="font-mono text-xs tabular-nums text-foreground">{refLabel}</span>
      </div>
      {def.key === "cbet_pct" && stats && (
        <>
          <div className="my-2 h-px bg-border" />
          {stats.cbet_ip == null && stats.cbet_oop == null ? (
            <p className="text-[11px] leading-snug text-muted-foreground">{t("playerStats.cbetSplitNone")}</p>
          ) : (
            <>
              {([["cbetSplitIp", stats.cbet_ip, stats.cbet_ip_opp, stats.cbet_ip_ref, stats.cbet_ip_cobertura],
                 ["cbetSplitOop", stats.cbet_oop, stats.cbet_oop_opp, stats.cbet_oop_ref, stats.cbet_oop_cobertura]] as const).map(([k, v, n, ref, cob]) => {
                // a cor do numero compara com o solver, como no perfil por posicao: fora = vermelho
                const fora = ref && v != null ? (v < ref.lo || v > ref.hi) : null;
                return (
                  <div key={k} className="py-0.5" data-testid={`cbet-${k}`}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[11px] text-muted-foreground">{t(`playerStats.${k}`)}</span>
                      <span className="whitespace-nowrap font-mono text-xs tabular-nums text-foreground">
                        <b className={fora == null ? "" : fora ? "text-red-400" : "text-emerald-400"}>{v == null ? "—" : `${v.toFixed(1)}%`}</b>
                        <span className="ml-1.5 text-[9px] text-muted-foreground/70">{t("playerStats.cbetSplitOpps", { n: n ?? 0 })}</span>
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between gap-3 text-[10px]">
                      <span className="text-muted-foreground/80">{t("playerStats.cbetSolver")}</span>
                      <span className="whitespace-nowrap font-mono tabular-nums text-foreground/90">
                        {ref ? `${ref.lo}–${ref.hi}%` : t("playerStats.cbetSolverNone", { pct: cob ?? 0 })}
                        {ref && (cob ?? 100) < 100 && <span className="ml-1 text-[9px] text-muted-foreground/60">{t("playerStats.cbetSolverCoverage", { pct: cob })}</span>}
                      </span>
                    </div>
                  </div>
                );
              })}
              <p className="mt-1.5 font-mono text-[9px] leading-snug text-muted-foreground/70">{t("playerStats.cbetSplitNote")}</p>
            </>
          )}
        </>
      )}
    </div>
  );

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
        <HudTooltip content={tooltip} />
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
          <span className="font-mono text-[9px] font-bold uppercase tracking-wide text-yellow-400" title={t("playerStats.tendenciaDirecional")}>
            {/* 03/09: o backend manda uma CHAVE (stubborn/passive/...), não texto de tela —
                antes ia cru pra tela e vazava português mesmo com o idioma em inglês.
                defaultValue = a própria chave, rede de segurança se um flag novo ainda
                não tiver tradução (nunca crasha, nunca mostra "playerStats.flags.x" literal). */}
            {flag.band === "above" ? "↑" : "↓"} {t(`playerStats.flags.${flag.flag}`, { defaultValue: flag.flag })}
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
        {t("playerStats.refMtt", { range: refLabel })}
      </span>
    </div>
  );
}

// Confiança estatistica baseada em volume:
// - < 200 mãos: IC > ±10pp em VPIP/PFR — numero ainda nao se estabilizou
// - 200-1000: IC tipico ±5pp — diretional, nao definitivo
// - >= 1000: IC < ±3pp — confiavel para benchmarking
function sampleConfidence(n: number, t: Traduz): { level: "low" | "medium" | "high"; label: string; tooltip: string } {
  if (n < 200) return {
    level: "low",
    label: t("playerStats.amostra.baixaLabel"),
    tooltip: t("playerStats.amostra.baixaTooltip", { n }),
  };
  if (n < 1000) return {
    level: "medium",
    label: t("playerStats.amostra.mediaLabel"),
    tooltip: t("playerStats.amostra.mediaTooltip", { n }),
  };
  return {
    level: "high",
    label: t("playerStats.amostra.robustaLabel"),
    tooltip: t("playerStats.amostra.robustaTooltip", { n }),
  };
}

const CONFIDENCE_CLS: Record<"low" | "medium" | "high", string> = {
  low:    "bg-amber-500/10 text-amber-300 ring-amber-500/30",
  medium: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
  high:   "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
};

export function PlayerStatsCard({ stats, v2 = false }: Props) {
  const { t } = useTranslation("dashboard");
  const conf = stats && stats.total_hands > 0 ? sampleConfidence(stats.total_hands, t) : null;
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
          <HudTooltip content={t("playerStats.hudResumo")} />
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
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} flag={stats.flags?.[def.key as string]} stats={stats} />
            ))}
          </div>

          {/* Row 2 — fold to 3bet, wtsd, 3bet, w$sd */}
          <div className="grid grid-cols-2 divide-x divide-border/60 border-t border-border/60 md:grid-cols-4">
            {ROW2.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} flag={stats.flags?.[def.key as string]} stats={stats} compact />
            ))}
          </div>

          {/* Row 3 — defense & positional stats */}
          <div className="grid grid-cols-2 divide-x divide-border/40 border-t border-border/40 md:grid-cols-4">
            {ROW3.map((def) => (
              <StatCell key={String(def.key)} def={def} value={stats[def.key] as number | null} flag={stats.flags?.[def.key as string]} stats={stats} compact />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
