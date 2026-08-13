// Card de veredito v2 — layout enxuto, desenhado a partir dos casos que QUEBRAM.
//
// O pedido veio de um exemplo de card mais simples. O exemplo, porém, mostrava uma decisão
// correta com cobertura total do solver — o caso fácil. Medido no acervo, o difícil é a regra:
//
//     decisões                                  9.813
//     SEM veredito GTO nenhum                   1.565  (16%)
//     com os TRÊS números (EV, equity, odds)    2.425  (24%)
//     com NENHUM dos três                           0
//
// Ou seja, a linha de métricas fica parcialmente vazia em 76% dos cards. Por isso o estado
// VAZIO é o centro deste componente, não um detalhe: cada slot diz POR QUE se calou.
//
// E são três ausências de naturezas diferentes, que não podem virar a mesma célula em branco:
//
//     não se aplica    pot odds quando o hero apostou em vez de pagar
//     não é confiável  o EV fora da escala do jogo (326 cards, ver `ev_loss_trustworthy`)
//     sempre existe    equity
//
// Célula sem dado nunca vira 0, e "não sei" sem explicação lê como produto quebrado — as duas
// regras já custaram caro aqui.
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

import { SOURCE_VARIANT_CLS } from "./DecisionCard";
import type { DecisionSource, DecisionVerdict, IcmBadge } from "./DecisionCard";
import { colorFor } from "@/lib/actionColors";

/** Uma métrica da linha de três. `valor` já formatado; `motivo` explica a ausência. */
export interface MetricaV2 {
  valor: string | null;
  /** Chave i18n do POR QUÊ longo (tooltip), quando `valor` é null. */
  motivo?: string | null;
  /**
   * Chave i18n do rótulo CURTO, mostrado sem hover. Explícito de propósito: a primeira versão
   * derivava por convenção (`motivo + "Curto"`) com `defaultValue`, e uma chave faltando caía
   * calada no genérico "sem dado" — o modo de falha que este componente existe para evitar.
   * Sendo campo, a omissão aparece no call site.
   */
  motivoCurto?: string | null;
  /** Tom do valor, quando ele merece cor (custo alto, equity forte). */
  tom?: "neutro" | "bom" | "ruim";
  /** Rótulo alternativo: o mesmo slot muda de nome quando muda de significado. */
  rotulo?: string | null;
}

export interface LinhaEstrategia {
  acao: string;
  freq: number;
  /** A ação que o hero de fato jogou — marcada, e não repetida em texto à parte. */
  jogada?: boolean;
}

interface Props {
  verdict: DecisionVerdict;
  source: DecisionSource;
  playedAction: string;
  idealAction?: string | null;
  isActionOk: boolean;
  /** Rótulo curto do contexto (street, "multiway", "pote limpado"). */
  contexto?: string | null;
  metricas: { evPerdido: MetricaV2; equity: MetricaV2; potOdds: MetricaV2 };
  /** Barras de frequência. `null` quando não há gabarito — e aí o bloco não aparece. */
  estrategia?: LinhaEstrategia[] | null;
  /** Título do bloco de estratégia: muda com a fonte (solver, carta, estimativa multiway). */
  estrategiaTitulo?: string | null;
  /** A frase única. É a LEITURA, sempre visível. */
  frase?: string | null;
  showDetails: boolean;
  onToggleDetails: () => void;
  /** Auditoria: fica atrás do olho, como no clássico. */
  detalhes?: React.ReactNode;
  icmBadge?: IcmBadge | null;
  fmtAction: (a: string) => string;
  verdictTooltip?: string;
}

const TOM_CLS: Record<NonNullable<MetricaV2["tom"]>, string> = {
  neutro: "text-foreground",
  bom: "text-emerald-400",
  ruim: "text-red-400",
};

function Metrica({ rotulo, m }: { rotulo: string; m: MetricaV2 }) {
  const { t } = useTranslation("replayer");
  const vazio = m.valor == null;
  return (
    <div className="flex-1 min-w-0 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/80">
        {m.rotulo ? t(m.rotulo) : rotulo}
      </div>
      {vazio ? (
        // O travessão sozinho seria "não sei" sem explicação. O `title` carrega o motivo, e o
        // rótulo curto abaixo garante que a razão apareça mesmo sem hover — em toque não há hover.
        <div className="cursor-help" title={m.motivo ? t(m.motivo) : undefined}>
          <span className="font-mono text-[15px] font-bold tabular-nums text-muted-foreground/40">
            —
          </span>
          {m.motivo && (
            <div className="font-mono text-[9px] leading-tight text-muted-foreground/60 truncate">
              {t(m.motivoCurto ?? "card.v2SemDado")}
            </div>
          )}
        </div>
      ) : (
        <div className={cn("font-mono text-[15px] font-bold tabular-nums",
                           TOM_CLS[m.tom ?? "neutro"])}>
          {m.valor}
        </div>
      )}
    </div>
  );
}

export function DecisionCardV2({
  verdict, source, playedAction, idealAction, isActionOk, contexto,
  metricas, estrategia, estrategiaTitulo, frase,
  showDetails, onToggleDetails, detalhes, icmBadge, fmtAction, verdictTooltip,
}: Props) {
  const { t } = useTranslation("replayer");
  // Duas colunas só quando o GTO recomenda OUTRA coisa. Concordando, repetir a ação dos dois
  // lados é a redundância que este layout existe para cortar — o exemplo que originou o pedido
  // mostrava o mesmo "62%" três vezes.
  const divergente = !!idealAction && !isActionOk
                     && idealAction.toLowerCase() !== playedAction.toLowerCase();

  return (
    <section className={cn("rounded-xl border overflow-hidden", verdict.borderCls)}>
      <div className={cn("flex items-center justify-between pl-3 pr-10 py-2.5", verdict.hdrCls)}>
        <span className={cn("font-mono text-sm font-bold uppercase tracking-wide", verdict.cls)}
              title={verdictTooltip}>
          {verdict.icon} {verdict.label}
        </span>
        <div className="flex items-center gap-2">
          {/* Contexto igual ao badge da fonte vira eco ("PREFLOP PREFLOP", print de 13/08) —
              a street só informa quando a FONTE não a diz. Comparação no ponto de display,
              então vale para qualquer par futuro, não só preflop. */}
          {contexto && contexto.toLowerCase() !== source.label.toLowerCase() && (
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/70">
              {contexto}
            </span>
          )}
          {/* A FONTE fica, e é deliberado. O exemplo escrevia só a street, que não diz de onde
              veio o veredito — com 1.565 decisões sem gabarito, o card tem de declarar a origem
              ou vira afirmação sem lastro. */}
          <span className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] uppercase ring-1",
                              SOURCE_VARIANT_CLS[source.variant])}
                title={source.tooltip}>
            {source.label}
          </span>
          <button type="button" onClick={onToggleDetails}
                  title={showDetails ? t("card.toggleHide") : t("card.toggleShow")}
                  className="text-muted-foreground/60 hover:text-foreground transition-colors">
            {showDetails ? "◉" : "◎"}
          </button>
        </div>
      </div>

      <div className={cn("grid divide-x divide-border/60", divergente ? "grid-cols-2" : "grid-cols-1")}>
        <div className="px-3 py-2.5">
          <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/80">
            {t("card.youPlayed")}
          </div>
          <div className="font-mono text-base font-bold text-foreground">
            {fmtAction(playedAction)}
          </div>
        </div>
        {divergente && (
          <div className="px-3 py-2.5">
            <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/80">
              {t("card.gtoRecommends")}
            </div>
            <div className={cn("font-mono text-base font-bold", verdict.cls)}>
              {fmtAction(idealAction!)}
            </div>
          </div>
        )}
      </div>

      {estrategia && estrategia.length > 0 && (
        <div className="border-t border-border/60 px-3 py-2.5">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/80">
              {estrategiaTitulo ?? t("card.solverStrategy")}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/60">
              {t("card.v2Freq")}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            {estrategia.map(r => {
              // Cor CANONICA por acao (a mesma do range grid e das barras do layout
              // classico) — barra monocromatica nao distingue Call de Raise de relance.
              const cor = colorFor(r.acao);
              return (
                <div key={r.acao} className="flex items-center gap-2">
                  <span className={cn("w-14 shrink-0 font-mono text-[11px]",
                                      r.jogada ? "font-bold" : "opacity-80")}
                        style={{ color: cor }}>
                    {fmtAction(r.acao)}{r.jogada ? " •" : ""}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border/40">
                    <div className="h-full rounded-full"
                         style={{ width: `${Math.min(100, r.freq * 100).toFixed(0)}%`,
                                  background: cor, opacity: r.jogada ? 1 : 0.75 }} />
                  </div>
                  <span className="w-9 shrink-0 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                    {(r.freq * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* A linha de três: SEMPRE presente, mesmo com slot vazio. Em 08/08 estes números foram
          para trás do olho, e no pote limpado isso deixou o card afirmando sem mostrar por quê. */}
      <div className="flex border-t border-border/60 divide-x divide-border/60">
        <Metrica rotulo={t("card.v2EvPerdido")} m={metricas.evPerdido} />
        <Metrica rotulo={t("card.v2Equity")} m={metricas.equity} />
        <Metrica rotulo={t("card.v2PotOdds")} m={metricas.potOdds} />
      </div>

      {frase && (
        <p className="border-t border-border/60 px-3 py-2.5 text-[12.5px] leading-relaxed text-foreground/90">
          {frase}
        </p>
      )}

      {showDetails && detalhes && (
        <div className="border-t border-border/60 bg-background/40 px-3 py-2.5">{detalhes}</div>
      )}

      {icmBadge && (
        <div className="border-t border-border/60 px-3 py-1.5">
          <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/70"
                title={icmBadge.tooltip}>
            {icmBadge.label}
          </span>
        </div>
      )}
    </section>
  );
}
