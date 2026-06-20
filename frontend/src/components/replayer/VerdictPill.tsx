import { useTranslation } from "react-i18next";
import { ChevronRight, Eye } from "lucide-react";
import { VERDICT_META, type VerdictLevel } from "@/lib/cardLogic";
import { cn } from "@/lib/utils";

/**
 * VerdictPill — barra de veredito compacta do Replayer mobile (UX-2 mobile, passo 2).
 * Mostra o veredito de 3 níveis (Correto/Aceitável/Erro) + EV-loss e abre o card de
 * análise (bottom-sheet). Consome a FONTE ÚNICA do veredito (VERDICT_META do cardLogic) —
 * ícone, cor e chip vêm de lá, nunca recriados inline. Veja project_verdict_3levels.
 */
const LABEL_KEY: Record<VerdictLevel, string> = {
  correct: "vCorrect",
  acceptable: "vAcceptable",
  error: "vError",
};

export function VerdictPill({
  level,
  evLossBb,
  onClick,
}: {
  level: VerdictLevel | null;
  evLossBb?: number | null;
  onClick: () => void;
}) {
  const { t } = useTranslation("replayer");
  const meta = level ? VERDICT_META[level] : null;
  // EV-loss só faz sentido quando há perda (aceitável/erro); em "correto" é ~0.
  const showEv = (level === "error" || level === "acceptable") && evLossBb != null && evLossBb > 0;

  return (
    <button
      onClick={onClick}
      aria-label={level ? t(LABEL_KEY[level]) : t("analysis")}
      className={cn(
        "lg:hidden shrink-0 flex items-center justify-between gap-2 rounded-xl border border-transparent px-3 py-2.5 font-mono text-[12px] font-bold uppercase tracking-wider transition-colors",
        meta ? meta.chipCls : "border-border bg-hud-surface text-muted-foreground hover:text-foreground",
      )}
    >
      <span className="flex items-center gap-1.5">
        {meta ? <span className="text-sm leading-none">{meta.icon}</span> : <Eye className="size-3.5" />}
        {level ? t(LABEL_KEY[level]) : t("analysis")}
      </span>
      <span className="flex items-center gap-2 text-[11px] font-normal">
        {showEv && <span className="tabular-nums opacity-80">−{evLossBb!.toFixed(1)} bb</span>}
        <ChevronRight className="size-3.5 opacity-60" />
      </span>
    </button>
  );
}
