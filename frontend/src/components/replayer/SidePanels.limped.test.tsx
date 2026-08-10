// @vitest-environment jsdom
// O PRECO aparece no pote limpado — pedido do usuario depois do relatorio do coach:
// "apresentar as odds nestas decisoes de completar, pra mostrar o quanto valia a pena".
//
// Havia um bloqueio real na tela. `equityNotRangeAware` esconde equity e pot odds no pre-flop
// quando a equity nao vem de range, e existe por um bom motivo: um AQs no SB pagando 3-bet
// aparecia como "66,3% vs 46,4% · +19,9pp" ao lado de "ERRO / RECOMENDADO FOLD", porque o numero
// era vs mao ALEATORIA. Evidencia contradizendo veredito ensina o jogador a desconfiar de tudo.
//
// Mas pote limpado e o unico spot pre-flop SEM CARTA em fonte nenhuma (a arvore do GW nao deixa
// UTG-BTN limpar). Ali a equity passou a ser multiway de verdade (Monte Carlo pelo numero de
// jogadores que ainda podem ver o flop), e o preco e a UNICA evidencia do veredito. Escondê-lo
// justo ali deixa o card afirmando sem mostrar por que.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SidePanels } from "./SidePanels";

afterEach(cleanup);

// `t` de identidade com interpolacao: o teste checa ESTRUTURA (a linha aparece, com o numero),
// nao a traducao — que vive nos locales e tem o seu proprio guarda de paridade de chaves.
const t = ((k: string, o?: Record<string, unknown>) =>
  o ? `${k}:${Object.values(o).join(",")}` : k) as never;

function passo(extra: Record<string, unknown> = {}) {
  return {
    // `type: "action"` e `is_hero` sao obrigatorios: sem eles o painel retorna null e o
    // DOM sai VAZIO — e ai todo `not.toContain` passa sem provar nada. Foi o que aconteceu
    // na primeira versao deste arquivo: dois "controles" verdes sobre tela em branco.
    type: "action", street: "preflop", action: "fold", is_hero: true, position: "SB",
    // `_hasBasis`: sem uma base de veredito o painel tambem nao renderiza.
    error_label: "standard",
    // Sem o bloco `preflop_gto` o card nao reconhece o pote limpado: `limpedPotHeuristic`
    // exige `coverage_reason === 'limped_pot'`.
    preflop_gto: { available: false, coverage_reason: "limped_pot" },
    facing_to_call_bb: 0.5,
    hand_equity: 0.32, pot_odds_equity: 0.119, hero_stack_bb: 32.2,
    ...extra,
  };
}

function montar(step: Record<string, unknown>) {
  // `SidePanels` usa `useMutation` (o "melhorar com IA" da anotacao do coach), entao precisa
  // do provider mesmo que o teste nunca dispare mutacao nenhuma.
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
    <SidePanels
      step={step as never} isError={false} isCorrect={false}
      coachAnnotation={null as never} studentId={null as never}
      currentDecisionId={null as never} annotating={false}
      annComment="" annMode={"replace" as never} annAction=""
      annOverride={null as never}
      saveAnn={{} as never} deleteAnn={{} as never}
      replayData={{ bb: 1000 } as never} playerAliases={{} as never}
      setAnnotating={() => {}} setAnnComment={() => {}} setAnnMode={() => {}}
      setAnnAction={() => {}} setAnnOverride={() => {}}
      openAnnotationForm={() => {}} t={t}
      gtoRequestStatus={null as never} onRequestGto={() => {}}
      tournamentId={1 as never} handId={"1" as never}
    />
    </QueryClientProvider>,
  );
}

describe("pote limpado mostra o preco", () => {
  it("SANIDADE: o painel renderiza alguma coisa", () => {
    // Sem este teste os `not.toContain` abaixo passam com o DOM vazio. Zero tranquilizador
    // e o pior resultado possivel num teste de tela.
    montar(passo({ facing_limp: true, n_can_see_flop: 2 }));
    expect((document.body.textContent ?? "").length).toBeGreaterThan(20);
  });

  it("o PRECO entra na frase sempre visivel, nao atras do olho", () => {
    // Em 08/08 equity e pot odds foram para tras do toggle de detalhes, com a regra "a LEITURA
    // sempre visivel, os DADOS no olho". No pote limpado o preco nao e auditoria: e a UNICA
    // evidencia do veredito, porque nao ha carta de GTO para essa arvore.
    montar(passo({ facing_limp: true, n_can_see_flop: 2 }));
    const texto = document.body.textContent ?? "";
    expect(texto, "a frase do preco nao apareceu").toContain("card.whyLimpedPreco");
    expect(texto, "o custo sumiu").toContain("0.50");
    expect(texto, "o minimo necessario sumiu").toContain("11.9");
    expect(texto, "a equity sumiu").toContain("32.0");
    expect(texto, "o numero de jogadores sumiu").toContain("2");
  });

  it("com o olho ABERTO, a fonte da equity diz contra quantos", () => {
    localStorage.setItem("replayer_show_details", "true");
    montar(passo({ facing_limp: true, n_can_see_flop: 3 }));
    const texto = document.body.textContent ?? "";
    // Nao e "vs range" (nao ha carta) nem "vs aleatoria" (o numero e multiway). E dizer QUANTOS
    // e o que faz o valor ser lido certo: 32% contra 1 jogador e outra coisa que 32% contra 3.
    expect(texto).toContain("card.vsMultiway:3");
    expect(texto, "rotulo antigo vazou").not.toContain("card.vsRandom");
    localStorage.removeItem("replayer_show_details");
  });

  it("CONTROLE: fora do pote limpado a supressao continua valendo", () => {
    // Mesmo passo, sem `facing_limp`. E o caso do AQs vs 3-bet que originou a supressao: aqui a
    // equity É vs mao aleatoria e nao pode aparecer. Sem este controle o teste acima passaria
    // com a regra removida de vez.
    montar(passo({ preflop_gto: { available: false, coverage_reason: "pairing_uncovered" } }));
    const texto = document.body.textContent ?? "";
    expect(texto.length, "controle vazio nao prova nada").toBeGreaterThan(20);
    expect(texto, "a frase do preco vazou para fora do pote limpado").not.toContain("card.whyLimpedPreco");
  });

  it("CONTROLE 2: pote limpado heads-up nao entra (o BB nao paga nada)", () => {
    // `n_can_see_flop < 2` significa que o hero e o BB com opcao gratis, ou que ninguem sobrou.
    // Sem custo nao ha preco, e mostrar "minimo necessario" ali seria inventar decisao.
    montar(passo({ facing_limp: true, n_can_see_flop: 1, facing_to_call_bb: 0 }));
    const texto = document.body.textContent ?? "";
    expect(texto.length, "controle vazio nao prova nada").toBeGreaterThan(20);
    expect(texto).not.toContain("card.whyLimpedPreco");
  });
});

describe("toggle do layout v2", () => {
  afterEach(() => localStorage.removeItem("replayer_card_v2"));

  it("o CLASSICO e o padrao, e existe porta para LIGAR o v2", () => {
    // A primeira versao so tinha o botao "voltar ao classico", dentro do ramo v2 — um opt-in sem
    // como optar. Sem este teste, o layout novo seria inalcancavel e ninguem notaria.
    montar(passo({ facing_limp: true, n_can_see_flop: 2 }));
    const texto = document.body.textContent ?? "";
    expect(texto, "sem a porta de entrada o v2 e inalcancavel").toContain("card.v2ToggleOff");
    expect(texto, "o padrao tem de ser o classico").not.toContain("card.v2ToggleOn");
  });

  it("com o v2 ligado, o card muda e a saida de volta aparece", () => {
    localStorage.setItem("replayer_card_v2", "true");
    montar(passo({ facing_limp: true, n_can_see_flop: 2 }));
    const texto = document.body.textContent ?? "";
    expect(texto, "o v2 nao renderizou").toContain("card.v2EvPerdido");
    expect(texto, "sem saida, o usuario fica preso no layout novo").toContain("card.v2ToggleOn");
  });

  it("o v2 mostra o MOTIVO quando o custo se cala", () => {
    // Pote limpado nao tem gabarito, entao nao ha linha otima contra a qual medir custo. O slot
    // vazio tem de dizer isso — celula em branco e o que este layout existe para nao ter.
    localStorage.setItem("replayer_card_v2", "true");
    montar(passo({ facing_limp: true, n_can_see_flop: 2, ev_loss_bb: null,
                   ev_loss_motivo: "sem_gabarito" }));
    expect(document.body.textContent ?? "").toContain("card.v2EvSemGabaritoCurto");
  });

  it("os 264 recebem motivo PROPRIO, nao 'fora de escala'", () => {
    // Eles cabem no jogo; o que falta e confianca. Chama-los de impossiveis seria impreciso.
    localStorage.setItem("replayer_card_v2", "true");
    montar(passo({ facing_limp: true, n_can_see_flop: 2, ev_loss_bb: null,
                   ev_loss_motivo: "nao_confiavel" }));
    const texto = document.body.textContent ?? "";
    expect(texto).toContain("card.v2EvNaoConfiavelCurto");
    expect(texto).not.toContain("card.v2EvForaDeEscalaCurto");
  });
});
