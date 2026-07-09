import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Constrói a lista de páginas com janela deslizante + reticências. Sempre inclui a 1ª e a
 *  última; mostra `siblings` páginas de cada lado da atual. Ex.: 1 … 4 5 [6] 7 8 … 20. */
function pageItems(page: number, pageCount: number, siblings = 1): (number | "…")[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);
  const left = Math.max(2, page - siblings);
  const right = Math.min(pageCount - 1, page + siblings);
  const items: (number | "…")[] = [1];
  if (left > 2) items.push("…");
  for (let i = left; i <= right; i++) items.push(i);
  if (right < pageCount - 1) items.push("…");
  items.push(pageCount);
  return items;
}

/** Paginação client-side: setas prev/próximo + números com reticências. Sempre mostra a 1ª e a
 *  última página (jump ao fim = clicar no último número). Some quando há só 1 página. */
export function Pager({ page, pageCount, onPage, className = "" }: {
  page: number;
  pageCount: number;
  onPage: (p: number) => void;
  className?: string;
}) {
  const { t } = useTranslation("common");
  if (pageCount <= 1) return null;

  const arrow =
    "inline-flex size-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-40 disabled:pointer-events-none";
  const numBtn =
    "inline-flex h-8 min-w-[2rem] items-center justify-center rounded-md border px-2 font-mono text-xs tabular-nums transition-colors";

  return (
    <div className={`flex flex-wrap items-center justify-center gap-1.5 py-4 ${className}`}>
      <button
        type="button"
        onClick={() => onPage(Math.max(1, page - 1))}
        disabled={page <= 1}
        aria-label={t("pagination.prev")}
        className={arrow}
      >
        <ChevronLeft className="size-4" />
      </button>

      {pageItems(page, pageCount).map((it, i) =>
        it === "…" ? (
          <span key={`e${i}`} className="px-1 font-mono text-xs text-muted-foreground/60" aria-hidden>
            …
          </span>
        ) : (
          <button
            key={it}
            type="button"
            onClick={() => onPage(it)}
            aria-current={it === page ? "page" : undefined}
            className={cn(
              numBtn,
              it === page
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-secondary hover:text-foreground",
            )}
          >
            {it}
          </button>
        ),
      )}

      <button
        type="button"
        onClick={() => onPage(Math.min(pageCount, page + 1))}
        disabled={page >= pageCount}
        aria-label={t("pagination.next")}
        className={arrow}
      >
        <ChevronRight className="size-4" />
      </button>
    </div>
  );
}
