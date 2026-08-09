/**
 * Escolha da frase "por quê" do Decision Card — função PURA.
 *
 * Por que isto saiu do Replayer: eram ~60 linhas de cascata inline dentro de um componente de
 * 1100+ linhas, sem teste, e produziram dois bugs de mentira ao usuário só numa conversa:
 *   1. uma decisão PREFLOP recebia "Spot postflop sem solução pré-computada" — o ramo sem GTO
 *      não olhava a street;
 *   2. um call vs 3-bet exibia equity vs mão ALEATÓRIA como evidência, apontando para o lado
 *      oposto do veredito.
 * Cascata de prioridade não testada é onde bug se esconde: cada `else if` novo pode roubar o
 * caso de outro, e ninguém percebe até o jogador reclamar.
 *
 * Devolve CHAVE + PARAMS em vez de texto traduzido — assim o teste verifica a decisão sem
 * depender do i18n, e a tradução continua sendo responsabilidade da view.
 */

export interface WhyInput {
  /** street atual — decide frases que citam flop/postflop */
  isPostflop: boolean;
  isError: boolean;
  /** ação do hero, minúscula (fold/call/check/bet/raise/shove) */
  heroAction: string;
  hasMultiwayAdvice: boolean;
  limpedPotHeuristic: boolean;
  /** preflop enfrentando aposta com equity vs_random: a conta não descreve o spot */
  equityNotRangeAware: boolean;
  preflopNoCoverageStrict: boolean;
  gtoSpotMismatch: boolean;
  isPfZone: boolean;
  heroStackBb?: number | null;
  /** posicao do hero (BB/SB/BTN/...). O check GRATIS so existe no BB: no SB o hero ja pos
   *  meia blind e precisa COMPLETAR, e nas demais posicoes nem existe check. */
  heroPosition?: string | null;
  hasEngineGtoConflict: boolean;
  engineBest?: string | null;
  gtoAction?: string | null;
  hasMathEvidence: boolean;
  requiredIsAdjusted: boolean;
  eq?: number | null;
  req?: number | null;
  profitable?: boolean | null;
  hasGto: boolean;
  isHero: boolean;
  /** bloco de range preflop, quando disponível */
  pg?: { available?: boolean; in_range?: boolean; hand_type?: string; scenario?: string;
         range_pct?: number; stack_bucket?: string; coverage_reason?: string | null;
         /** frequência GTO da AÇÃO recomendada, quando a carta traz (0..1) */
         top_freq?: number | null } | null;
  /** ação recomendada pelo card (o `_best_action` final, não o palpite da heurística) */
  recAction?: string | null;
  /** ação que o jogador tomou, normalizada */
  heroActionRaw?: string | null;
}

export interface WhyChoice {
  /** chave i18n completa, ou "" quando a frase deve ser omitida de propósito */
  key: string;
  params?: Record<string, unknown>;
  /** ação a formatar antes de traduzir (a view aplica formatAction) */
  actionParams?: Record<string, string>;
}

const NONE: WhyChoice = { key: "" };

export function selectWhy(i: WhyInput): WhyChoice {
  // Estimativa multiway: o why heads-up usaria equity vs aleatória e contradiria o fold.
  if (i.hasMultiwayAdvice) return { key: "card.whyMultiwayEstimate" };

  // Pote limpado: a heurística recomenda passivo, sem fingir GTO. A frase MUDA com a posição —
  // "check é a opção grátis" só vale no BB. No SB o hero já pôs meia blind e precisa COMPLETAR,
  // e fora dos blinds não existe check nenhum. Reportado por um aluno no SB, que leu a frase e
  // viu um erro factual: a análise descrevia uma mesa que não era a dele.
  if (i.limpedPotHeuristic) {
    return { key: (i.heroPosition ?? "").toUpperCase() === "BB"
      ? "card.whyLimped" : "card.whyLimpedForaDoBb" };
  }

  // ANTES da cobertura (que zera a frase): sem isto o card fica com o veredito nu depois de
  // omitir a barra de equity, e o jogador não descobre de onde veio o "erro".
  if (i.equityNotRangeAware) return { key: "card.whyRangeNotPrice" };

  // Sem cobertura GTO: a tag de cobertura já explica; não inventar porquê sobre dado stale.
  if (i.preflopNoCoverageStrict) {
    // Era `NONE` — a frase sumia e o MOTIVO da ausencia vivia num indicador, que em 08/08 foi
    // para tras do olho. Resultado: o card dizia "Heuristica" e nao explicava por que a carta
    // GTO calou. Saber POR QUE nao ha gabarito e leitura, nao auditoria.
    const motivo = i.pg?.coverage_reason;
    return motivo && motivo !== "limped_pot"
      ? { key: `card.semGabarito.${motivo}` }
      : NONE;
  }

  if (i.gtoSpotMismatch) {
    return { key: i.engineBest === "call" ? "card.whyMismatchFacing" : "card.whyMismatchNoBet" };
  }

  if (i.isPfZone) {
    return { key: "card.whyPushfold", params: { stack: (i.heroStackBb ?? 0).toFixed(1) } };
  }

  if (i.hasEngineGtoConflict) {
    return { key: "card.whyEngineConflict",
             actionParams: { engine: i.engineBest ?? "", gto: i.gtoAction ?? "" } };
  }

  if (i.hasMathEvidence && i.eq != null && i.req != null) {
    const eqPct = Math.round(i.eq * 100);
    const reqPct = Math.round(i.req * 100);
    const margin = eqPct - reqPct;
    // "necessário" é pot odds bruto, ou o ajustado quando o engine aplicou realization/ICM.
    const reqLabelKey = i.requiredIsAdjusted ? "card.reqLabelAdjusted" : "card.reqLabelPotOdds";
    const base = { eqPct, reqPct, reqLabelKey };
    const act = i.heroAction;

    // A frase descreve a AÇÃO TOMADA, nunca a alternativa: "Call lucrativo" quando o hero
    // foldou soa como crítica oposta ao veredito.
    if (act === "fold") {
      return i.profitable
        ? { key: margin <= 3 ? "card.whyFoldBreakeven" : "card.whyFoldLeftEv", params: base }
        : { key: "card.whyFoldCorrect", params: base };
    }
    if (act === "call") {
      return { key: i.profitable ? "card.whyCallProfit" : "card.whyCallLose", params: base };
    }
    if (act === "check") return { key: "card.whyCheck", params: base };
    // bet/raise/shove
    return { key: i.profitable ? "card.whyAggrProfit" : "card.whyAggrRisk",
             params: base, actionParams: { act } };
  }

  if (!i.isPostflop && i.pg?.available) {
    const pct = (i.pg.range_pct ?? 0) > 0 ? ` (${((i.pg.range_pct ?? 0) * 100).toFixed(0)}%)` : "";
    const base = { hand: i.pg.hand_type, scenKey: i.pg.scenario, pct, bucket: i.pg.stack_bucket };

    // A frase tem que falar da AÇÃO quando é a ação que está errada.
    //
    // Caso real (print de producao): 33 no SB heads-up a 17bb, jogador min-raisou, a carta manda
    // all-in. O card dizia "33 está no range de abertura" — verdade, e irrelevante: ele NÃO errou
    // por estar fora do range, errou o TAMANHO. Descrever a mão quando o veredito é sobre a ação
    // deixa o jogador sem saber o que corrigir.
    const dif = !!i.recAction && !!i.heroActionRaw
      && i.recAction.toLowerCase() !== i.heroActionRaw.toLowerCase();
    if (i.pg.in_range && dif) {
      const freq = i.pg.top_freq != null && i.pg.top_freq > 0
        ? ` (${(i.pg.top_freq * 100).toFixed(0)}%)` : "";
      // O fecho "o que saiu do lugar foi o TAMANHO" so vale quando as duas acoes sao agressivas
      // (min-raise onde a carta manda all-in, por exemplo). Se a carta manda CALL e o jogador
      // aumentou, nao e questao de tamanho — e de acao, e a primeira metade da frase ja disse
      // isso. Afirmar "tamanho" ali seria explicar errado com confianca.
      const agressiva = (a?: string | null) =>
        !!a && /^(raise|bet|jam|shove|allin|all-in)/.test(a.toLowerCase());
      const soTamanho = agressiva(i.recAction) && agressiva(i.heroActionRaw);
      return {
        key: soTamanho ? "card.whyAcaoDivergeTamanho" : "card.whyAcaoDiverge",
        params: { ...base, freq },
        actionParams: { rec: i.recAction as string, act: i.heroActionRaw as string },
      };
    }
    return { key: i.pg.in_range ? "card.whyInRange" : "card.whyOutRange", params: base };
  }

  if (!i.hasGto && i.isHero) {
    // A frase PRECISA respeitar a street: `whyMultiway` afirma "Spot postflop", e este ramo
    // pega QUALQUER decisão do hero sem GTO — inclusive preflop.
    return { key: i.isPostflop ? "card.whyMultiway" : "card.whyNoGtoPreflop" };
  }

  if (i.isPostflop && i.eq != null) {
    return { key: i.eq >= 0.70 ? "card.whyEqStrong"
                 : i.eq >= 0.50 ? "card.whyEqFavorable"
                 : i.eq >= 0.35 ? "card.whyEqUnfavorable"
                 : "card.whyEqWeak" };
  }

  return { key: "card.whyContext" };
}
