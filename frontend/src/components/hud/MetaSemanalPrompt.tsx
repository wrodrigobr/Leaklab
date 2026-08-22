import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { CalendarCheck } from "lucide-react";
import { proximoPasso } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * A pergunta única do compromisso (spec cobranca-proximo-passo.md §6, Fase 3).
 *
 * Perguntada UMA vez, no primeiro acesso ao trainer. A partir daí a cobrança deixa de ser contra
 * um ideal nosso e passa a ser contra o compromisso dele: "você prometeu 3, treinou em 1". Não é
 * o app cobrando, é o espelho — e essa diferença é psicológica, não semântica.
 *
 * ── Em DIAS, e não em sessões ─────────────────────────────────────────────────────────────────
 *
 * A spec pedia "sessões por semana". `progression_attempts` não tem identidade de sessão, só
 * carimbos de tempo, então perguntar em sessões e contar dias seria devolver um número que não
 * responde à pergunta feita. Dia também é a unidade melhor: 3 sessões numa terça e nada no resto
 * da semana é pior que 3 dias espalhados, que é a mesma tese do SRS.
 *
 * ── Três opções, e uma saída ──────────────────────────────────────────────────────────────────
 *
 * Mais que três vira formulário, e formulário ninguém responde. "Depois" existe porque forçar a
 * resposta para entrar no treino transformaria a primeira tela numa cobrança, que é exatamente o
 * oposto do que a Fase 3 quer.
 */
export function MetaSemanalPrompt({ onPular }: { onPular: () => void }) {
  const { t } = useTranslation("academy");
  const qc = useQueryClient();
  const [enviando, setEnviando] = useState<number | null>(null);

  const escolher = async (dias: number) => {
    setEnviando(dias);
    try {
      await proximoPasso.definirMeta(dias);
      // A faixa do dashboard e o próprio trainer leem do mesmo cache; sem invalidar, o aluno
      // responde e a tela segue perguntando.
      qc.invalidateQueries({ queryKey: ["proximo-passo"] });
      onPular();
    } finally {
      setEnviando(null);
    }
  };

  return (
    <div className="rounded-xl border border-sky-500/30 bg-sky-500/[0.05] p-4">
      <div className="flex items-start gap-2.5">
        <CalendarCheck className="mt-0.5 size-4 shrink-0 text-sky-400" aria-hidden />
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-sky-400">
            {t("leakTrainer.meta.eyebrow")}
          </p>
          <p className="mt-1 text-[13px] leading-snug text-foreground">
            {t("leakTrainer.meta.pergunta")}
          </p>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
            {t("leakTrainer.meta.porque")}
          </p>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2">
        {[2, 3, 5].map((d) => (
          <button key={d} onClick={() => escolher(d)} disabled={enviando !== null}
            className={cn(
              "flex-1 rounded-lg border border-border bg-background/60 px-3 py-2.5 font-mono text-sm font-bold text-foreground transition-colors",
              "hover:border-sky-500/60 hover:text-sky-300 disabled:opacity-40",
              enviando === d && "border-sky-500/60 text-sky-300",
            )}>
            {d}
          </button>
        ))}
        <button onClick={onPular} disabled={enviando !== null}
          className="shrink-0 px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40">
          {t("leakTrainer.meta.depois")}
        </button>
      </div>
    </div>
  );
}
