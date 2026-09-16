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

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { rotuloDoLeak } from "@/lib/playlistDoLeak";
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
    // A MESMA leitura do cabeçalho do replayer. O texto não coincide caractere a caractere de
    // propósito: aqui a street cai numa segunda linha (`block`) para a coluna caber em 150px,
    // enquanto no cabeçalho ela vem na mesma linha depois de um "·". O que TEM de coincidir é a
    // ordem, porque ela carrega o sentido do leak: "Call → Fold" é pagar onde o certo era
    // foldar, e invertida a mesma frase acusa o oposto sem parecer defeito.
    const rotulo = rotuloDoLeak({ street: "preflop", actionTaken: "call", bestAction: "fold" });
    const txt = col.textContent ?? "";
    const partes = rotulo.split(" · ")[0].split(" → ");          // ["Call", "Fold"]
    expect(txt).toContain(partes[0]);
    expect(txt).toContain("preflop");
    expect(txt.indexOf(partes[0]), "a jogada FEITA vem antes da indicada")
      .toBeLessThan(txt.indexOf(partes[1]));
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

  it("é painel LATERAL no fluxo, e só aparece no desktop", async () => {
    // O dono pediu menu lateral com toggle em vez de janela flutuante (16/09). Então o painel
    // agora participa do fluxo de propósito, e o guarda mudou de alvo: ele protege o que torna
    // isso seguro, e não mais a flutuação.
    //
    // A cicatriz que continua valendo é a do aside de 288px removido em 20/06, e ela tinha DUAS
    // partes: largura reservada em toda mão, e nenhuma forma de recolher. O teste a seguir trava
    // as duas (`shrink-0` com largura limitada aqui, aba de 36px no caso de baixo).
    monta();
    const col = await screen.findByTestId("leak-coluna");
    expect(col.className).toContain("shrink-0");
    expect(col.className).toContain("hidden");
    expect(col.className).toContain("lg:flex");
    // não volta a flutuar por descuido: `absolute` aqui sobreporia o feltro outra vez
    expect(col.className).not.toContain("absolute");
    // e a largura tem teto: o aside antigo cravava 288px, este não passa de 190
    expect(col.className).toMatch(/w-\[clamp\(\d+px,[^)]+,(1[0-9]{2})px\)\]/);
  });

  it("o painel COLA na borda, sem ser CORTADO pela faixa da mesa", async () => {
    // O dono, vendo o painel a 20px da borda: "por que estamos com esta margem à esquerda da
    // página? é área útil". A margem não era do painel: é o `px-3 md:px-5` do wrapper da página
    // inteira, mais o `max-w-[1600px] mx-auto` que centraliza no monitor largo.
    //
    // A primeira tentativa pôs margem negativa NO PAINEL, e ela quebrou de um jeito pior que o
    // defeito original: a faixa da mesa é `overflow-hidden`, então o painel saiu do pai e perdeu
    // 20px de conteúdo pela esquerda -- "FOLD → CALL" virou "OLD → CALL", "MÃOS" virou "ÃOS", e
    // as cartas apareceram cortadas. Quem desloca é a coluna da mesa, um nível ACIMA do corte.
    //
    // Este guarda trava as duas pontas: o painel não volta a ter margem negativa (senão soma com
    // a de cima e corta de novo), e o negativo da coluna bate com o padding da página.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    expect(col.className, "margem negativa no painel volta a ser cortada pelo overflow-hidden")
      .not.toMatch(/-ml-\d/);

    const replayer = readFileSync(
      join(import.meta.dirname, "..", "..", "pages", "Replayer.tsx"), "utf-8");
    const pad = replayer.match(/"flex-1 min-h-0 flex flex-col px-(\d+) md:px-(\d+)/);
    expect(pad, "o wrapper da pagina mudou de forma: reveja o deslocamento da coluna").toBeTruthy();
    const neg = replayer.match(/leakSpot && "-ml-(\d+) md:-ml-(\d+)"/);
    expect(neg, "a coluna da mesa precisa sair do padding quando ha playlist").toBeTruthy();
    expect(neg?.[1]).toBe(pad?.[1]);
    expect(neg?.[2]).toBe(pad?.[2]);

    // E a moldura de largura maxima: ela centraliza a pagina no monitor largo, e a margem
    // negativa nao alcanca esse centramento. Com `?leak=` a pagina tem de soltar a moldura,
    // senao o conserto so funciona em tela de ate 1600px e "arrumado" seria meia verdade.
    expect(replayer, "com playlist aberta a pagina precisa soltar o max-w")
      .toMatch(/focusMode \|\| leakSpot \? "max-w-none"/);
  });

  it("a lista rola com a barra do TEMA, e nao a do sistema", async () => {
    // Pedido do dono (16/09): a barra nativa do Windows era uma faixa cinza clara sobre o fundo
    // escuro, a unica coisa da tela fora da paleta. `.scrollbar-hud` mora no `index.css` e usa
    // os TOKENS, entao trocar a paleta troca a barra junto.
    //
    // jsdom nao pinta scrollbar: o guarda trava a classe estar aplicada no elemento que ROLA, e
    // o teste abaixo confere que a classe existe de verdade no CSS.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    const rolavel = col.querySelector(".overflow-y-auto");
    expect(rolavel, "a lista de maos precisa ser o elemento que rola").toBeTruthy();
    expect(rolavel!.className).toContain("scrollbar-hud");
  });

  it("a classe da barra EXISTE no css, e usa os tokens do tema", async () => {
    // CONTROLE do guarda de cima: uma classe aplicada e nao definida nao pinta nada, e o teste
    // anterior passaria igual -- cobertura sem cobertura.
    const css = readFileSync(
      join(import.meta.dirname, "..", "..", "index.css"), "utf-8");
    expect(css).toContain(".scrollbar-hud");
    expect(css).toMatch(/scrollbar-hud::-webkit-scrollbar-thumb/);
    // tokens, nunca hex: hex aqui sobreviveria a uma troca de paleta e ficaria fora do tema
    const bloco = css.slice(css.indexOf(".scrollbar-hud"),
                            css.indexOf(".scrollbar-hud") + 1200);
    expect(bloco).toContain("hsl(var(--border))");
    expect(bloco).not.toMatch(/#[0-9a-fA-F]{6}/);
  });

  it("recolhido, o painel devolve a largura para a mesa", async () => {
    // O toggle é a razão pela qual um painel no fluxo é aceitável aqui. Se recolher só esconde o
    // conteúdo e mantém a coluna larga, voltamos ao aside de 20/06 com um botão decorativo.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByRole("button", { name: "close" }));
    expect(screen.queryByTestId("leak-coluna")).toBeNull();

    const aba = await screen.findByTestId("leak-coluna-fechada");
    expect(aba.className).toContain("w-9");          // 36px, a aba
    expect(aba.className).toContain("shrink-0");
    expect(aba.className).not.toMatch(/w-\[clamp/); // nada de largura de painel escondida aqui
    // e a aba continua dizendo quantas mãos esperam, senão o jogador esquece que há playlist
    expect((await screen.findByTestId("leak-coluna-abrir")).textContent).toContain("12");
  });
});
