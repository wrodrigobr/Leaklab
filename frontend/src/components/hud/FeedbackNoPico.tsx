import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";

import { support } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Feedback no PICO: uma linha "isso te ajudou?" nos dois momentos de maior engajamento.
 *
 * ── O que originou (30/08) ────────────────────────────────────────────────────────────────
 *
 * O canal de feedback global (FAB) existe desde agosto e a medição do programa de fundadores
 * mostrou ZERO uso. O problema não é falta de formulário — é o MOMENTO do pedido: ninguém
 * abre um FAB genérico para elogiar, mas responde um toque no fim de algo que acabou de usar.
 *
 * ── As regras ─────────────────────────────────────────────────────────────────────────────
 *
 * 1. Um toque responde (👍/👎). O texto é opcional e só aparece DEPOIS do toque — pedir texto
 *    antes é pedir demais no pico.
 * 2. Vai para o MESMO canal do FAB (`support.contact` → support_tickets): nenhuma segunda
 *    fonte de feedback para o admin olhar.
 * 3. `contexto` viaja no assunto ("boletim", "analise-ia") — sem ele o admin lê "👍" solto.
 * 4. Nunca bloqueia nem re-pergunta: respondeu, vira "obrigado" e some na próxima render.
 */

interface Props {
  /** de onde veio o feedback — vai no assunto do ticket */
  contexto: string;
  className?: string;
}

export function FeedbackNoPico({ contexto, className }: Props) {
  const { t } = useTranslation("common");
  const [voto, setVoto] = useState<"up" | "down" | null>(null);
  const [texto, setTexto] = useState("");
  const [enviado, setEnviado] = useState(false);

  const enviar = async (v: "up" | "down", detalhe?: string) => {
    try {
      await support.contact({
        category: v === "up" ? "praise" : "problem",
        subject: `Feedback rápido · ${contexto} · ${v === "up" ? "👍" : "👎"}`,
        message: (detalhe || "").trim() || (v === "up" ? "+1" : "-1"),
      });
    } catch {
      // falha calada de propósito: feedback nunca vira erro na cara de quem acabou de treinar
    }
  };

  const tocar = (v: "up" | "down") => {
    setVoto(v);
    // O toque já conta sozinho; o texto, se vier, gera um segundo ticket com o detalhe.
    void enviar(v);
  };

  const complementar = async () => {
    if (!texto.trim() || !voto) return;
    await enviar(voto, texto);
    setEnviado(true);
  };

  if (enviado) {
    return (
      <p className={cn("flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground", className)}>
        <Check className="size-3 text-primary" aria-hidden /> {t("feedbackPico.obrigado")}
      </p>
    );
  }

  return (
    <div className={cn("flex flex-col items-center gap-1.5", className)}>
      {voto === null ? (
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground">{t("feedbackPico.pergunta")}</span>
          <button type="button" onClick={() => tocar("up")} aria-label={t("feedbackPico.sim")}
                  className="rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary">
            <ThumbsUp className="size-3.5" aria-hidden />
          </button>
          <button type="button" onClick={() => tocar("down")} aria-label={t("feedbackPico.nao")}
                  className="rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:border-destructive/50 hover:text-destructive">
            <ThumbsDown className="size-3.5" aria-hidden />
          </button>
        </div>
      ) : (
        <div className="flex w-full max-w-xs items-center gap-1.5">
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value.slice(0, 500))}
            onKeyDown={(e) => { if (e.key === "Enter") void complementar(); }}
            placeholder={t(voto === "up" ? "feedbackPico.detalheBom" : "feedbackPico.detalheRuim")}
            className="min-w-0 flex-1 rounded-lg border border-border bg-background/50 px-2.5 py-1.5 text-[12px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <button type="button" onClick={() => void complementar()}
                  disabled={!texto.trim()}
                  className="rounded-lg bg-primary px-2.5 py-1.5 font-mono text-[10px] font-bold uppercase text-primary-foreground disabled:opacity-40">
            {t("feedbackPico.enviar")}
          </button>
          <button type="button" onClick={() => setEnviado(true)}
                  className="font-mono text-[10px] uppercase text-muted-foreground hover:text-foreground">
            {t("feedbackPico.pular")}
          </button>
        </div>
      )}
    </div>
  );
}
