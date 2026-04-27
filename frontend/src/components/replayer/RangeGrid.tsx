import { RANKS, cellHand, cellLabel, getCellAction, rangeStats, CellAction, RangeSet } from "@/data/ranges";
import { cn } from "@/lib/utils";

const ACTION_CLS: Record<CellAction, string> = {
  r:  'bg-emerald-500/80 text-emerald-50',
  c:  'bg-blue-500/80 text-blue-50',
  rc: 'bg-amber-500/80 text-amber-50',
  '': 'bg-muted/20 text-muted-foreground/30',
};

interface Props {
  range: RangeSet;
  heroHand?: string | null;
}

export function RangeGrid({ range, heroHand }: Props) {
  const { combos, pct } = rangeStats(range);

  return (
    <div className="space-y-1.5">
      <div
        className="grid gap-px"
        style={{ gridTemplateColumns: 'repeat(13, minmax(0, 1fr))' }}
      >
        {Array.from({ length: 13 }, (_, row) =>
          Array.from({ length: 13 }, (_, col) => {
            const hand    = cellHand(row, col);
            const label   = cellLabel(row, col);
            const action  = getCellAction(hand, range);
            const isHero  = heroHand === hand;
            return (
              <div
                key={`${row}-${col}`}
                title={hand}
                className={cn(
                  'aspect-square flex items-center justify-center rounded-[2px]',
                  'font-mono leading-none select-none transition-colors',
                  'text-[6px] sm:text-[7px]',
                  ACTION_CLS[action],
                  isHero && 'ring-2 ring-yellow-400 ring-offset-[1px] ring-offset-background relative z-10',
                )}
              >
                {label}
              </div>
            );
          })
        )}
      </div>

      <div className="flex items-center justify-between font-mono text-[9px] text-muted-foreground">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-[1px] bg-emerald-500" />Raise
          </span>
          {range.call && range.call.size > 0 && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px] bg-blue-500" />Call
            </span>
          )}
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-[1px] bg-muted/40 ring-1 ring-border" />Fold
          </span>
        </div>
        <span>{pct}% · {combos} combos</span>
      </div>

      <p className="font-mono text-[8px] text-muted-foreground/60 text-center">
        Superior-dir: suited · Inferior-esq: offsuit · Diagonal: pares
      </p>
    </div>
  );
}
