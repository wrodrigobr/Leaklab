import { useTranslation } from "react-i18next";
import { ChevronRight } from "lucide-react";
import { VERDICT_META, type VerdictLevel } from "@/lib/cardLogic";
import { cn } from "@/lib/utils";

/**
 * VerdictPill — barra de veredito compacta do Replayer mobile (UX-2 mobile, passo 2).
 * Mostra o veredito de 3 níveis (Correto/Aceitável/Erro) + EV-loss e abre o card de
 * análise (bottom-sheet). Consome a FONTE ÚNICA do veredito (VERDICT_META do cardLogic) —
 * ícone, cor e chip vêm de lá, nunca recriados inline. Veja project_verdict_3levels.
 */
const LABEL_KEY: Record<VerdictLevel, string> = {
  correct: "card.vCorrect",
  acceptable: "card.vAcceptable",
  error: "card.vError",
};

export function VerdictPill({
  level,
  evLossBb,
  onClick,
  desktop = false,
}: {
  level: VerdictLevel | null;
  evLossBb?: number | null;
  onClick: () => void;
  /** Quando true, o pill fica visível no desktop (lg+) em vez de oculto. */
  desktop?: boolean;
}) {
  const { t } = useTranslation("replayer");
  // Sem veredito (passo sem ação do hero) → nenhum botão: abriria um card vazio.
  if (!level) return null;
  const meta = VERDICT_META[level];
  // EV-loss só faz sentido quando há perda (aceitável/erro); em "correto" é ~0.
  const showEv = (level === "error" || level === "acceptable") && evLossBb != null && evLossBb > 0;

  return (
    <button
      onClick={onClick}
      aria-label={t(LABEL_KEY[level])}
      className={cn(
        "group inline-flex items-center gap-2 rounded-full bg-hud-surface/90 px-3 py-2 shadow-lg ring-1 backdrop-blur-sm transition-all hover:bg-hud-surface active:scale-[0.97]",
        desktop ? "" : "lg:hidden",
        meta.ringCls,
      )}
    >
      <span className={cn("text-[15px] leading-none", meta.textCls)}>{meta.icon}</span>
      <span className={cn("font-mono text-[12px] font-bold uppercase tracking-wide", meta.textCls)}>{t(LABEL_KEY[level])}</span>
      {showEv && (
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground/80">−{evLossBb!.toFixed(1)}bb</span>
      )}
      <span className="ml-0.5 flex items-center gap-0.5 border-l border-white/10 pl-2 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
        {t("details")}
        <ChevronRight className="size-3 transition-transform group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}
