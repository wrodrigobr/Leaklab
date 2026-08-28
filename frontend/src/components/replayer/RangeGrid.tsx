import { cellHand, getHandFreq, rangeActionPresence, rangeStats, RangeSet } from "@/data/ranges";
import { HandCellLabel, CLASSE_FONTE_CELULA } from '@/components/HandCellLabel';
import { cn } from "@/lib/utils";
import { ACTION_COLORS } from "@/lib/actionColors";

/**
 * RangeGrid estilo solver — cada célula pode ter múltiplas cores
 * proporcionais à frequência de cada ação (raise / call / allin / fold).
 *
 * Layout: stripes verticais. Ex: 88 com 70% call + 30% raise → 70% da largura
 * azul + 30% verde. Folds = zinc-500 (distintivo do fundo).
 */

const COLORS = {
  raise: ACTION_COLORS.raise,
  call:  ACTION_COLORS.call,
  allin: ACTION_COLORS.allin,
  fold:  ACTION_COLORS.fold,
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
  // A constante, nao o literal: ate 27/08 `COLORS.fold` era atribuido acima e NUNCA lido,
  // enquanto a celula pintava um rgba cravado. Duas fontes para a cor da mesma acao.
  if (foldPct > 0.001) segs.push([COLORS.fold, foldPct]);

  if (segs.length === 0) return COLORS.fold;
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
  const present = rangeActionPresence(range);

  return (
    <div className="space-y-1.5">
      <div
        className="grid gap-px"
        style={{ gridTemplateColumns: 'repeat(13, minmax(0, 1fr))' }}
      >
        {Array.from({ length: 13 }, (_, row) =>
          Array.from({ length: 13 }, (_, col) => {
            const hand    = cellHand(row, col);

            const isHero  = heroHand === hand;
            const gradient = buildGradient(hand, range);
            const txtColor = textColor(hand, range);
            // Tooltip mostra freq por ação
            const f = getHandFreq(hand, range);
            const tipParts: string[] = [];
            if (f.raise && f.raise > 0.001) tipParts.push(`Raise ${(f.raise*100).toFixed(0)}%`);
            if (f.call  && f.call  > 0.001) tipParts.push(`Call ${(f.call*100).toFixed(0)}%`);
            if (f.allin && f.allin > 0.001) tipParts.push(`Shove ${(f.allin*100).toFixed(0)}%`);
            const totalActive = tipParts.length ? ((f.raise ?? 0) + (f.call ?? 0) + (f.allin ?? 0)) : 0;
            if (totalActive < 0.999) tipParts.push(`Fold ${((1-totalActive)*100).toFixed(0)}%`);
            const tooltip = `${hand}: ${tipParts.join(' · ')}`;
            return (
              <div
                key={`${row}-${col}`}
                title={tooltip}
                className={cn(
                  'aspect-square flex items-center justify-center rounded-[2px]',
                  'font-mono leading-none select-none transition-colors',
                  CLASSE_FONTE_CELULA,
                  // Contorno na diagonal: separa visualmente os dois triângulos. Sem isto, saber
                  // se uma célula é suited ou offsuit dependia de contar a distância até a
                  // diagonal, que ninguém faz olhando.
                  row === col && 'ring-1 ring-inset ring-white/25',
                  isHero && 'ring-2 ring-yellow-400 ring-offset-[1px] ring-offset-background relative z-10',
                )}
                style={{ background: gradient, color: txtColor }}
              >
                <HandCellLabel row={row} col={col} hand={hand} />
              </div>
            );
          })
        )}
      </div>

      {/* Legenda — deriva das ações REALMENTE pintadas na grade (rangeActionPresence, mesma
          fonte do gradiente). Antes olhava os Sets, que na aba OPEN não trazem `allin`: em
          push/fold a grade ficava toda vermelha sem legenda de Shove. */}
      <div className="flex items-center justify-between font-mono text-[9px] text-muted-foreground">
        <div className="flex items-center gap-3 flex-wrap">
          {present.raise && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.raise }} />Raise
            </span>
          )}
          {present.call && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.call }} />Call
            </span>
          )}
          {present.allin && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.allin }} />Shove
            </span>
          )}
          {present.fold && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2 rounded-[1px]" style={{ background: COLORS.fold, border: '1px solid #71717a' }} />Fold
            </span>
          )}
        </div>
        <span>{pct}% · {combos} combos</span>
      </div>

      {/* Legenda de LEITURA da grade, não de cores.
          Era 8px a 60% de opacidade, e carregava sozinha a única indicação de suited × offsuit.
          Agora a célula se descreve, então esta linha volta a ser o que deveria: um lembrete da
          geometria, legível. */}
      <p className="font-mono text-[10px] leading-relaxed text-muted-foreground text-center">
        <span className="text-foreground">s</span> = suited (acima da diagonal) ·{' '}
        <span className="text-foreground">o</span> = offsuit (abaixo) ·{' '}
        diagonal = pares
      </p>
    </div>
  );
}
