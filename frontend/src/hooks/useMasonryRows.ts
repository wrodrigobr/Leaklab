import { useEffect } from "react";

/**
 * Masonry real para um CSS grid: mede a altura de cada filho direto e seta
 * `grid-row-end: span N` (N = altura / rowUnit) para os cards "altos" ocuparem mais
 * linhas e os "curtos" liberarem o espaço vertical — o `grid-flow-dense` então empacota,
 * eliminando os vãos que o grid normal (auto-rows: auto) deixa quando um card curto fica
 * ao lado de um alto.
 *
 * Requer no grid (só no breakpoint ativo): `auto-rows-[{rowUnit}px]`, `gap-y-0`,
 * `items-start` e `grid-flow-dense`. Abaixo de `minWidth` o masonry é desligado (volta ao
 * fluxo normal 1-col/2-col com gap-y do CSS).
 */
export function useMasonryRows(
  ref: React.RefObject<HTMLElement | null>,
  deps: unknown[] = [],
  opts: { rowUnit?: number; gap?: number; minWidth?: number } = {},
) {
  const { rowUnit = 8, gap = 24, minWidth = 1024 } = opts;

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;

    let timer = 0;
    let observed: HTMLElement | null = null;
    let ro: ResizeObserver | null = null;
    let mo: MutationObserver | null = null;

    // SEMPRE lê ref.current (nunca um closure de nó): o React pode SUBSTITUIR o
    // elemento da grade (remount atrás de loading) e um apply preso no nó antigo
    // escreveria spans num DOM morto.
    const apply = () => {
      const grid = ref.current;
      if (!grid) return;
      const active = window.matchMedia(`(min-width:${minWidth}px)`).matches;
      for (const child of Array.from(grid.children) as HTMLElement[]) {
        if (!active) {
          if (child.style.gridRowEnd) child.style.gridRowEnd = "";
          continue;
        }
        // altura do CONTEÚDO (o grid é items-start → o filho não estica) + o gap visual.
        const h = child.getBoundingClientRect().height;
        const span = `span ${Math.max(1, Math.ceil((h + gap) / rowUnit))}`;
        if (child.style.gridRowEnd !== span) child.style.gridRowEnd = span;  // só escreve se mudou
      }
    };

    // Debounce por setTimeout, NÃO requestAnimationFrame: rAF não dispara em páginas
    // em segundo plano/sem foco (webviews, abas ocultas) — um masonry agendado só por
    // rAF fica congelado nesses ambientes. setTimeout sempre dispara.
    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(apply, 50);
    };

    const attach = (grid: HTMLElement) => {
      ro?.disconnect();
      mo?.disconnect();
      ro = new ResizeObserver(schedule);
      for (const child of Array.from(grid.children)) ro.observe(child);
      // re-observa filhos novos/removidos E mudanças profundas (subtree): um card que
      // renderiza null e depois monta o conteúdo (ex.: chart com useQuery) não dispara
      // o RO de forma confiável — a mutação de subtree garante a re-medição.
      mo = new MutationObserver(() => {
        ro?.disconnect();
        for (const child of Array.from(grid.children)) ro?.observe(child);
        schedule();
      });
      mo.observe(grid, { childList: true, subtree: true });
      observed = grid;
      apply();   // síncrono: o primeiro layout não espera o debounce
    };

    // Guard de correção: pega (1) grid que monta DEPOIS do effect (ex.: atrás de um
    // loading com deps que nunca mais mudam — clássico, deps=[sections]) e (2) nó
    // substituído pelo React (observers órfãos). Barato: apply só escreve se mudou.
    const tick = window.setInterval(() => {
      const grid = ref.current;
      if (grid && grid !== observed) attach(grid);
      else if (grid) schedule();
    }, 600);

    if (ref.current) attach(ref.current);
    window.addEventListener("resize", schedule);

    return () => {
      window.clearInterval(tick);
      window.clearTimeout(timer);
      ro?.disconnect();
      mo?.disconnect();
      window.removeEventListener("resize", schedule);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
