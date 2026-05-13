import { useState, useEffect } from "react";
import { LayoutGrid, X, Loader2, CheckCircle2, XCircle, AlertTriangle, Info } from "lucide-react";
import { RangeGrid } from "./RangeGrid";
import {
  heroHand, RANGES, normalizePosition, PUSH_FOLD, getPushFoldBucket,
  Position, RangeType, POSITIONS, RANGE_TYPES, RangeSet,
} from "@/data/ranges";
import { ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000";

function authFetch(path: string): Promise<Response> {
  const t = sessionStorage.getItem("ll_token");
  return fetch(`${API_BASE}${path}`, {
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

interface PreflopRangesResp {
  position: string;
  stack_bb: number;
  stack_bucket: string;
  rfi: { hands: string[]; pct: number } | null;
  vs_rfi: Record<string, { hands: string[]; raise3bet: string[]; call: string[]; pct_play: number; acoes: string[] }>;
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
      description: `Top ${(resp.rfi.pct * 100).toFixed(0)}% das mãos`,
      raise: new Set(resp.rfi.hands),
    };
  }
  if (type === '3bet') {
    if (!resp.vs_3bet) return null;
    return {
      label: `vs 3-Bet ${resp.position} (${resp.stack_bucket})`,
      description: `${(resp.vs_3bet.pct_continua * 100).toFixed(0)}% continuam — Verde: 4-bet · Azul: call`,
      raise: new Set(resp.vs_3bet.hands_4bet),
      call:  new Set(resp.vs_3bet.hands_call),
    };
  }
  if (type === 'call') {
    const openers = Object.keys(resp.vs_rfi);
    if (!openers.length) return null;
    const key   = openerPos && resp.vs_rfi[openerPos] ? openerPos : openers[0];
    const def   = resp.vs_rfi[key];
    const acoes = def.acoes.map(a => a.toUpperCase());
    const sbOnly = acoes.includes('THREBET') && !acoes.includes('CALL');
    return {
      label: `vs ${key} open · ${resp.position} (${resp.stack_bucket})`,
      description: sbOnly
        ? `${(def.pct_play * 100).toFixed(0)}% das mãos — Verde: 3-bet ou fold (sem call)`
        : `${(def.pct_play * 100).toFixed(0)}% das mãos — Azul: continuar (GTO mistura 3-bet/call)`,
      raise: new Set(sbOnly ? def.hands : []),
      call:  new Set(sbOnly ? [] : def.hands),
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

  // Default to 'shove' in push/fold zone; otherwise auto-select from GTO/raise context
  const defaultType: RangeType = isPushZone
    ? 'shove'
    : (gto?.scenario ? (SCENARIO_TO_TYPE[gto.scenario] ?? 'open')
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
    if (t.id === 'shove') return isPushZone && !!nashRange;
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

  // Show GTO context only when viewing hero's detected position
  const showGtoCtx = gto?.available && pos === detectedPos;
  const quality    = showGtoCtx ? QUALITY_META[gto!.action_quality ?? 'unknown'] : null;
  const QIcon      = quality?.icon ?? Info;

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
          gto.in_range ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
        )}>
          {/* Scenario */}
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide">
            Cenário: {SCENARIO_LABEL[gto.scenario] ?? gto.scenario}
          </p>

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
        </div>
      )}

      {/* Push/Fold zone banner */}
      {isPushZone && effectiveType === 'shove' && (
        <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 px-3 py-2 space-y-1">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[9px] font-bold uppercase tracking-wide text-violet-400">
              Push/Fold Zone · {stackBb.toFixed(0)}bb
            </span>
            {pos === 'BB' && (
              <span className="font-mono text-[8px] text-muted-foreground">(call vs shove)</span>
            )}
          </div>
          <p className="font-mono text-[9px] text-muted-foreground leading-relaxed">
            {pos === 'BB'
              ? 'Verde = call · Fold o resto. Sem call no SB, re-raise é shove.'
              : 'Verde = shove all-in · Fold o resto. Sem open pequeno nessa profundidade.'}
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

      {/* Range grid */}
      {displayRange ? (
        <>
          {displayRange.description && (
            <p className="font-mono text-[9px] text-muted-foreground">{displayRange.description}</p>
          )}
          <RangeGrid range={displayRange} heroHand={hand} />
        </>
      ) : loading ? (
        <p className="text-xs text-muted-foreground text-center py-4 animate-pulse">Carregando ranges…</p>
      ) : (
        <p className="text-xs text-muted-foreground text-center py-4">Range não disponível para esta posição.</p>
      )}

      {/* Pro notes */}
      {showGtoCtx && gto?.pro_notes && gto.pro_notes.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 px-3 py-2 space-y-1">
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide mb-1.5">Análise GTO</p>
          {gto.pro_notes.map((note, i) => (
            <p key={i} className="font-mono text-[9px] text-foreground/80 leading-relaxed">
              · {note}
            </p>
          ))}
        </div>
      )}

      {/* Footer */}
      {detectedPos && (
        <p className="font-mono text-[8px] text-muted-foreground/50 text-center">
          Posição: {detectedPos} · {stackBb.toFixed(0)}bb{openerPos ? ` · opener: ${openerPos}` : ''}
        </p>
      )}
    </section>
  );
}
