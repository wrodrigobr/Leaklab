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
    const grid = ref.current;
    if (!grid || typeof ResizeObserver === "undefined") return;

    const apply = () => {
      const active = window.matchMedia(`(min-width:${minWidth}px)`).matches;
      for (const child of Array.from(grid.children) as HTMLElement[]) {
        if (!active) {
          child.style.gridRowEnd = "";
          continue;
        }
        // altura do CONTEÚDO (o grid é items-start → o filho não estica) + o gap visual.
        const h = child.getBoundingClientRect().height;
        const span = Math.max(1, Math.ceil((h + gap) / rowUnit));
        child.style.gridRowEnd = `span ${span}`;
      }
    };

    apply();
    // re-mede quando o conteúdo de qualquer card muda (dados carregam async) e no resize.
    const ro = new ResizeObserver(() => apply());
    for (const child of Array.from(grid.children)) ro.observe(child);
    window.addEventListener("resize", apply);
    // re-observa filhos novos/removidos
    const mo = new MutationObserver(() => {
      ro.disconnect();
      for (const child of Array.from(grid.children)) ro.observe(child);
      apply();
    });
    mo.observe(grid, { childList: true });

    return () => {
      ro.disconnect();
      mo.disconnect();
      window.removeEventListener("resize", apply);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
