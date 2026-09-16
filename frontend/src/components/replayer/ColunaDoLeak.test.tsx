// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within, fireEvent, cleanup, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k}:${Object.values(o).join(",")}` : k,
  }),
}));
const evLeakHands = vi.fn();
const evSummary = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, metrics: { ...real.metrics,
    evLeakHands: (...a: unknown[]) => evLeakHands(...a),
    evSummary: (...a: unknown[]) => evSummary(...a) } };
});

import { ColunaDoLeak } from "./ColunaDoLeak";

/**
 * A coluna com as mãos do leak, ao lado da mesa.
 *
 * ── O que ela precisa provar ──────────────────────────────────────────────────────────────────
 *
 * Que ela NÃO é o aside de 288px que removemos em 20/06. Aquele era fixo e encolhia a mesa em
 * toda mão, mesmo sem nada a mostrar. Esta só aparece com playlist de leak, é `absolute` no
 * contêiner da mesa (não empurra nada) e some no telefone, onde não há espaço ocioso.
 */

const MAO = (id: number, cartas: string, ev: number, tid: number) => ({
  decision_id: id, tournament_id: tid, tournament: "T", hand_id: `H${id}`,
  played_at: "2026-09-10", position: "HJ", hero_cards: cartas, board: "[]",
  stack_bb: 67, ev_loss_bb: ev, gto_label: "gto_critical", label: "clear_mistake",
});

// as quatro primeiras do leak real, com os torneios reais: elas ATRAVESSAM torneios
const HANDS = [MAO(1, "QhJd", 2.79, 18), MAO(2, "4dAd", 2.28, 2),
               MAO(3, "Kh7h", 1.82, 30), MAO(4, "3h3c", 1.66, 19)];

const SPOT = { street: "preflop", actionTaken: "call", bestAction: "fold" };

// a MESMA lista de 5 leaks que o card do dono mostra, na mesma ordem (por custo)
const LEAKS = [
  { street: "preflop", action_taken: "fold",  best_action: "call",  count: 46, loss_bb: 14.3, share_pct: 29 },
  { street: "preflop", action_taken: "call",  best_action: "fold",  count: 12, loss_bb: 12.2, share_pct: 25 },
  { street: "preflop", action_taken: "fold",  best_action: "raise", count: 19, loss_bb: 9.6,  share_pct: 19 },
  { street: "preflop", action_taken: "fold",  best_action: "jam",   count: 18, loss_bb: 8.1,  share_pct: 16 },
  { street: "preflop", action_taken: "shove", best_action: "fold",  count: 7,  loss_bb: 4.4,  share_pct: 9 },
];

function monta(handId = "H3") {
  const aoIr = vi.fn();
  const r = render(
    <ColunaDoLeak spot={SPOT} lastN={50} handId={handId}
                  hrefDaMao={(h) => `/replayer?h=${h}&leak=x`}
                  hrefEmOutroLeak={(mao, tid, chave) => `/replayer?t=${tid}&h=${mao}&leak=${chave}`}
                  aoIr={aoIr} />);
  return { aoIr, ...r };
}

describe("coluna do leak", () => {
  beforeEach(() => {
    localStorage.clear();
    evLeakHands.mockReset();
    evLeakHands.mockResolvedValue({
      total: 12, loss_bb: 12.2, limit: 200, offset: 0,
      street: SPOT.street, action_taken: SPOT.actionTaken, best_action: SPOT.bestAction,
      hands: HANDS,
    });
    evSummary.mockResolvedValue({ top_leaks: LEAKS });
  });

  // Sem isto o render do caso anterior fica no DOM e `findByTestId` acha dois.
  afterEach(cleanup);

  it("lista as mãos do leak com as cartas desenhadas, no mesmo recorte da lista", async () => {
    monta();
    const col = await screen.findByTestId("leak-coluna");
    // o `lastN` vai na chamada: a coluna responde pelo MESMO recorte do card que a gerou, senão
    // o "12" dela e o "12" do contador falariam de janelas diferentes
    expect(evLeakHands).toHaveBeenCalledWith("preflop", "call", "fold", 50, 200);
    const linha = within(col).getByTestId("leak-coluna-mao-2");
    // `4dAd` sai com o ás na frente — a ordenação mora em `HeroHand`
    expect(within(linha).getAllByRole("img").map((i) => i.getAttribute("alt"))).toEqual(["Ad", "4d"]);
    expect(linha.textContent).toContain("−2.28");
  });

  it("a linha mostra só cartas e custo, e o resto vai para o title", async () => {
    // Decisão do dono (16/09) depois de ver a coluna cobrindo o assento do BB na mesa: assento e
    // stack já estão NA MESA quando a mão está aberta, então na lista eram repetição ocupando a
    // largura que faltava. A coluna caiu de ~300px para ~150px.
    //
    // O guarda não mede pixel (jsdom não faz layout): ele trava o que ENCHE a linha. Se alguém
    // voltar a pôr assento e stack no texto, a largura volta a crescer atrás.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    const linha = within(col).getByTestId("leak-coluna-mao-2");
    expect(linha.textContent).toContain("−2.28");
    expect(linha.textContent).not.toContain("UTG");     // assento
    expect(linha.textContent).not.toContain("bb");      // stack
    // e a informação não se perdeu: está no title, para quem procura uma mão específica
    expect(linha.getAttribute("title")).toContain("HJ");
    expect(linha.getAttribute("title")).toContain("67bb");
  });

  it("marca a mão atual e apaga as que já passaram", async () => {
    monta("H3");
    const col = await screen.findByTestId("leak-coluna");
    const atual = within(col).getByTestId("leak-coluna-mao-3");
    expect(atual.getAttribute("aria-current")).toBe("true");
    // as duas de cima (mais caras, já revistas) ficam apagadas; a de baixo, não
    expect(within(col).getByTestId("leak-coluna-mao-1").className).toContain("opacity-45");
    expect(within(col).getByTestId("leak-coluna-mao-4").className).not.toContain("opacity-45");
  });

  it("clicar numa mão navega pelo MESMO href da navegação por setas", async () => {
    // Sem isto a coluna seria uma segunda forma de montar o link, e a que erra manda o jogador
    // para uma mão que não existe naquele torneio.
    const { aoIr } = monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByTestId("leak-coluna-mao-4"));
    expect(aoIr).toHaveBeenCalledWith("/replayer?h=H4&leak=x");
  });

  it("recolhe, lembra a escolha, e volta a abrir", async () => {
    monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByRole("button", { name: "close" }));
    expect(screen.queryByTestId("leak-coluna")).toBeNull();
    expect(localStorage.getItem("replayer_coluna_leak")).toBe("false");
    // recolhida, sobra o botão que diz quantas mãos esperam
    expect((await screen.findByTestId("leak-coluna-abrir")).textContent).toContain("12");
  });

  it("some inteira quando o leak não tem mão medida", async () => {
    // A régua da casa: sem dado o bloco SOME, nunca renderiza vazio fingindo informação.
    evLeakHands.mockResolvedValue({
      total: 0, loss_bb: 0, limit: 200, offset: 0,
      street: SPOT.street, action_taken: SPOT.actionTaken, best_action: SPOT.bestAction, hands: [],
    });
    monta();
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByTestId("leak-coluna")).toBeNull();
    expect(screen.queryByTestId("leak-coluna-abrir")).toBeNull();
  });

  it("diz QUAL leak está aberto e em que posição da lista do card", async () => {
    // O pedido do dono: "exibir o leak que está sendo tratado agora". O spot montado aqui é
    // `preflop call -> fold`, que é o SEGUNDO da lista, e o cabeçalho tem de dizer isso.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    expect(col.textContent).toContain("Call");
    expect(col.textContent).toContain("Fold");
    expect(col.textContent).toContain("navigation.leakDeN:2,5,12");   // leak 2 de 5, 12 mãos
  });

  it("o menu lista os MESMOS leaks do card, na mesma ordem, e marca o aberto", async () => {
    monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByTestId("leak-menu-toggle"));
    const menu = await screen.findByTestId("leak-menu");
    // 5 linhas, e a ordem é a do card (por custo)
    expect(within(menu).getByTestId("leak-menu-0").textContent).toContain("−14.3");
    expect(within(menu).getByTestId("leak-menu-4").textContent).toContain("−4.4");
    // o leak aberto não navega para si mesmo
    // jest-dom nao esta instalado neste projeto: a propriedade do DOM diz a mesma coisa
    expect((within(menu).getByTestId("leak-menu-1") as HTMLButtonElement).disabled).toBe(true);
    expect((within(menu).getByTestId("leak-menu-2") as HTMLButtonElement).disabled).toBe(false);
  });

  it("avançar vai para a PRIMEIRA mão do próximo leak", async () => {
    // Trocar de leak precisa de uma chamada extra, porque o replayer abre por MÃO e a playlist
    // do próximo leak é outra lista. A primeira mão é a mais cara, que é a ordem da lista.
    const { aoIr } = monta();
    const col = await screen.findByTestId("leak-coluna");
    evLeakHands.mockResolvedValue({
      total: 19, loss_bb: 9.6, limit: 1, offset: 0,
      street: "preflop", action_taken: "fold", best_action: "raise",
      hands: [MAO(99, "KsQs", 1.9, 77)],
    });
    fireEvent.click(within(col).getByTestId("leak-proximo"));
    await waitFor(() => expect(aoIr).toHaveBeenCalledWith(
      "/replayer?t=77&h=H99&leak=preflop:fold:raise"));
    // o próximo do SEGUNDO leak é o terceiro da lista, e não o quarto nem o primeiro
    expect(evLeakHands).toHaveBeenLastCalledWith("preflop", "fold", "raise", 50, 1);
  });

  it("no último leak o botão de avançar não existe", async () => {
    // Botão que não faz nada ensina o jogador a não confiar no botão.
    cleanup();
    const aoIr = vi.fn();
    render(<ColunaDoLeak spot={{ street: "preflop", actionTaken: "shove", bestAction: "fold" }}
                         lastN={50} handId="H3" hrefDaMao={(h) => `/x?h=${h}`}
                         hrefEmOutroLeak={() => "/x"} aoIr={aoIr} />);
    await screen.findByTestId("leak-coluna");
    expect(screen.queryByTestId("leak-proximo")).toBeNull();
  });

  it("não empurra a mesa: é absolute e só aparece no desktop", async () => {
    // O que separa esta coluna do aside de 288px removido em 20/06. `absolute` não participa do
    // fluxo, então a mesa mantém a largura; `hidden lg:flex` a tira do telefone, onde não há
    // espaço ocioso para ocupar.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    expect(col.className).toContain("absolute");
    expect(col.className).toContain("hidden");
    expect(col.className).toContain("lg:flex");
    // LADO ESQUERDO (pedido do dono, 16/09). O lado importa para o botao de reabrir aparecer
    // onde a coluna abre: quando ela estava a direita e o botao ficou a esquerda numa versao
    // intermediaria, o jogador clicava num canto e a lista aparecia no outro.
    expect(col.className).toContain("left-0");
    expect(col.className).not.toContain("right-0");
  });

  it("o botao de reabrir nasce do MESMO lado da coluna", async () => {
    monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByRole("button", { name: "close" }));
    const botao = await screen.findByTestId("leak-coluna-abrir");
    expect(botao.className).toContain("left-2");
    expect(botao.className).not.toContain("right-2");
  });
});
