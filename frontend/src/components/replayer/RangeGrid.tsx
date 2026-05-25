import { cellHand, cellLabel, getHandFreq, rangeStats, RangeSet } from "@/data/ranges";
import { cn } from "@/lib/utils";

/**
 * RangeGrid estilo GTO Wizard — cada célula pode ter múltiplas cores
 * proporcionais à frequência de cada ação (raise / call / allin / fold).
 *
 * Layout: stripes verticais. Ex: 88 com 70% call + 30% raise → 70% da largura
 * azul + 30% verde. Folds = sem cor (cinza claro).
 */

// Cores por ação — alinhadas com convenções GW (vermelho=allin, verde=raise, azul=call)
const COLORS = {
  raise: '#10b981', // emerald-500
  call:  '#3b82f6', // blue-500
  allin: '#ef4444', // red-500
  fold:  'transparent',
} as const;

interface Props {
  range: RangeSet;
  heroHand?: string | null;
}

function buildGradient(hand: string, range: RangeSet): string {
  const f = getHandFreq(hand, range);
  const segs: Array<[string, number]> = [];
  if (f.raise && f.raise > 0.001) segs.push([COLORS.raise, f.raise]);
  if (f.call  && f.call  > 0.001) segs.push([COLORS.call,  f.call]);
  if (f.allin && f.allin > 0.001) segs.push([COLORS.allin, f.allin]);
  const totalActive = segs.reduce((a, [, v]) => a + v, 0);
  const foldPct = Math.max(0, 1 - totalActive);
  if (foldPct > 0.001) segs.push(['rgba(120,120,120,0.10)', foldPct]); // cinza claro pra fold

  if (segs.length === 0) return 'rgba(120,120,120,0.10)';
  if (segs.length === 1) return segs[0][0];

  // Linear gradient horizontal — stripes proporcionais
  let acc = 0;
  const parts: string[] = [];
  for (const [color, pct] of segs) {
    const start = acc * 100;
    acc += pct;
    const end = acc * 100;
    parts.push(`${color} ${start.toFixed(1)}% ${end.toFixed(1)}%`);
  }
  return `linear-gradient(to right, ${parts.join(', ')})`;
}

function textColor(hand: string, range: RangeSet): string {
  const f = getHandFreq(hand, range);
  const active = (f.raise ?? 0) + (f.call ?? 0) + (f.allin ?? 0);
  // Cells coloridas (>30% ativa): texto branco. Cells brancas: cinza claro.
  return active > 0.3 ? 'rgba(255,255,255,0.95)' : 'rgba(120,120,120,0.5)';
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
            const isHero  = heroHand === hand;
            const gradient = buildGradient(hand, range);
            const txtColor = textColor(hand, range);
            // Tooltip mostra freq por ação
            const f = getHandFreq(hand, range);
            const tipParts: string[] = [];
            if (f.raise && f.raise > 0.001) tipParts.push(`Raise ${(f.raise*100).toFixed(0)}%`);
            if (f.call  && f.call  > 0.001) tipParts.push(`Call ${(f.call*100).toFixed(0)}%`);
            if (f.allin && f.allin > 0.001) tipParts.push(`Allin ${(f.allin*100).toFixed(0)}%`);
            const totalActive = tipParts.length ? ((f.raise ?? 0) + (f.call ?? 0) + (f.allin ?? 0)) : 0;
            if (totalActive < 0.999) tipParts.push(`Fold ${((1-totalActive)*100).toFixed(0)}%`);
            const tooltip = `${hand} — ${tipParts.join(' · ')}`;
            return (
              <div
                key={`${row}-${col}`}
                title={tooltip}
                className={cn(
                  'aspect-square flex items-center justify-center rounded-[2px]',
                  'font-mono leading-none select-none transition-colors',
                  'text-[6px] sm:text-[7px]',
                  isHero && 'ring-2 ring-yellow-400 ring-offset-[1px] ring-offset-background relative z-10',
                )}
                style={{ background: gradient, color: txtColor }}
              >
                {label}
              </div>
            );
          })
        )}
      </div>

      {/* Legenda: cada ação com cor + % global */}
      <div className="flex items-center justify-between font-mono text-[9px] text-muted-foreground">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.raise }} />Raise
          </span>
          {range.call && range.call.size > 0 && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.call }} />Call
            </span>
          )}
          {range.allin && range.allin.size > 0 && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.allin }} />Allin
            </span>
          )}
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-[1px]" style={{ background: 'rgba(120,120,120,0.10)', border: '1px solid rgba(120,120,120,0.3)' }} />Fold
          </span>
        </div>
        <span>{pct}% · {combos} combos</span>
      </div>

      <p className="font-mono text-[8px] text-muted-foreground/60 text-center">
        Superior-dir: suited · Inferior-esq: offsuit · Diagonal: pares · Hover na célula vê freq por ação
      </p>
    </div>
  );
}
