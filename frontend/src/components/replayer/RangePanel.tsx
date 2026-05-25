import { useState, useEffect } from "react";
import { LayoutGrid, X, Loader2, CheckCircle2, XCircle, AlertTriangle, Info } from "lucide-react";
import { GtoMixedBadge } from "./GtoMixedBadge";
import { RangeGrid } from "./RangeGrid";
import {
  heroHand, RANGES, normalizePosition, PUSH_FOLD, getPushFoldBucket,
  Position, RangeType, POSITIONS, RANGE_TYPES, RangeSet,
} from "@/data/ranges";
import { ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";
import { computeEffectiveGtoLabel } from "@/lib/gtoUtils";

function authFetch(path: string): Promise<Response> {
  const t = sessionStorage.getItem("ll_token");
  const base = import.meta.env.VITE_API_URL ?? "";
  return fetch(`${base}${path}`, {
    headers: t ? { Authorization: `Bearer ${t}` } : {},
  });
}

interface Props {
  step: ReplayStep;
  hero: string;
  heroCards: string[];
  onClose: () => void;
  onHeaderMouseDown?: (e: React.MouseEvent<HTMLDivElement>) => void;
}

// Frequência por ação (estilo GTO Wizard — soma 1.0)
interface HandFreqApi {
  raise?: number; call?: number; allin?: number; fold?: number;
}

interface PreflopRangesResp {
  position: string;
  stack_bb: number;
  stack_bucket: string;
  rfi: { hands: string[]; pct: number; raise_pct?: number; allin_pct?: number; frequencies?: Record<string, HandFreqApi> } | null;
  vs_rfi: Record<string, {
    hands: string[];
    raise3bet: string[];
    call: string[];
    allin?: string[];
    pct_play: number;
    call_pct?: number;
    raise_pct?: number;
    allin_pct?: number;
    acoes: string[];
    frequencies?: Record<string, HandFreqApi>;
  }>;
  vs_3bet: { hands_4bet: string[]; hands_call: string[]; pct_continua: number } | null;
}

function fmtAction(a: string): string {
  const s = (a ?? "").toLowerCase();
  if (s === "jam" || s === "allin" || s === "all-in") return "Shove";
  if (s === "fold") return "Fold";
  if (s === "call") return "Call";
  if (s === "raise") return "Raise";
  if (s === "bet")  return "Bet";
  if (s === "check") return "Check";
  return a;
}

const SCENARIO_TO_TYPE: Record<string, RangeType> = {
  rfi: 'open',
  vs_rfi: 'call',
  vs_3bet: '3bet',
};

const SCENARIO_LABEL: Record<string, string> = {
  rfi: 'Raise First In (abertura)',
  vs_rfi: 'vs Open (defender)',
  vs_3bet: 'vs 3-Bet (continuar)',
  vs_shove_fallback: 'Call vs Shove',
};

const QUALITY_META: Record<string, { label: string; color: string; icon: typeof CheckCircle2 }> = {
  correct:    { label: 'Correto (GTO)',    color: 'text-emerald-400', icon: CheckCircle2 },
  acceptable: { label: 'Aceitável',        color: 'text-sky-400',     icon: Info          },
  leak:       { label: 'Leak',             color: 'text-amber-400',   icon: AlertTriangle },
  major_leak: { label: 'Leak grave',       color: 'text-red-400',     icon: XCircle       },
  unknown:    { label: 'Sem dados',        color: 'text-muted-foreground', icon: Info     },
};

function buildRangeFromApi(resp: PreflopRangesResp, type: RangeType, openerPos?: string): RangeSet | null {
  if (type === 'open') {
    if (!resp.rfi) return null;
    return {
      label: `Open ${resp.position} (${resp.stack_bucket})`,
      description: `Open ${(resp.rfi.pct * 100).toFixed(1)}% das mãos`,
      raise: new Set(resp.rfi.hands),
      frequencies: resp.rfi.frequencies,
    };
  }
  if (type === '3bet') {
    if (!resp.vs_3bet) return null;
    return {
      label: `vs 3-Bet ${resp.position} (${resp.stack_bucket})`,
      description: `${(resp.vs_3bet.pct_continua * 100).toFixed(0)}% continuam`,
      raise: new Set(resp.vs_3bet.hands_4bet),
      call:  new Set(resp.vs_3bet.hands_call),
    };
  }
  if (type === 'call') {
    const openers = Object.keys(resp.vs_rfi);
    if (!openers.length) return null;
    const resolvedKey = openerPos
      ? (resp.vs_rfi[openerPos] ? openerPos
        : resp.vs_rfi[openerPos + '_open'] ? openerPos + '_open'
        : null)
      : null;
    const key = resolvedKey ?? openers[0];
    const def = resp.vs_rfi[key];
    const parts: string[] = [];
    if (def.call_pct  != null && def.call_pct  > 0.001) parts.push(`Call ${(def.call_pct*100).toFixed(1)}%`);
    if (def.raise_pct != null && def.raise_pct > 0.001) parts.push(`Raise ${(def.raise_pct*100).toFixed(1)}%`);
    if (def.allin_pct != null && def.allin_pct > 0.001) parts.push(`Allin ${(def.allin_pct*100).toFixed(1)}%`);
    const description = `vs ${key.replace('_open', '')} open · ${(def.pct_play*100).toFixed(1)}% defendem${parts.length ? ` · ${parts.join(' / ')}` : ''}`;
    return {
      label: `vs ${key.replace('_open', '')} open · ${resp.position} (${resp.stack_bucket})`,
      description,
      raise: new Set(def.raise3bet ?? []),
      call:  new Set(def.call ?? []),
      allin: new Set(def.allin ?? []),
      frequencies: def.frequencies,
    };
  }
  return null;
}

export function RangePanel({ step, hero, heroCards, onClose, onHeaderMouseDown }: Props) {
  const heroSeat    = Object.entries(step.seats ?? {}).find(([, s]) => s.player === hero);
  const detectedPos = heroSeat ? normalizePosition(heroSeat[1].pos) : null;
  const gto         = step.preflop_gto;

  const [pos,  setPos]  = useState<Position>(detectedPos ?? 'BTN');

  const [apiData, setApiData] = useState<PreflopRangesResp | null>(null);
  const [loading, setLoading] = useState(false);

  // hero_stack_bb só existe em steps de decisão do hero; fallback via seats + bb
  const heroSeatStack = heroSeat ? heroSeat[1].stack : null;
  const stackBb = step.hero_stack_bb
    ?? (heroSeatStack && step.bb ? Math.round(heroSeatStack / step.bb) : null)
    ?? 30;
  const openerPos  = gto?.vs_position ?? undefined;
  const pushBucket = getPushFoldBucket(stackBb);
  const isPushZone = pushBucket !== null;

  // Default: segue o cenário (open pra RFI, call pra vs_RFI, 3bet pra vs 3-bet).
  // Aba 'shove' (Nash simplificado) só é default quando NÃO temos GW v3 — caso contrário
  // o range de open/call já mostra raise+allin com freqs reais (mais informativo).
  const defaultType: RangeType =
    (gto?.scenario ? (SCENARIO_TO_TYPE[gto.scenario] ?? 'open')
      : (Object.entries(step.bets ?? {}).some(([seat, bet]) =>
          step.seats?.[seat]?.player !== hero && bet > (step.bb ?? 0))
        ? 'call' : 'open'));

  const [type, setType] = useState<RangeType>(defaultType);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setApiData(null);
    authFetch(`/preflop-ranges?position=${pos}&stack_bb=${stackBb}`)
      .then(r => r.json())
      .then((d: PreflopRangesResp) => { if (!cancelled) setApiData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pos, stackBb]);

  const staticRange    = RANGES[pos];
  const nashRange      = pushBucket ? PUSH_FOLD[pushBucket]?.[pos] : null;

  const availableTypes = RANGE_TYPES.filter(t => {
    // Aba shove (Nash simplificado) só faz sentido sem GW v3 — o range de open já tem
    // raise+allin com freqs precisas. Esconde quando apiData.rfi existe.
    if (t.id === 'shove') return isPushZone && !!nashRange && !apiData?.rfi;
    if (apiData) {
      if (t.id === 'open')  return !!apiData.rfi;
      if (t.id === '3bet')  return !!apiData.vs_3bet;
      if (t.id === 'call')  return Object.keys(apiData.vs_rfi).length > 0;
    }
    return staticRange?.[t.id] !== undefined;
  });

  const effectiveType: RangeType = availableTypes.some(t => t.id === type)
    ? type : (availableTypes[0]?.id ?? 'open');

  const displayRange: RangeSet | null | undefined = effectiveType === 'shove'
    ? nashRange
    : (apiData ? buildRangeFromApi(apiData, effectiveType, openerPos) : staticRange?.[effectiveType]);

  const hand = heroHand(heroCards);

  // Show GTO context when data is available — detectedPos may be null for positions
  // not yet in the static list (e.g. LJ before the fix), so we show it regardless
  const showGtoCtx = gto?.available ?? false;

  // Solver overrides RegLife when available — same logic as effectiveGtoLabel in Replayer.tsx
  const solverStratSorted = step.gto_strategy
    ? [...step.gto_strategy].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0))
    : [];
  const effectiveGtoLabel = computeEffectiveGtoLabel(solverStratSorted, step.gto_label, step.action);
  const solverOverridesRegLife =
    !!effectiveGtoLabel &&
    ['gto_correct', 'gto_mixed', 'gto_minor_deviation'].includes(effectiveGtoLabel) &&
    ['leak', 'major_leak'].includes(gto?.action_quality ?? '');

  const quality = showGtoCtx && !solverOverridesRegLife
    ? QUALITY_META[gto!.action_quality ?? 'unknown'] : null;
  const QIcon   = quality?.icon ?? Info;

  return (
    <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      {/* Header */}
      <div
        className={cn("flex items-center justify-between", onHeaderMouseDown && "cursor-grab active:cursor-grabbing select-none")}
        onMouseDown={onHeaderMouseDown}
      >
        <div className="flex items-center gap-2">
          <LayoutGrid className="size-3.5 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-foreground">
            Range Reference
          </span>
          {hand && <span className="font-mono text-[10px] text-primary font-bold">· {hand}</span>}
          {apiData && <span className="font-mono text-[8px] text-emerald-400/60">{apiData.stack_bucket}</span>}
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="size-3 text-muted-foreground animate-spin" />}
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors" aria-label="Fechar">
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {/* GTO context banner */}
      {showGtoCtx && gto && (
        <div className={cn(
          "rounded-lg border px-3 py-2 space-y-1.5",
          solverOverridesRegLife
            ? "border-border/40 bg-muted/10"
            : gto.in_range ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
        )}>
          {/* Scenario — em PF zone renomear "Raise First In" para "Push/Fold" */}
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide">
            Cenário: {
              isPushZone && gto.scenario === 'rfi'
                ? `Push/Fold (RFI · ${stackBb.toFixed(0)}bb)`
                : isPushZone && gto.scenario === 'vs_rfi'
                ? `Push/Fold (Reshove vs Open · ${stackBb.toFixed(0)}bb)`
                : (SCENARIO_LABEL[gto.scenario] ?? gto.scenario)
            }
          </p>

          {/* Solver override notice */}
          {solverOverridesRegLife ? (
            <div className="flex items-center flex-wrap gap-2">
              <p className="font-mono text-[9px] text-muted-foreground/60 italic">
                Veredicto do solver substitui análise de range estática.
              </p>
              {(effectiveGtoLabel === 'gto_mixed' || effectiveGtoLabel === 'gto_minor_deviation') && (
                <GtoMixedBadge label={effectiveGtoLabel} size="xs" />
              )}
            </div>
          ) : (
            <>
              {/* In-range status */}
              <div className="flex items-center gap-1.5">
                {gto.in_range
                  ? <CheckCircle2 className="size-3 text-emerald-400 shrink-0" />
                  : <XCircle     className="size-3 text-amber-400 shrink-0" />}
                <span className={cn("font-mono text-[10px] font-bold", gto.in_range ? "text-emerald-400" : "text-amber-400")}>
                  {hand} {gto.in_range ? "está no range GTO" : "fora do range GTO"}
                </span>
              </div>

              {/* Quality + recommended */}
              <div className="flex items-center gap-2 flex-wrap">
                {quality && (
                  <div className={cn("flex items-center gap-1", quality.color)}>
                    <QIcon className="size-3 shrink-0" />
                    <span className="font-mono text-[9px]">{quality.label}</span>
                  </div>
                )}
                {gto.recommended_actions.length > 0 && (
                  <span className="font-mono text-[9px] text-muted-foreground">
                    GTO: <span className="text-primary font-bold">{gto.recommended_actions.map(fmtAction).join(' / ')}</span>
                  </span>
                )}
                {gto.range_pct > 0 && (
                  <span className="font-mono text-[9px] text-muted-foreground">
                    Range: top <span className="text-foreground">{(gto.range_pct * 100).toFixed(0)}%</span>
                  </span>
                )}
              </div>
              {gto.reasoning && (
                <p className="font-mono text-[9px] text-muted-foreground/70 leading-relaxed">
                  {gto.reasoning}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* Push/Fold zone banner — só mostra quando NÃO há dados GW v3 disponíveis
          (Nash simplificado faz sentido em 4-6bb fallback). GW v3 cobre 10bb+ com
          freqs reais incluindo raise sized — banner ficaria contraditório. */}
      {isPushZone && effectiveType === 'shove' && !apiData?.rfi && (
        <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 px-3 py-2 space-y-1">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[9px] font-bold uppercase tracking-wide text-violet-400">
              Push/Fold Zone · {stackBb.toFixed(0)}bb (Nash simplificado)
            </span>
          </div>
          <p className="font-mono text-[9px] text-muted-foreground leading-relaxed">
            Sem dados GTO Wizard pra este bucket — usando tabela Nash binária shove/fold.
          </p>
          {hand && nashRange && (
            <p className={cn(
              "font-mono text-[10px] font-bold",
              (nashRange.raise.has(hand) || nashRange.call?.has(hand)) ? "text-emerald-400" : "text-amber-400"
            )}>
              {hand}: {(nashRange.raise.has(hand) || nashRange.call?.has(hand)) ? '✓ no range' : '✗ fora do range'}
            </p>
          )}
        </div>
      )}

      {/* Position selector */}
      <div className="grid gap-px rounded-md overflow-hidden ring-1 ring-border"
        style={{ gridTemplateColumns: `repeat(${POSITIONS.length}, minmax(0, 1fr))` }}>
        {POSITIONS.map(p => (
          <button key={p} onClick={() => setPos(p)}
            className={cn(
              'py-1 font-mono text-[9px] font-bold uppercase transition-colors',
              pos === p ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/30',
            )}>
            {p}
          </button>
        ))}
      </div>

      {/* Range type selector */}
      <div className="grid gap-px rounded-md overflow-hidden ring-1 ring-border"
        style={{ gridTemplateColumns: `repeat(${availableTypes.length}, minmax(0, 1fr))` }}>
        {availableTypes.map(t => (
          <button key={t.id} onClick={() => setType(t.id)}
            className={cn(
              'py-1 font-mono text-[9px] font-bold uppercase transition-colors',
              effectiveType === t.id ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/30',
            )}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Aviso quando a aba ativa não corresponde ao cenário da decisão */}
      {showGtoCtx && gto?.scenario && SCENARIO_TO_TYPE[gto.scenario] && effectiveType !== SCENARIO_TO_TYPE[gto.scenario] && (
        <div className="rounded-md border border-amber-500/25 bg-amber-500/5 px-3 py-1.5">
          <p className="font-mono text-[9px] text-amber-400/80 leading-snug">
            Esta grade mostra referência ({effectiveType === 'open' ? 'abertura RFI' : effectiveType === '3bet' ? '3-bet' : 'defesa'}).
            {" "}A decisão desta mão ({SCENARIO_TO_TYPE[gto.scenario] === 'call' ? 'defesa vs open' : SCENARIO_TO_TYPE[gto.scenario] === '3bet' ? 'resposta ao 3-bet' : 'abertura'}) está na aba <strong className="text-amber-400">{availableTypes.find(t => t.id === SCENARIO_TO_TYPE[gto!.scenario])?.label ?? SCENARIO_TO_TYPE[gto.scenario]}</strong>.
          </p>
        </div>
      )}

      {/* Range grid — sempre interativo (tooltips por célula). */}
      {displayRange ? (
        <RangeGrid range={displayRange} heroHand={hand} />
      ) : loading ? (
        <p className="text-xs text-muted-foreground text-center py-4 animate-pulse">Carregando ranges…</p>
      ) : (
        <p className="text-xs text-muted-foreground text-center py-4">Range não disponível para esta posição.</p>
      )}

      {/* Pro notes — suprimidas quando solver contradiz RegLife */}
      {showGtoCtx && !solverOverridesRegLife && gto?.pro_notes && gto.pro_notes.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 px-3 py-2 space-y-1">
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide mb-1.5">Análise GTO</p>
          {gto.pro_notes.map((note, i) => (
            <p key={i} className="font-mono text-[9px] text-foreground/80 leading-relaxed">
              · {note}
            </p>
          ))}
        </div>
      )}

      {/* Footer — data source + context */}
      <p className="font-mono text-[8px] text-muted-foreground/40 text-center leading-relaxed">
        {detectedPos ? `Posição: ${detectedPos} · ` : ''}{stackBb.toFixed(0)}bb
        {openerPos ? ` · opener: ${openerPos}` : ''}
        {' · '}Fonte: {apiData ? 'Nash MTT (local)' : 'tabelas estáticas'}
        {!showGtoCtx && gto && !gto.available && ' · análise GTO indisponível neste spot'}
      </p>
    </section>
  );
}
