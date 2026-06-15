import { useTranslation } from "react-i18next";
import { verdictLevelOrError, VERDICT_META } from "@/lib/cardLogic";

/**
 * Tag de veredito em 3 níveis (Correto / Aceitável / Erro) — FEAT-20.
 * FONTE ÚNICA de cor/ícone/texto do veredito fora do card do replayer (painel do coach,
 * tabelas de decisões). Recebe a SEVERIDADE interna (`label`) e colapsa via
 * `verdictLevelOrError`; o texto vem de `common:verdict.<level>`. Espelha o card.
 */
export function VerdictTag({ label, className = "" }: { label: string | null | undefined; className?: string }) {
  const { t } = useTranslation("common");
  const m = VERDICT_META[verdictLevelOrError(label)];
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${m.chipCls} ${className}`}>
      <span aria-hidden>{m.icon}</span> {t(m.i18nKey)}
    </span>
  );
}
