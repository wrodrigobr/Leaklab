import { useState, useEffect } from "react";
import { LayoutGrid, X, Loader2 } from "lucide-react";
import { RangeGrid } from "./RangeGrid";
import {
  heroHand, RANGES, normalizePosition,
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

// API response shape
interface PreflopRangesResp {
  position: string;
  stack_bb: number;
  stack_bucket: string;
  rfi: { hands: string[]; pct: number } | null;
  vs_rfi: Record<string, { hands: string[]; raise3bet: string[]; call: string[]; pct_play: number; acoes: string[] }>;
  vs_3bet: { hands_4bet: string[]; hands_call: string[]; pct_continua: number } | null;
}

function buildRangeFromApi(resp: PreflopRangesResp, type: RangeType, openerPos?: string): RangeSet | null {
  if (type === 'open') {
    if (!resp.rfi) return null;
    return {
      label: `Open ${resp.position} (${resp.stack_bucket})`,
      description: `${(resp.rfi.pct * 100).toFixed(0)}% das mãos`,
      raise: new Set(resp.rfi.hands),
    };
  }
  if (type === '3bet') {
    if (!resp.vs_3bet) return null;
    return {
      label: `vs 3bet ${resp.position} (${resp.stack_bucket})`,
      description: `${(resp.vs_3bet.pct_continua * 100).toFixed(0)}% continuam`,
      raise: new Set(resp.vs_3bet.hands_4bet),
      call:  new Set(resp.vs_3bet.hands_call),
    };
  }
  if (type === 'call') {
    // pick the first available opener or the specified one
    const openers = Object.keys(resp.vs_rfi);
    if (!openers.length) return null;
    const key     = openerPos && resp.vs_rfi[openerPos] ? openerPos : openers[0];
    const def     = resp.vs_rfi[key];
    const acoes   = def.acoes.map(a => a.toUpperCase());
    const has3bet  = acoes.includes('THREBET') || acoes.includes('3BET');
    return {
      label: `vs ${key} open (${resp.stack_bucket})`,
      description: `${(def.pct_play * 100).toFixed(0)}% das mãos — ${def.acoes.join('/')}`,
      raise: new Set(has3bet ? def.hands : []),
      call:  new Set(has3bet ? [] : def.hands),
    };
  }
  return null;
}

export function RangePanel({ step, hero, heroCards, onClose, onHeaderMouseDown }: Props) {
  const heroSeat = Object.entries(step.seats ?? {}).find(([, s]) => s.player === hero);
  const detectedPos = heroSeat ? normalizePosition(heroSeat[1].pos) : null;

  const hasRaise = Object.entries(step.bets ?? {}).some(([seat, bet]) =>
    step.seats?.[seat]?.player !== hero && bet > (step.bb ?? 0)
  );

  const [pos,  setPos]  = useState<Position>(detectedPos ?? 'BTN');
  const [type, setType] = useState<RangeType>(hasRaise ? 'call' : 'open');

  const [apiData,  setApiData]  = useState<PreflopRangesResp | null>(null);
  const [loading,  setLoading]  = useState(false);

  const stackBb = step.hero_stack_bb ?? 30;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setApiData(null);
    authFetch(`/preflop-ranges?position=${pos}&stack_bb=${stackBb}`)
      .then(r => r.json())
      .then((d: PreflopRangesResp) => { if (!cancelled) setApiData(d); })
      .catch(() => {/* fall back to static data */})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pos, stackBb]);

  // Determine which types are available (api or static fallback)
  const staticRange   = RANGES[pos];
  const availableTypes = RANGE_TYPES.filter(t => {
    if (apiData) {
      if (t.id === 'open')  return !!apiData.rfi;
      if (t.id === '3bet')  return !!apiData.vs_3bet;
      if (t.id === 'call')  return Object.keys(apiData.vs_rfi).length > 0;
    }
    return staticRange?.[t.id] !== undefined;
  });

  const effectiveType: RangeType = availableTypes.some(t => t.id === type)
    ? type
    : (availableTypes[0]?.id ?? 'open');

  const displayRange: RangeSet | null | undefined = apiData
    ? buildRangeFromApi(apiData, effectiveType)
    : staticRange?.[effectiveType];

  const hand = heroHand(heroCards);

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
          {hand && (
            <span className="font-mono text-[10px] text-primary font-bold">· {hand}</span>
          )}
          {apiData && (
            <span className="font-mono text-[8px] text-emerald-400/70">{apiData.stack_bucket}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="size-3 text-muted-foreground animate-spin" />}
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Fechar"
          >
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Position selector */}
      <div
        className="grid gap-px rounded-md overflow-hidden ring-1 ring-border"
        style={{ gridTemplateColumns: `repeat(${POSITIONS.length}, minmax(0, 1fr))` }}
      >
        {POSITIONS.map(p => (
          <button
            key={p}
            onClick={() => setPos(p)}
            className={cn(
              'py-1 font-mono text-[9px] font-bold uppercase transition-colors',
              pos === p
                ? 'bg-primary/20 text-primary'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/30',
            )}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Range type selector */}
      <div
        className="grid gap-px rounded-md overflow-hidden ring-1 ring-border"
        style={{ gridTemplateColumns: `repeat(${availableTypes.length}, minmax(0, 1fr))` }}
      >
        {availableTypes.map(t => (
          <button
            key={t.id}
            onClick={() => setType(t.id)}
            className={cn(
              'py-1 font-mono text-[9px] font-bold uppercase transition-colors',
              effectiveType === t.id
                ? 'bg-primary/20 text-primary'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/30',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Range info */}
      {displayRange ? (
        <>
          {displayRange.description && (
            <p className="font-mono text-[9px] text-muted-foreground">{displayRange.description}</p>
          )}
          <RangeGrid range={displayRange} heroHand={hand} />
        </>
      ) : loading ? (
        <p className="text-xs text-muted-foreground text-center py-4 animate-pulse">
          Carregando ranges…
        </p>
      ) : (
        <p className="text-xs text-muted-foreground text-center py-4">
          Range não disponível para esta posição.
        </p>
      )}

      {detectedPos && (
        <p className="font-mono text-[8px] text-muted-foreground/60 text-center">
          Posição detectada: {detectedPos}{hasRaise ? ' · raise detectado' : ' · sem raise anterior'}
          {stackBb ? ` · ${stackBb.toFixed(0)}bb` : ''}
        </p>
      )}
    </section>
  );
}
