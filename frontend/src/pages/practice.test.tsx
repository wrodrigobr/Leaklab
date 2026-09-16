// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
  }),
}));

const tables = vi.fn();
const grade = vi.fn();
const evSummary = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return {
    ...real,
    practice: { tables: (...a: unknown[]) => tables(...a), grade: (...a: unknown[]) => grade(...a) },
    metrics: { ...real.metrics, evSummary: (...a: unknown[]) => evSummary(...a) },
  };
});

import { CONFIG_PADRAO } from "@/lib/pratica";
import Practice from "./Practice";

/**
 * A tela do modo Prática.
 *
 * ── O que ela precisa provar ──────────────────────────────────────────────────────────────────
 *
 * Três comportamentos que só existem com mais de uma mesa, e que a lógica pura de `lib/pratica`
 * não alcança porque dependem da orquestração:
 *
 * 1. A tecla age na mesa com FOCO, e só nela. Quatro mesas com a mesma letra ativa em todas é o
 *    defeito que transformaria o teclado numa armadilha.
 * 2. Uma resposta não conta duas vezes. Dois cliques rápidos na mesma mesa mandariam duas
 *    correções, e o placar da sessão contaria a mão duas vezes.
 * 3. Mudar a configuração fica PENDENTE em vez de descartar as mesas em jogo -- o conserto do que
 *    o GTO Wizard faz ao reiniciar a sessão.
 */

const SPOT = (pos: string, hand: string, stack: number, cenario = "rfi") => ({
  position: pos, vs_position: "", stack_bb: stack, facing_size: 0, is_3bet_pot: false,
  hand, scenario: cenario, hero_was_aggressor: false, facing_raises: 0,
});

const MESA = (id: string, pos: string, hand: string, stack: number) => ({
  id, spot: SPOT(pos, hand, stack), scenario: "rfi", context: `ctx ${pos}`, hand,
  hero_cards: [{ rank: hand[0], suit: "s" }, { rank: hand[1], suit: "h" }],
  options: [{ action: "fold", label: "Fold" }, { action: "raise", label: "Raise 2" },
            { action: "allin", label: `All-in ${stack}` }],
  xp_value: 20,
  table: {
    seats: [
      { seat: 1, name: "UTG", stack: 2000, bet: 0, folded: true, active: false, hero: false, pos: "UTG" },
      { seat: 7, name: "Hero", stack: 2000, bet: 0, folded: false, active: true, hero: true, pos: pos },
      { seat: 8, name: "SB", stack: 1950, bet: 50, folded: false, active: true, hero: false, pos: "SB" },
      { seat: 9, name: "BB", stack: 1900, bet: 100, folded: false, active: true, hero: false, pos: "BB" },
    ],
    button: 7, pot: 150, bb_chips: 100, street: "preflop", board: [], hero_cards: hand,
  },
});

const QUATRO = [MESA("m1", "BTN", "K7s", 12), MESA("m2", "CO", "33", 40),
                MESA("m3", "SB", "A7s", 19), MESA("m4", "HJ", "QJs", 80)];

function monta() {
  return render(<MemoryRouter initialEntries={["/practice"]}><Practice /></MemoryRouter>);
}

describe("modo Pratica", () => {
  beforeEach(() => {
    localStorage.clear();
    tables.mockReset(); grade.mockReset(); evSummary.mockReset();
    tables.mockResolvedValue({ tables: QUATRO, pedidas: 4, servidas: 4 });
    grade.mockResolvedValue({ is_correct: true, action_quality: "correct",
                              hand_freq: { F: 0.8, R2: 0.2 }, ev_loss_bb: null, xp_awarded: 20 });
    evSummary.mockResolvedValue({ top_leaks: [] });
  });
  afterEach(cleanup);

  it("abre as quatro mesas, e a primeira tem o foco", async () => {
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    for (const id of ["m1", "m2", "m3", "m4"]) expect(screen.getByTestId(`pratica-mesa-${id}`)).toBeTruthy();
    expect(screen.getByTestId("pratica-mesa-m1").getAttribute("data-foco")).toBe("1");
    expect(screen.getByTestId("pratica-mesa-m2").getAttribute("data-foco")).toBe("0");
  });

  it("a tecla age na mesa com FOCO, e so nela", async () => {
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    fireEvent.keyDown(window, { key: "f" });
    await waitFor(() => expect(grade).toHaveBeenCalledTimes(1));
    // a mao corrigida e a da mesa 1, nao a de outra
    expect(grade.mock.calls[0][0].hand).toBe("K7s");
    expect(grade.mock.calls[0][1]).toBe("fold");
  });

  it("Tab move o foco, e a tecla passa a agir na mesa nova", async () => {
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    fireEvent.keyDown(window, { key: "Tab" });
    await waitFor(() =>
      expect(screen.getByTestId("pratica-mesa-m2").getAttribute("data-foco")).toBe("1"));
    fireEvent.keyDown(window, { key: "a" });
    await waitFor(() => expect(grade).toHaveBeenCalledTimes(1));
    expect(grade.mock.calls[0][0].hand).toBe("33");
    expect(grade.mock.calls[0][1]).toBe("allin");
  });

  it("tecla que a mesa NAO oferece nao manda nada", async () => {
    tables.mockResolvedValue({
      tables: [{ ...QUATRO[0], options: [{ action: "fold", label: "Fold" },
                                         { action: "call", label: "Call" }] }],
      pedidas: 1, servidas: 1,
    });
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    fireEvent.keyDown(window, { key: "r" });      // esta mesa nao tem raise
    fireEvent.keyDown(window, { key: "a" });      // nem all-in
    await new Promise((r) => setTimeout(r, 30));
    expect(grade).not.toHaveBeenCalled();
  });

  it("a MESMA mesa nao e corrigida duas vezes", async () => {
    // Sem a trava, dois cliques rapidos mandariam duas correcoes e o placar contaria a mao duas
    // vezes -- o percentual da sessao mentindo com o proprio dado.
    monta();
    const m1 = await screen.findByTestId("pratica-mesa-m1");
    const fold = within(m1).getByTestId("pratica-acao-fold");
    fireEvent.click(fold);
    fireEvent.click(fold);
    fireEvent.keyDown(window, { key: "f" });
    await waitFor(() => expect(grade).toHaveBeenCalledTimes(1));
  });

  it("mudar o numero de mesas fica PENDENTE, sem descartar as em jogo", async () => {
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    expect(tables).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("pratica-mesas-2"));
    // o aviso aparece, as quatro mesas continuam na tela, e NENHUMA rodada nova foi pedida
    expect(screen.getByTestId("pratica-pendente")).toBeTruthy();
    expect(screen.getByTestId("pratica-mesa-m4")).toBeTruthy();
    expect(tables).toHaveBeenCalledTimes(1);
  });

  it("mudar a PAUSA aplica na hora, sem pendencia", async () => {
    // Ela nao muda o sorteio: so decide quando a tela espera o jogador.
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    fireEvent.click(screen.getByTestId("pratica-pausa-nunca"));
    expect(screen.queryByTestId("pratica-pendente")).toBeNull();
    expect(tables).toHaveBeenCalledTimes(1);
  });

  it("o veredito aparece na mesa respondida, e nao como modal", async () => {
    monta();
    const m1 = await screen.findByTestId("pratica-mesa-m1");
    fireEvent.click(within(m1).getByTestId("pratica-acao-fold"));
    const v = await within(m1).findByTestId("pratica-veredito");
    // fold com 80% de F no hand_freq: melhor jogada
    expect(v.textContent).toContain("nivel.melhor");
  });

  it("depois do veredito, o spot novo entra SO naquela mesa", async () => {
    // O pedido do dono (16/09): "sempre que eu tomar uma acao em uma mesa, precisamos dar o
    // alerta do veredito, mas apos 2 segundos, um novo spot tem que ser carregado nesta mesa".
    //
    // O desenho anterior esperava as QUATRO responderem para girar a rodada inteira, e isso
    // fazia o jogador parar na mesa mais lenta -- o oposto do que quatro mesas resolvem. Trocar
    // o modelo nao quebrou nenhum teste, o que e o sinal de que ele nao estava coberto.
    vi.useFakeTimers();
    try {
      monta();
      await vi.waitFor(() => expect(screen.getByTestId("pratica-mesa-m1")).toBeTruthy());

      const m1 = screen.getByTestId("pratica-mesa-m1");
      fireEvent.click(within(m1).getByTestId("pratica-acao-fold"));
      await vi.waitFor(() => expect(grade).toHaveBeenCalledTimes(1));

      // o veredito aparece e a mesa CONTINUA na tela: o jogador precisa lê-lo
      await vi.waitFor(() => expect(within(screen.getByTestId("pratica-mesa-m1"))
        .getByTestId("pratica-veredito")).toBeTruthy());
      expect(tables).toHaveBeenCalledTimes(1);

      // o servidor passa a devolver um spot diferente para a troca
      tables.mockResolvedValue({ tables: [MESA("m9", "BTN", "72o", 10)], pedidas: 1, servidas: 1 });
      await vi.advanceTimersByTimeAsync(2100);

      // a mesa 1 virou o spot novo, e as outras tres NAO se mexeram
      await vi.waitFor(() => expect(screen.getByTestId("pratica-mesa-m9")).toBeTruthy());
      expect(screen.queryByTestId("pratica-mesa-m1")).toBeNull();
      for (const id of ["m2", "m3", "m4"]) expect(screen.getByTestId(`pratica-mesa-${id}`)).toBeTruthy();
      // e pediu UMA mesa, não a rodada inteira
      expect(tables.mock.calls[1][0]).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('a pausa em "acao" SEGURA a mesa, e o continuar solta', async () => {
    vi.useFakeTimers();
    try {
      render(<MemoryRouter initialEntries={["/practice?pausa=acao"]}><Practice /></MemoryRouter>);
      await vi.waitFor(() => expect(screen.getByTestId("pratica-mesa-m1")).toBeTruthy());

      fireEvent.click(within(screen.getByTestId("pratica-mesa-m1")).getByTestId("pratica-acao-fold"));
      await vi.waitFor(() => expect(grade).toHaveBeenCalledTimes(1));

      // passou muito mais que os 2s e a mesa NAO trocou: quem solta e o jogador
      await vi.advanceTimersByTimeAsync(5000);
      expect(screen.getByTestId("pratica-mesa-m1")).toBeTruthy();
      expect(tables).toHaveBeenCalledTimes(1);

      tables.mockResolvedValue({ tables: [MESA("m9", "BTN", "72o", 10)], pedidas: 1, servidas: 1 });
      fireEvent.click(screen.getByTestId("pratica-continuar"));
      await vi.advanceTimersByTimeAsync(2100);
      await vi.waitFor(() => expect(screen.getByTestId("pratica-mesa-m9")).toBeTruthy());
    } finally {
      vi.useRealTimers();
    }
  });

  it("a unidade da mesa e BB por padrao, e o padrao tem UMA fonte", async () => {
    // A primeira versao deste guarda passou VERDE com o padrao invertido na lib, e o controle da
    // quebra pegou: a pagina tinha "bb" num literal proprio, entao havia duas fontes para a
    // mesma decisao e a da pagina ganhava sempre. Este assert amarra as duas.
    expect(CONFIG_PADRAO.unidade).toBe("bb");
    // A cicatriz mais recorrente do projeto e "fichas vs BB", e a regua do produto e BB: o
    // solver, os leaks, o EV e o ELO todos falam nela. Mesa em fichas obrigaria o jogador a
    // converter de cabeca para ligar o que ve ao que o veredito diz.
    monta();
    const m1 = await screen.findByTestId("pratica-mesa-m1");
    // o cabecalho da mesa mostra o stack em bb, e nao 1.200 fichas
    expect(m1.textContent).toContain("12bb");
    expect(m1.textContent).not.toContain("1.200");
  });

  it("em fichas, a MESMA mesa mostra o stack convertido", async () => {
    // O controle do caso acima: sem ele, um seletor quebrado que ignora a escolha passaria
    // verde, porque BB e o padrao.
    render(<MemoryRouter initialEntries={["/practice?un=fichas"]}><Practice /></MemoryRouter>);
    const m1 = await screen.findByTestId("pratica-mesa-m1");
    expect(m1.textContent).toContain("1.200");     // 12bb x 100 fichas
    expect(m1.textContent).not.toContain("12bb");
  });

  it("a grade das mesas NAO rola: ela e limitada pela altura", async () => {
    // Requisito do dono: "as 4 mesas tem que caber na tela do usuario, sem depender de barra de
    // rolagem". jsdom nao faz layout, entao o guarda trava a ESTRUTURA que garante isso: a faixa
    // e overflow-hidden e a grade declara as linhas (sem linhas, o grid usa a altura do
    // conteudo e volta a estourar).
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    const grade = document.querySelector('[class*="grid-rows-2"]');
    expect(grade, "a grade de 4 mesas precisa declarar as linhas").toBeTruthy();
    expect(grade!.className).toContain("h-full");
    const faixa = grade!.parentElement!;
    expect(faixa.className).toContain("overflow-hidden");
    expect(faixa.className).not.toContain("overflow-y-auto");
  });

  it("sem spot para o filtro, a tela DIZ, em vez de piscar vazio", async () => {
    tables.mockResolvedValue({ tables: [], pedidas: 4, servidas: 0 });
    monta();
    expect(await screen.findByText("semSpot.titulo")).toBeTruthy();
  });

  it("o servidor recebe os spots JA VISTOS, para nao repetir", async () => {
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    // a primeira chamada nao tem o que evitar; o que importa e o parametro existir e ser lista
    expect(Array.isArray(tables.mock.calls[0][1].evitar)).toBe(true);
    expect(tables.mock.calls[0][0]).toBe(4);
  });
});
