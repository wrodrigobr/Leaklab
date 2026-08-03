// @vitest-environment jsdom
/**
 * Modo grind: a mão real inteira, e as coisas que a tela não pode fazer.
 *
 * 1. **Passo sem gabarito NÃO vira "errou".** O backend devolve `sem_veredito` e a tela tem que
 *    dizer isso em vez de pontuar contra o jogador. Inventar veredito aqui seria o defeito que o
 *    Ghost Table levou um dia inteiro para tirar.
 * 2. **A decisão sem gabarito fica FORA do denominador.** Contar "2/3" quando um dos três não tinha
 *    resposta pune o jogador por uma lacuna nossa.
 * 3. **A tela diz que é REPLAY.** O board e as cartas do vilão já estão decididos; omitir isso
 *    venderia simulação.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const estado = vi.hoisted(() => ({
  mao: null as unknown,
  respostas: [] as Array<{ resultado: unknown; sem_veredito: boolean }>,
  i: 0,
}));

vi.mock("@/lib/api", () => ({
  grind: {
    hand: () => Promise.resolve({ mao: estado.mao, esgotou: estado.mao === null }),
    grade: () => Promise.resolve(estado.respostas[estado.i++] ?? { resultado: null, sem_veredito: true }),
  },
}));
vi.mock("@/components/hud/HudHeader", () => ({ HudHeader: () => <div data-testid="hud" /> }));
vi.mock("@/components/hud/PokerTableV3", () => ({ PokerTableV3: () => <div data-testid="mesa" /> }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, o?: unknown) => (typeof o === "string" ? o : k),
                           i18n: { language: "pt-BR" } }),
}));

import Grind from "./Grind";

const passo = (street: string, facing = 0) => ({
  street, board: street === "preflop" ? [] : ["3h", "2d", "6d"],
  hero_hand: ["Js", "Td"], position: "BB", vs_position: "BTN",
  stack_bb: 40, pot_bb: 4, facing_size_bb: facing,
  options: facing > 0 ? ["fold", "call", "raise"] : ["check", "bet"],
  tree_hash: "t1", vilao_antes: null,
});

function montar() {
  return render(<MemoryRouter><Grind /></MemoryRouter>);
}

afterEach(() => { cleanup(); estado.i = 0; estado.respostas = []; estado.mao = null; });

describe("modo grind", () => {
  it("passo sem gabarito não vira erro: diz que não conta", async () => {
    estado.mao = { token: "abc", total: 1, passos: [passo("flop")] };
    estado.respostas = [{ resultado: null, sem_veredito: true }];
    montar();
    await waitFor(() => expect(screen.getByText("check")).toBeTruthy());
    fireEvent.click(screen.getByText("check"));
    await waitFor(() => expect(screen.getByText("grind.noVerdict")).toBeTruthy());
    expect(screen.queryByText("grind.wrong")).toBeNull();
  });

  it("a decisão sem gabarito fica fora do denominador da nota", async () => {
    estado.mao = { token: "abc", total: 2, passos: [passo("flop"), passo("turn")] };
    estado.respostas = [
      { resultado: { is_correct: true, gto_tier: "correct", gto_strategy: [] }, sem_veredito: false },
      { resultado: null, sem_veredito: true },
    ];
    montar();
    await waitFor(() => expect(screen.getByText("check")).toBeTruthy());
    fireEvent.click(screen.getByText("check"));
    await waitFor(() => expect(screen.getByText("grind.next")).toBeTruthy());
    fireEvent.click(screen.getByText("grind.next"));
    await waitFor(() => expect(screen.getByText("check")).toBeTruthy());
    fireEvent.click(screen.getByText("check"));
    await waitFor(() => expect(screen.getByText("grind.finishHand")).toBeTruthy());
    fireEvent.click(screen.getByText("grind.finishHand"));
    // 1 acerto em 1 CONTADA, não em 2 respondidas
    await waitFor(() => expect(screen.getByText("1/1")).toBeTruthy());
  });

  it("sem vilão definido, a tela não escreve 'vs' nem anuncia pote zero", async () => {
    // Reportado: "UTG+1 vs unknown ... pote 0bb" numa abertura, onde ainda não existe adversário.
    // Pote 0 é ausência de dado, não um pote de zero fichas.
    estado.mao = { token: "abc", total: 1, passos: [{
      ...passo("preflop"), position: "UTG+1", vs_position: "", pot_bb: 0,
      options: ["fold", "raise"],
    }] };
    const { container } = montar();
    await waitFor(() => expect(screen.getByText("UTG+1")).toBeTruthy());
    const texto = container.textContent ?? "";
    expect(texto).not.toContain("UTG+1 vs");   // não inventa adversário
    // O RÓTULO do pote não pode aparecer. Checar a string "0bb" era impreciso: o stack de 40bb
    // contém "0bb" como substring, e o teste falhava com o código certo.
    expect(texto).not.toContain("grind.pot");  // pote ausente não vira pote de zero
  });

  it("a tela nao rola: a casca tem a altura da viewport e a mesa cresce com ela", async () => {
    // Reportado: "temos que aproveitar melhor o espaço da tela e evitar barras de rolagem... quanto
    // maior a mesa melhor". A mesa estava travada em `max-w-3xl` (768px) no meio de uma tela de
    // 1600, com o cabeçalho grande empurrando tudo. Agora a casca é `h-dvh overflow-hidden` e a
    // mesa é dimensionada pela ALTURA que sobra, com a largura saindo da proporção.
    estado.mao = { token: "abc", total: 1, passos: [passo("flop")] };
    const { container } = montar();
    await waitFor(() => expect(screen.getByTestId("mesa")).toBeTruthy());
    const casca = container.querySelector(".h-dvh");
    expect(casca, "a casca não tem altura de viewport").not.toBeNull();
    expect(casca?.className).toContain("overflow-hidden");
    // a mesa deriva a largura da ALTURA, e não o contrário
    const alvo = container.querySelector('[class*="aspect-"]');
    expect(alvo?.className).toContain("h-full");
    expect(alvo?.className).toContain("w-auto");
    expect(alvo?.className ?? "").not.toContain("max-w-3xl");
  });

  it("a fita mostra cada STREET uma vez, e nao 'flop, flop'", async () => {
    // Reportado: "em cima tem preflop, flop, flop". Uma street pode ter DUAS decisões (check e
    // depois enfrentar a aposta); listar passo a passo escrevia a street repetida, o que se lê como
    // erro em vez de "duas decisões no mesmo flop".
    estado.mao = { token: "abc", total: 3, passos: [
      passo("preflop"), passo("flop"), passo("flop", 1.9),
    ] };
    const { container } = montar();
    await waitFor(() => expect(screen.getByTestId("mesa")).toBeTruthy());
    const fita = container.textContent ?? "";
    // "flop" aparece uma vez só na fita (a contagem "1/2" indica as duas decisões)
    const chips = [...container.querySelectorAll("span")]
      .map((e) => e.textContent ?? "").filter((x) => x.startsWith("grind.street."));
    const nomes = chips.map((c) => c.replace(/[^a-z.]/g, ""));
    expect(new Set(nomes).size).toBe(nomes.length);   // sem street repetida
    // A street com DUAS decisões anuncia isso. Estando no preflop, ela mostra a contagem (`·2`);
    // quando você chega nela, passa a mostrar em qual das duas está (`1/2`).
    expect(fita).toMatch(/·2|1\/2/);
  });

  it("os botões de ação ficam centralizados, sem esticar pela tela", async () => {
    estado.mao = { token: "abc", total: 1, passos: [passo("flop")] };
    const { container } = montar();
    await waitFor(() => expect(screen.getByText("check")).toBeTruthy());
    const grupo = screen.getByText("check").parentElement;
    expect(grupo?.className).toContain("justify-center");
    expect(grupo?.className).toContain("mx-auto");
    expect(grupo?.className).toContain("max-w-2xl");
  });

  it("sem saber quem é o adversário, a mesa NÃO dobra ninguém", async () => {
    // Reportado duas vezes: "não aparece quais jogadores estão na jogada" e "aqui também não tem
    // ninguém na mão". A regra anterior deduzia "quem agiu antes do herói foldou", e com o herói no
    // BB isso apagava os oito outros assentos. Dobrar todo mundo é uma AFIRMAÇÃO — "todos passaram"
    // — e era falsa: a mão seguia para o flop.
    estado.mao = { token: "abc", total: 1, passos: [{
      ...passo("preflop"), position: "BB", vs_position: "", options: ["fold", "raise"],
    }] };
    const { container } = montar();
    await waitFor(() => expect(screen.getByTestId("mesa")).toBeTruthy());
    expect(container.querySelector("[data-folded]")?.getAttribute("data-folded")).toBe("0");
  });

  it("com adversário conhecido, sobra o par na mesa", async () => {
    estado.mao = { token: "abc", total: 1, passos: [{ ...passo("flop"), position: "BB", vs_position: "BTN" }] };
    const { container } = montar();
    await waitFor(() => expect(screen.getByTestId("mesa")).toBeTruthy());
    // 9 assentos, 2 na mão → 7 dobrados
    expect(container.querySelector("[data-folded]")?.getAttribute("data-folded")).toBe("7");
  });

  it("sem mão disponível, não fica em branco", async () => {
    estado.mao = null;
    montar();
    await waitFor(() => expect(screen.getByText("grind.empty.title")).toBeTruthy());
  });
});
