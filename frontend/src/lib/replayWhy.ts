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
  /** veredito CLAMPADO exibido no banner (o mesmo `isActionOk` que decide ✓/◎/✗).
   *  A frase não pode ser decidida por uma fonte independente do selo — ver `precoDiverge`. */
  isActionOk?: boolean;
  /** ação do hero, minúscula (fold/call/check/bet/raise/shove) */
  heroAction: string;
  hasMultiwayAdvice: boolean;
  limpedPotHeuristic: boolean;
  /** Preco do pote limpado, quando ha custo de verdade (o BB tem opcao gratis e fica fora). */
  limpedPrice?: {
    custoBb: number; poteBb: number; exige: number; equity: number; nJogadores: number;
  } | null;
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
         top_freq?: number | null;
         /** tokens CRUS da carta (fold/call/raise/jam) — a comparação com a ação do hero tem que
          *  ser feita aqui, não na string já formatada que o card exibe */
         recommended_actions?: string[] | null } | null;
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

/**
 * Leitura de range por INICIATIVA — quem tinha a iniciativa quando a street começou diz o que a
 * aposta enfrentada costuma ser. Derivação PURA; a view só traduz a chave.
 *
 * A copy é ESTRUTURAL de propósito, sem alegação estatística: a medição de 12/08 (showdowns
 * reais do acervo) não sustenta ajuste de força por iniciativa — calls contra donk/check-raise
 * venceram 63,9% contra 55,8% vs c-bet, porque quem paga check-raise paga com range mais forte
 * (seleção, não força do vilão). O que se afirma é teoria estabelecida: c-bet é a aposta mais
 * frequente e mais larga; apostar contra o agressor é linha tipicamente mais polarizada.
 */
export function leituraDaIniciativa(isPostflop: boolean, facingBet: boolean,
                                    streetInitiative?: string | null): string | null {
  if (!isPostflop || !facingBet) return null;
  if (streetInitiative === "vilao") return "card.rangeCbet";
  if (streetInitiative === "hero") return "card.rangeTomada";
  return null;   // pote passivo ate aqui: a aposta nao tem historia de iniciativa para ler
}

/** Família canônica de uma ação, para comparar dialetos diferentes sem inventar equivalência.
 *  `jam`/`shove`/`allin` são a mesma ação com três nomes; `check` é a forma passiva de `call`
 *  (é assim que o backend classifica frequência). Raise e jam NÃO se fundem: a diferença entre
 *  min-raise e all-in é exatamente o que a frase de tamanho existe para dizer. */
function familiaAcao(a?: string | null): string {
  const t = (a ?? "").toLowerCase().trim();
  if (!t) return "";
  if (t === "jam" || t === "shove" || t === "allin" || t === "all-in") return "allin";
  if (t === "bet" || t === "raise") return "raise";
  if (t === "check" || t === "call" || t === "complete") return "call";
  if (t === "fold") return "fold";
  return t;
}

const AGRESSIVAS = new Set(["raise", "allin"]);

export function selectWhy(i: WhyInput): WhyChoice {
  // Estimativa multiway: o why heads-up usaria equity vs aleatória e contradiria o fold.
  if (i.hasMultiwayAdvice) return { key: "card.whyMultiwayEstimate" };

  // Pote limpado: a heurística recomenda passivo, sem fingir GTO. A frase MUDA com a posição —
  // "check é a opção grátis" só vale no BB. No SB o hero já pôs meia blind e precisa COMPLETAR,
  // e fora dos blinds não existe check nenhum. Reportado por um aluno no SB, que leu a frase e
  // viu um erro factual: a análise descrevia uma mesa que não era a dele.
  if (i.limpedPotHeuristic) {
    if ((i.heroPosition ?? "").toUpperCase() === "BB") return { key: "card.whyLimped" };
    // ── O PRECO entra na frase, e nao atras do olho ────────────────────────────────────────
    // Em 08/08 os dados de auditoria (equity, pot odds) foram para tras do toggle, com a regra
    // "a LEITURA sempre visivel, os DADOS no olho". No pote limpado o preco NAO e auditoria: e
    // a unica evidencia que sustenta o veredito, porque nao existe carta de GTO para essa
    // arvore. Esconde-lo deixava o card afirmando sem mostrar por que — e foi o pedido do
    // usuario depois do relatorio do coach: "mostrar o quanto valia a pena".
    if (i.limpedPrice) {
      const { custoBb, poteBb, exige, equity, nJogadores } = i.limpedPrice;
      return { key: "card.whyLimpedPreco", params: {
        custo: custoBb.toFixed(2), pote: poteBb.toFixed(1),
        exige: (exige * 100).toFixed(1), equity: (equity * 100).toFixed(1), n: nJogadores } };
    }
    return { key: "card.whyLimpedForaDoBb" };
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

    // ── A frase não pode absolver o que o card condena (nem o contrário) ────────────────────
    // Este ramo escolhia a frase SÓ pelo sinal do preço, sem olhar o veredito que está no mesmo
    // input. Caso real: turn call que o solver folda 88% — banner "✗ Erro", selo "−0,9 bb", "GTO
    // recomenda Fold", barras "Fold 88% / Call 12%", e a única frase sempre visível dizendo
    // "Call lucrativo: equity 28% supera pot odds 25%". Quem lê só a frase mantém o call. É a
    // mesma família do bug já corrigido no SELO de EV, agora na frase e no sentido inverso:
    // absolvendo em vez de acusar.
    //
    // `absolve` = a frase que sairia daqui elogia a ação tomada. Para o FOLD isso se inverte:
    // o preço fechar significa que o fold deixou EV na mesa (crítica), e o preço não fechar
    // significa fold correto (elogio).
    // Quando `absolve` discorda do veredito, quem manda é o veredito — e a frase NOMEIA a
    // divergência em vez de escolher um dos lados, que é o que o parágrafo `precoPagaMasVeredito`
    // já faz na evidência ao lado. `isActionOk` indefinido = chamador antigo: mantém o
    // comportamento conhecido em vez de inventar um terceiro.
    // `check` fica de fora: a frase dele (`whyCheck`) só recita os números, não elogia nem
    // critica, então não há o que contradizer.
    if (i.isActionOk != null && act !== "check") {
      const absolve = act === "fold" ? !i.profitable : !!i.profitable;
      if (absolve !== i.isActionOk) {
        return { key: i.profitable ? "card.whyPrecoFechaMasVeredito"
                                   : "card.whyPrecoNaoFechaMasVeredito", params: base };
      }
    }

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
    //
    // ── A comparação é de CONJUNTO e em tokens crus, não igualdade de string formatada ──────
    // `recAction` chega como `pg.recommended_actions.map(fmtAction).join(" / ")` — já formatada e
    // possivelmente com N ações ("Raise / Call") — enquanto `heroActionRaw` é o token cru
    // (`raise`). Com 2+ ações recomendadas a igualdade era IMPOSSÍVEL por construção, então `dif`
    // era sempre true e este ramo roubava o caso do `whyInRange`: um jogador que jogou
    // EXATAMENTE como a carta manda lia "✓ Correto" e, logo abaixo, "a jogada aqui é RAISE / CALL
    // — não Raise. A mão é boa; o que saiu do lugar foi o tamanho do aumento" — causa inventada
    // para um erro que não houve. Com hero pagando, a frase se contradizia em si mesma
    // ("é RAISE / CALL — não Call"). Medido no acervo: 33 de 707 cards preflop com veredito
    // Correto. E rec multi-ação é o caso NORMAL — a porta única monta `rec` com toda ação de
    // frequência ≥2% (ou ≥10%), e a própria fixture de exemplo do produto tem duas.
    const recFams = (i.pg.recommended_actions ?? []).map(familiaAcao).filter(Boolean);
    const heroFam = familiaAcao(i.heroActionRaw);
    const dif = recFams.length > 0 && !!heroFam && !recFams.includes(heroFam);
    if (i.pg.in_range && dif) {
      const freq = i.pg.top_freq != null && i.pg.top_freq > 0
        ? ` (${(i.pg.top_freq * 100).toFixed(0)}%)` : "";
      // O fecho "o que saiu do lugar foi o TAMANHO" so vale quando as duas acoes sao agressivas
      // (min-raise onde a carta manda all-in, por exemplo). Se a carta manda CALL e o jogador
      // aumentou, nao e questao de tamanho — e de acao, e a primeira metade da frase ja disse
      // isso. Afirmar "tamanho" ali seria explicar errado com confianca.
      // `every`, e nao "a primeira": com rec = Raise / Call o problema tambem nao e o tamanho.
      const soTamanho = AGRESSIVAS.has(heroFam) && recFams.every(f => AGRESSIVAS.has(f));
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
