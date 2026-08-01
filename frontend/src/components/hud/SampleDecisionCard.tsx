import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { SidePanels } from "@/components/replayer/SidePanels";
import { sample, type ReplayData, type ReplayStep } from "@/lib/api";

/**
 * Decisão de EXEMPLO para quem ainda não subiu arquivo nenhum (landing e dashboard vazio).
 *
 * O que havia aqui era um card escrito à mão: equity 34% contra 42%, uma frase, e nada da
 * evidência que a análise de verdade produz — nem range de defesa, nem cenário, nem como o GTO
 * joga a mão, nem ICM. Quem via aquilo não via o produto, via uma maquete dele.
 *
 * Agora são duas coisas reais ao mesmo tempo:
 *   • o DADO vem de uma mão jogada, analisada pela pipeline do `/replay` e congelada pelo
 *     backend (`GET /sample/decision`);
 *   • a VITRINE é o mesmo `SidePanels` que renderiza a análise no Replayer, não uma cópia.
 *
 * A segunda parte é a que envelhece bem. Uma cópia da apresentação passa a mentir sozinha no dia
 * em que o card real muda, e ninguém percebe porque nada quebra.
 *
 * Falha em silêncio de propósito: sem exemplo, não renderiza nada. É vitrine, não caminho
 * crítico, e uma landing com mensagem de erro é pior do que uma landing sem o exemplo.
 */
export function SampleDecisionCard() {
  const { t } = useTranslation("replayer");
  const [step, setStep] = useState<ReplayStep | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let vivo = true;
    sample.decision()
      .then((r) => { if (vivo) setStep(r.decision); })
      .catch(() => { if (vivo) setFalhou(true); });
    return () => { vivo = false; };
  }, []);

  // As mutations existem para satisfazer o contrato do painel; os blocos de coach que as usariam
  // ficam ocultos sem `studentId`. Reais (e inertes) em vez de objetos forjados: um dublê com
  // buraco quebraria em runtime se algum dia o gate mudasse.
  const inerte = useMutation({ mutationFn: async () => undefined });

  if (falhou) return null;
  if (!step) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-border bg-hud-surface py-10">
        <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
      </div>
    );
  }

  return (
    <SidePanels
      step={step}
      isError={!!step.is_error}
      isCorrect={!step.is_error}
      coachAnnotation={null}
      studentId={null}
      currentDecisionId={null}
      annotating={false}
      annComment=""
      annMode="complement"
      annAction=""
      annOverride={null}
      saveAnn={inerte}
      deleteAnn={inerte}
      // Só `replayData?.bb` é lido, e apenas nos blocos de showdown, que uma decisão de preflop
      // não tem. O `bb` do próprio step é a resposta certa quando alguém passar por ali.
      replayData={{ bb: step.bb } as ReplayData}
      playerAliases={{}}
      setAnnotating={() => {}}
      setAnnComment={() => {}}
      setAnnMode={() => {}}
      setAnnAction={() => {}}
      setAnnOverride={() => {}}
      openAnnotationForm={() => {}}
      t={t}
      gtoRequestStatus="idle"
      onRequestGto={() => {}}
      tournamentId=""
      handId=""
    />
  );
}
