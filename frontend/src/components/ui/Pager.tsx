import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";

/** Paginação client-side simples: setas + "página / total". Some quando há só 1 página.
 *  Texto visível é só número (neutro); aria-labels via i18n (namespace common). */
export function Pager({ page, pageCount, onPage, className = "" }: {
  page: number;
  pageCount: number;
  onPage: (p: number) => void;
  className?: string;
}) {
  const { t } = useTranslation("common");
  if (pageCount <= 1) return null;
  const btn =
    "inline-flex size-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-40 disabled:pointer-events-none";
  return (
    <div className={`flex items-center justify-center gap-2 py-4 ${className}`}>
      <button
        type="button"
        onClick={() => onPage(Math.max(1, page - 1))}
        disabled={page <= 1}
        aria-label={t("pagination.prev")}
        className={btn}
      >
        <ChevronLeft className="size-4" />
      </button>
      <span className="min-w-[3.5rem] text-center font-mono text-xs tabular-nums text-muted-foreground">
        {page} / {pageCount}
      </span>
      <button
        type="button"
        onClick={() => onPage(Math.min(pageCount, page + 1))}
        disabled={page >= pageCount}
        aria-label={t("pagination.next")}
        className={btn}
      >
        <ChevronRight className="size-4" />
      </button>
    </div>
  );
}
