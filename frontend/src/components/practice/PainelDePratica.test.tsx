// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
  }),
}));

import { PainelDePratica, aoClicarNaPosicao } from "./PainelDePratica";
import { CONFIG_PADRAO, POSICOES_DISPONIVEIS, STATS_ZERO, type ConfigPratica } from "@/lib/pratica";

/**
 * O painel de configuração do Prática.
 *
 * ── Por que ele ganhou teste agora (17/09) ────────────────────────────────────────────────────
 *
 * Ele não tinha nenhum, nem o filtro de stack que já existia. O painel é VITRINE, e a casa tem a
 * cicatriz de bug de vitrine escapando: o que o jogador clica é onde o defeito aparece primeiro e
 * é onde ninguém está olhando.
 *
 * O filtro de posição nasceu de um pedido do Rullian, trazido pelo dono: "a escolha de uma posição
 * específica para o treino. podemos deixar todas selecionadas, ou escolher uma única posição,
 * assim como é feito com o stack".
 */

function monta(config: ConfigPratica = CONFIG_PADRAO, onConfig = vi.fn()) {
  render(<PainelDePratica aberto config={config} pendente={null} stats={STATS_ZERO}
                          tetoDeMesas={4} onConfig={onConfig}
                          onAlternar={() => {}} onAplicar={() => {}} />);
  return onConfig;
}

describe("o filtro de posicao do painel", () => {
  afterEach(cleanup);

  it("comeca com as NOVE marcadas", () => {
    monta();
    for (const pos of POSICOES_DISPONIVEIS) {
      expect(screen.getByTestId(`pratica-posicao-${pos}`).getAttribute("aria-pressed"),
             `${pos} devia comecar marcada`).toBe("true");
    }
    // e sem o atalho "todas", que ja e o estado
    expect(screen.queryByTestId("pratica-posicao-todas")).toBeNull();
  });

  it("de TODAS, um clique deixa SO aquela posicao", () => {
    // O pedido nomeia dois estados: todas, ou uma. Com liga/desliga puro, sair de todas para so o
    // BTN custaria OITO cliques -- e nenhum jogador faz isso.
    const onConfig = monta();
    fireEvent.click(screen.getByTestId("pratica-posicao-BTN"));
    expect(onConfig).toHaveBeenCalledTimes(1);
    expect(onConfig.mock.calls[0][0].posicoes).toEqual(["BTN"]);
  });

  it("com uma escolhida, o clique volta a ser liga/desliga, e o 'todas' desfaz", () => {
    const onConfig = monta({ ...CONFIG_PADRAO, posicoes: ["BTN"] });
    fireEvent.click(screen.getByTestId("pratica-posicao-CO"));
    expect(onConfig.mock.calls[0][0].posicoes, "o segundo clique tem de SOMAR")
      .toEqual(["CO", "BTN"]);   // ordem de acao, e nao de clique

    fireEvent.click(screen.getByTestId("pratica-posicao-todas"));
    expect(onConfig.mock.calls[1][0].posicoes).toEqual([...POSICOES_DISPONIVEIS]);
  });
});

describe("a regra do clique na posicao", () => {
  const TODAS = [...POSICOES_DISPONIVEIS];

  it("de todas, seleciona uma so", () => {
    expect(aoClicarNaPosicao(TODAS, "SB")).toEqual(["SB"]);
  });

  it("some na ORDEM DE ACAO, e nao na ordem dos cliques", () => {
    // Duas listas com as mesmas posicoes em ordens diferentes fariam `mudaOSorteio` dizer que o
    // sorteio mudou quando nada mudou, e o painel mostraria "aplica na proxima rodada" sem motivo.
    expect(aoClicarNaPosicao(["BTN"], "UTG")).toEqual(["UTG", "BTN"]);
    expect(aoClicarNaPosicao(["UTG", "BTN"], "CO")).toEqual(["UTG", "CO", "BTN"]);
  });

  it("tira quando ja esta marcada", () => {
    expect(aoClicarNaPosicao(["UTG", "CO", "BTN"], "CO")).toEqual(["UTG", "BTN"]);
  });

  it("NUNCA deixa a lista vazia", () => {
    // Sem posicao nenhuma o sorteio nao tem de onde tirar mesa, e a tela ficaria pedindo mesas que
    // nunca chegam -- um estado sem saida, porque o proprio filtro seria o que impede a mesa.
    expect(aoClicarNaPosicao(["BTN"], "BTN")).toEqual(["BTN"]);
  });
});
