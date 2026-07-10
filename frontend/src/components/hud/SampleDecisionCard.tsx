import { useState } from "react";
import { useTranslation } from "react-i18next";
import { DecisionCard } from "@/components/replayer/DecisionCard";
import { formatAction } from "@/lib/utils";

/**
 * Decision Card de EXEMPLO (estático), renderizado com o mesmo componente do produto (single
 * source of truth, sem screenshot). Um spot de MTT onde o hero pagou mas devia foldar: veredito
 * de Erro + ação recomendada + EV perdido. Reusado na landing (P1) e no fallback do fluxo de
 * mão-de-exemplo (P2). Classes de veredito idênticas às do Replayer (cardLogic error).
 */
export function SampleDecisionCard() {
  const { t } = useTranslation("replayer");
  const { t: to } = useTranslation("onboarding");
  const [showDetails, setShowDetails] = useState(false);

  const evidence = (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-2 py-1 ring-1 ring-primary/30">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">{to("sample.equity")}</span>
        <span className="font-mono text-sm font-bold text-primary tabular-nums">34%</span>
      </span>
      <span className="font-mono text-muted-foreground">&lt;</span>
      <span className="inline-flex items-center gap-1.5 rounded-md bg-red-500/10 px-2 py-1 ring-1 ring-red-500/30">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">{to("sample.needs")}</span>
        <span className="font-mono text-sm font-bold text-red-400 tabular-nums">42%</span>
      </span>
    </div>
  );

  return (
    <DecisionCard
      verdict={{
        icon: "✗",
        label: t("card.vError"),
        cls: "text-red-400",
        borderCls: "border-red-500/30",
        hdrCls: "bg-red-500/8",
      }}
      source={{ label: "GTO Solver", tooltip: to("sample.sourceTip"), variant: "gto" }}
      playedAction="call"
      idealAction="fold"
      isActionOk={false}
      evLossBb={1.8}
      evidence={evidence}
      why={to("sample.why")}
      footer={{ stackBb: 22, mRatio: 9 }}
      showDetails={showDetails}
      onToggleDetails={() => setShowDetails((s) => !s)}
      fmtAction={formatAction}
    />
  );
}
