/**
 * As três métricas do card v2, com o MOTIVO de cada ausência. Função pura, testada à parte.
 *
 * Mora aqui, e não dentro do componente, pelo mesmo motivo que `replayWhy`: é uma cascata de
 * decisão, e cascata não testada é onde bug se esconde. Cada `else` novo pode roubar o caso de
 * outro sem ninguém perceber.
 *
 * ── Por que o motivo importa tanto ────────────────────────────────────────────────────────────
 * Medido no acervo, a linha fica parcialmente vazia em 76% dos cards. Se as ausências virarem a
 * mesma célula em branco, o card passa três quartos do tempo dizendo "não sei" sem dizer de quê.
 * São QUATRO ausências distintas, e a diferença entre as duas últimas foi decisão do usuário:
 *
 *   sem_gabarito     não há carta nem nó: não existe linha ótima contra a qual medir custo
 *   fora_de_escala   o número é IMPOSSÍVEL (passa do pote + 2 stacks) — 62 decisões medidas
 *   nao_confiavel    os guardas desconfiam sem que o valor seja absurdo — 264 decisões; elas
 *                    CABEM no jogo, então chamá-las de "fora de escala" seria impreciso
 *   não se aplica    pot odds quando o hero apostou: não há preço a comparar, e isso não é
 *                    dado faltando
 */
import type { MetricaV2 } from "@/components/replayer/DecisionCardV2";

export interface EntradaMetricas {
  evLossBb?: number | null;
  /** Vem do backend (`_ev_e_motivo`). `null`/ausente quando o EV está presente. */
  evLossMotivo?: "sem_gabarito" | "fora_de_escala" | "nao_confiavel" | null;
  equity?: number | null;
  /** Equity exigida pelo preço enfrentado. Ausente quando o hero não pagou nada. */
  requerido?: number | null;
  /**
   * Equity mínima para a APOSTA do hero ser +EV. É o preço da jogada dele, e existe justamente
   * quando `requerido` não existe. O card clássico já resolvia assim — um slot, rótulo que muda.
   * O v2 dizia "não pagou" e três linhas abaixo mostrava esse número: o jogador lia "não tem
   * preço" seguido de um preço.
   */
  requeridoImplicito?: number | null;
  /** A ação do hero, para distinguir "não pagou" de "faltou dado". */
  acao?: string | null;
  /** `true` quando o veredito diz que a ação está ok — o EV zero então é informativo, não erro. */
  acaoOk?: boolean;
}

const MOTIVO_EV: Record<string, { motivo: string; motivoCurto: string }> = {
  sem_gabarito:   { motivo: "card.v2EvSemGabarito",   motivoCurto: "card.v2EvSemGabaritoCurto" },
  fora_de_escala: { motivo: "card.v2EvForaDeEscala",  motivoCurto: "card.v2EvForaDeEscalaCurto" },
  nao_confiavel:  { motivo: "card.v2EvNaoConfiavel",  motivoCurto: "card.v2EvNaoConfiavelCurto" },
};

/** Ações em que o hero PÕE fichas por iniciativa própria — não há preço enfrentado. */
const AGRESSIVAS = new Set(["bet", "raise", "shove", "jam", "all-in", "allin", "check"]);

export function metricasDoCard(e: EntradaMetricas): {
  evPerdido: MetricaV2; equity: MetricaV2; potOdds: MetricaV2;
} {
  // ── EV ────────────────────────────────────────────────────────────────────────────────────
  let evPerdido: MetricaV2;
  if (e.evLossBb != null) {
    // Zero é INFORMATIVO e aparece: "não custou nada" é diferente de "não sei quanto custou".
    evPerdido = {
      valor: `${e.evLossBb.toFixed(2)}bb`,
      tom: e.evLossBb >= 0.5 ? "ruim" : "neutro",
    };
  } else {
    // Sem motivo declarado pelo backend, o padrão é `sem_gabarito` — é o caso mais comum e o
    // menos alarmante. Inventar "fora de escala" aqui acusaria o solver por omissão nossa.
    const m = MOTIVO_EV[e.evLossMotivo ?? "sem_gabarito"] ?? MOTIVO_EV.sem_gabarito;
    evPerdido = { valor: null, ...m };
  }

  // ── Equity ────────────────────────────────────────────────────────────────────────────────
  // Existe em 100% das decisões medidas, mas o `null` é tratado mesmo assim: um dia em que
  // deixar de existir, o card diz "sem dado" em vez de imprimir "NaN%".
  const equity: MetricaV2 = e.equity != null
    ? { valor: `${(e.equity * 100).toFixed(1)}%`,
        tom: e.equity >= 0.55 ? "bom" : e.equity <= 0.35 ? "ruim" : "neutro" }
    : { valor: null, motivo: "card.v2SemDado", motivoCurto: "card.v2SemDado" };

  // ── Pot odds ──────────────────────────────────────────────────────────────────────────────
  let potOdds: MetricaV2;
  if (e.requerido != null && e.requerido > 0) {
    potOdds = { valor: `${(e.requerido * 100).toFixed(0)}%` };
  } else if (e.requeridoImplicito != null && e.requeridoImplicito > 0) {
    // Apostou: o preço é o dele. Mesmo slot, rótulo diferente — "mín. EV" é a equity a partir da
    // qual a aposta paga. Dizer "não pagou" aqui era a contradição.
    potOdds = { valor: `${(e.requeridoImplicito * 100).toFixed(0)}%`, rotulo: "card.reqMinEv" };
  } else if (AGRESSIVAS.has((e.acao ?? "").toLowerCase())) {
    potOdds = { valor: null, motivo: "card.v2OddsNaoEnfrentouAposta",
                motivoCurto: "card.v2OddsNaoEnfrentouApostaCurto" };
  } else {
    potOdds = { valor: null, motivo: "card.v2SemDado", motivoCurto: "card.v2SemDado" };
  }

  return { evPerdido, equity, potOdds };
}
