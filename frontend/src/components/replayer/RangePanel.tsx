import { useState } from "react";
import { LayoutGrid, X } from "lucide-react";
import { RangeGrid } from "./RangeGrid";
import {
  heroHand, RANGES, normalizePosition,
  Position, RangeType, POSITIONS, RANGE_TYPES,
} from "@/data/ranges";
import { ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  step: ReplayStep;
  hero: string;
  heroCards: string[];
  onClose: () => void;
}

export function RangePanel({ step, hero, heroCards, onClose }: Props) {
  const heroSeat = Object.entries(step.seats ?? {}).find(([, s]) => s.player === hero);
  const detectedPos = heroSeat ? normalizePosition(heroSeat[1].pos) : null;

  const hasRaise = Object.entries(step.bets ?? {}).some(([seat, bet]) =>
    step.seats?.[seat]?.player !== hero && bet > (step.bb ?? 0)
  );

  const [pos,  setPos]  = useState<Position>(detectedPos ?? 'BTN');
  const [type, setType] = useState<RangeType>(hasRaise ? 'call' : 'open');

  const range         = RANGES[pos]?.[type];
  const hand          = heroHand(heroCards);
  const availableTypes = RANGE_TYPES.filter(t => RANGES[pos]?.[t.id] !== undefined);

  // If current type not available for new position, fall back to first available
  const effectiveType = availableTypes.some(t => t.id === type)
    ? type
    : (availableTypes[0]?.id ?? 'open');

  const displayRange = RANGES[pos]?.[effectiveType];

  return (
    <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LayoutGrid className="size-3.5 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-foreground">
            Range Reference
          </span>
          {hand && (
            <span className="font-mono text-[10px] text-primary font-bold">· {hand}</span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Fechar"
        >
          <X className="size-3.5" />
        </button>
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
      ) : (
        <p className="text-xs text-muted-foreground text-center py-4">
          Range não disponível para esta posição.
        </p>
      )}

      {detectedPos && (
        <p className="font-mono text-[8px] text-muted-foreground/60 text-center">
          Posição detectada: {detectedPos}{hasRaise ? ' · raise detectado' : ' · sem raise anterior'}
        </p>
      )}
    </section>
  );
}
