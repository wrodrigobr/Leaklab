// @vitest-environment jsdom
// O card v2 desenhado a partir dos casos que QUEBRAM, nao do caso facil.
//
// O pedido veio de um exemplo de card mais simples, e o exemplo mostrava uma decisao correta com
// cobertura total do solver. Medido no acervo, esse e o caso raro:
//
//     decisoes                                  9.813
//     SEM veredito GTO nenhum                   1.565  (16%)
//     com os TRES numeros (EV, equity, odds)    2.425  (24%)
//     com NENHUM dos tres                           0
//
// A linha de metricas fica parcialmente vazia em 76% dos cards. Se o layout so funcionar cheio,
// ele quebra em tres de cada quatro telas — e o jeito de descobrir isso e testar o dificil
// primeiro. O facil vem de graca; o inverso nao e verdade.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DecisionCardV2 } from "./DecisionCardV2";
import type { MetricaV2 } from "./DecisionCardV2";

afterEach(cleanup);

const veredito = (label: string) => ({
  icon: "✓", label, cls: "text-emerald-400",
  borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8",
});
const fonte = (label: string, variant = "gto") =>
  ({ label, tooltip: `tip:${label}`, variant } as never);

const VAZIO: MetricaV2 = { valor: null };

function montar(props: Record<string, unknown> = {}) {
  return render(
    <DecisionCardV2
      verdict={veredito("Correto") as never}
      source={fonte("Solver")}
      playedAction="call"
      isActionOk
      metricas={{ evPerdido: { valor: "0.00bb" }, equity: { valor: "54.0%" },
                  potOdds: { valor: "29%" } }}
      showDetails={false}
      onToggleDetails={() => {}}
      fmtAction={(a: string) => a.toUpperCase()}
      {...props}
    />,
  );
}

const txt = () => document.body.textContent ?? "";

// LIMITE CONHECIDO desta suite: `textContent` prova que o texto esta na ARVORE, nao que esta
// VISIVEL. O jsdom nao carrega o Tailwind, entao trocar uma classe por `hidden` passaria batido
// aqui — verificado mutando: `className="hidden"` sobreviveu, remover o elemento foi acusado.
// Para regressao de VISIBILIDADE por CSS este arquivo nao serve; serve para estrutura e conteudo.

describe("card v2 — os quatro casos que quebram", () => {
  it("SANIDADE: o caso facil renderiza os tres numeros", () => {
    // Sem esta ancora, todo `not.toContain` abaixo passaria com a tela em branco. Ja aconteceu
    // neste projeto: dois controles verdes sobre DOM vazio.
    montar();
    expect(txt()).toContain("0.00bb");
    expect(txt()).toContain("54.0%");
    expect(txt()).toContain("29%");
  });

  it("SEM GABARITO: some a estrategia, ficam as metricas, e o EV diz por que calou", () => {
    // 1.565 decisoes (16%) nao tem veredito GTO nenhum. O bloco de barras nao pode aparecer
    // vazio nem com zeros — some. Mas o card nao pode virar so um selo: equity existe sempre.
    montar({
      source: fonte("Heurística", "heuristic"),
      estrategia: null,
      metricas: { evPerdido: { valor: null, motivo: "card.v2EvSemGabarito", motivoCurto: "card.v2EvSemGabaritoCurto" },
                  equity: { valor: "34.0%" }, potOdds: { valor: "25%" } },
    });
    expect(txt(), "a equity sumiu junto com a estrategia").toContain("34.0%");
    expect(txt(), "o preco sumiu junto com a estrategia").toContain("25%");
    expect(txt(), "o motivo curto nao apareceu").toContain("card.v2EvSemGabaritoCurto");
    expect(txt(), "a fonte sumiu, e ela e o que sustenta o veredito sem carta")
      .toContain("Heurística");
  });

  it("EV SILENCIADO: o slot nao fica mudo — diz que esta fora de escala", () => {
    // O caso que o usuario reportou: "-3588 bb" num stack de 32,2bb. Hoje o backend cala o
    // numero (326 cards). Calar sem explicar seria trocar um defeito por outro: o jogador nao
    // sabe se nao perdeu nada ou se o produto nao sabe.
    montar({
      verdict: veredito("Erro") as never,
      isActionOk: false, idealAction: "call",
      metricas: { evPerdido: { valor: null, motivo: "card.v2EvForaDeEscala", motivoCurto: "card.v2EvForaDeEscalaCurto" },
                  equity: { valor: "34.0%" }, potOdds: { valor: "25%" } },
    });
    expect(txt()).toContain("card.v2EvForaDeEscalaCurto");
    expect(txt(), "um zero no lugar do desconhecido e a pior saida").not.toContain("0.00bb");
  });

  it("NAO ENFRENTOU APOSTA: pot odds nao se aplica, e isso nao e o mesmo que faltar dado", () => {
    // Pot odds so existe em 48% das decisoes — quando o hero APOSTOU, nao ha preco a comparar.
    // Sao ausencias de naturezas diferentes e nao podem virar a mesma celula em branco.
    montar({
      playedAction: "bet",
      metricas: { evPerdido: { valor: "0.30bb" }, equity: { valor: "61.0%" },
                  potOdds: { valor: null, motivo: "card.v2OddsNaoEnfrentouAposta", motivoCurto: "card.v2OddsNaoEnfrentouApostaCurto" } },
    });
    expect(txt()).toContain("card.v2OddsNaoEnfrentouApostaCurto");
    expect(txt(), "o EV e a equity tem de continuar").toContain("0.30bb");
    expect(txt()).toContain("61.0%");
  });

  it("MULTIWAY: o titulo da estrategia diz que NAO e o solver", () => {
    // O solver e heads-up e nao resolve 3-way+. Mostrar barras sob o titulo "Estrategia do
    // Solver" num pote multiway seria atribuir ao solver uma resposta que nao e dele.
    montar({
      source: fonte("Multiway", "multiway"),
      estrategiaTitulo: "card.mwTitle",
      estrategia: [{ acao: "fold", freq: 0.7, jogada: true }, { acao: "call", freq: 0.3 }],
    });
    expect(txt()).toContain("card.mwTitle");
    expect(txt(), "atribuiu ao solver uma resposta que nao e dele")
      .not.toContain("card.solverStrategy");
  });
});

describe("card v2 — o que o layout enxuto NAO pode perder", () => {
  it("o slot de preco RENDERIZA o rotulo alternativo quando o significado muda", () => {
    // O mapeamento ja devolvia `rotulo: "card.reqMinEv"` para quem apostou, e o componente
    // ignorava — a mutacao "o rotulo alternativo e ignorado" sobrevivia porque nenhum teste de
    // COMPONENTE exercitava o campo. Regra pura testada nao cobre a tela que a consome.
    montar({
      playedAction: "raise",
      metricas: { evPerdido: { valor: "0.30bb" }, equity: { valor: "55.3%" },
                  potOdds: { valor: "18%", rotulo: "card.reqMinEv" } },
    });
    expect(txt(), "o rotulo alternativo nao apareceu").toContain("card.reqMinEv");
    expect(txt(), "manteve o rotulo padrao junto, e ai sao dois nomes para um slot")
      .not.toContain("card.v2PotOdds");
  });

  it("a FONTE do veredito fica sempre visivel", () => {
    // O exemplo que originou o pedido escrevia so "PRE-FLOP", que e a street. Com 1.565
    // decisoes sem gabarito, o card tem de declarar de ONDE veio o veredito.
    montar({ source: fonte("Heurística", "heuristic"), contexto: "PRÉ-FLOP" });
    expect(txt()).toContain("Heurística");
    expect(txt(), "o contexto tambem cabe, mas nao substitui a fonte").toContain("PRÉ-FLOP");
  });

  it("nao repete a acao quando os dois concordam", () => {
    // A redundancia que este layout existe para cortar: o exemplo mostrava o mesmo 62% em tres
    // lugares. Concordando, "GTO recomenda" ao lado de "voce jogou" e a mesma palavra duas vezes.
    montar({ playedAction: "call", idealAction: "call", isActionOk: true });
    expect(txt()).not.toContain("card.gtoRecommends");

    cleanup();
    // CONTROLE: divergindo, as duas colunas aparecem — sem isto o teste passaria com a coluna
    // removida de vez.
    montar({ playedAction: "fold", idealAction: "call", isActionOk: false });
    expect(txt()).toContain("card.gtoRecommends");
  });

  it("a frase e sempre visivel; a auditoria fica atras do olho", () => {
    montar({
      frase: "Call é a linha principal.",
      detalhes: <span>SPR 3.0 · sizing 33%</span>,
      showDetails: false,
    });
    expect(txt(), "a leitura tem de estar sempre visivel").toContain("Call é a linha principal.");
    expect(txt(), "a auditoria vazou para fora do olho").not.toContain("SPR 3.0");

    cleanup();
    montar({
      frase: "Call é a linha principal.",
      detalhes: <span>SPR 3.0 · sizing 33%</span>,
      showDetails: true,
    });
    expect(txt(), "o olho aberto nao mostrou a auditoria").toContain("SPR 3.0");
  });

  it("marca a acao JOGADA na barra em vez de repeti-la em texto", () => {
    montar({
      estrategia: [{ acao: "call", freq: 0.62, jogada: true },
                   { acao: "raise", freq: 0.33 }, { acao: "fold", freq: 0.05 }],
    });
    expect(txt()).toContain("62%");
    expect(txt()).toContain("33%");
    expect(txt()).toContain("5%");
    // A marca da acao jogada e um ponto na barra, nao uma linha "GTO: 62% de frequencia" a parte.
    expect(txt()).toContain("CALL •");
  });
});
