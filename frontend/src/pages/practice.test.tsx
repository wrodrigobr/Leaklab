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
    comLargura(1440, 1000);          // desktop folgado: os casos gerais assumem quatro mesas
    localStorage.clear();
    tables.mockReset(); grade.mockReset(); evSummary.mockReset();
    tables.mockResolvedValue({ tables: QUATRO, pedidas: 4, servidas: 4 });
    // `nivel` vem do SERVIDOR desde 16/09: a regua saiu do front quando o historico passou a
    // gravar o veredito, e o mock precisa falar o contrato novo. Sem ele a mesa mostra "sem
    // avaliacao", que e o comportamento certo para uma resposta sem veredito.
    grade.mockResolvedValue({ is_correct: true, action_quality: "correct", nivel: "correta",
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
    // O timeout é explícito e maior que o padrão de 1s por um motivo medido: este caso falhou
    // QUATRO vezes na suíte cheia e passou sempre isolado, com duração de ~1,4s contra ~250ms
    // sozinho. A causa é disputa de CPU entre os 103 arquivos rodando em paralelo, e não a
    // lógica -- mas um teste que pisca mascara regressão de verdade, e conviver com ele é pior
    // que afrouxar o prazo. O que o caso prova (a tecla agir na mesa em foco) não mudou.
    await waitFor(() => expect(grade).toHaveBeenCalledTimes(1), { timeout: 5000 });
    // a mao corrigida e a da mesa 1, nao a de outra
    expect(grade.mock.calls[0][0].hand).toBe("K7s");
    expect(grade.mock.calls[0][1]).toBe("fold");
  });

  it("Tab move o foco, e a tecla passa a agir na mesa nova", async () => {
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    fireEvent.keyDown(window, { key: "Tab" });
    await waitFor(() =>
      expect(screen.getByTestId("pratica-mesa-m2").getAttribute("data-foco")).toBe("1"),
      { timeout: 5000 });
    fireEvent.keyDown(window, { key: "a" });
    await waitFor(() => expect(grade).toHaveBeenCalledTimes(1), { timeout: 5000 });
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
    await waitFor(() => expect(grade).toHaveBeenCalledTimes(1), { timeout: 5000 });
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
    // o veredito agora ocupa o CENTRO da mesa (pedido do dono), e nao o rodape do card
    const v = await within(m1).findByTestId("pratica-veredito");
    // `melhor` e `correta` foram fundidos por decisao do dono ("pra mim sao a mesma coisa"), e
    // o rotulo voltou a "correta" para bater com o `action_quality` do servidor.
    expect(v.textContent).toContain("nivel.correta");
    // a pontuacao: a frequencia com que o GTO joga a acao ESCOLHIDA (F = 80%)
    expect(v.textContent).toContain("80%");
    // e o SIMBOLO da escala, que e o que ORDENA os quatro niveis
    expect(v.textContent).toContain("✓✓");
  });

  it("a COR do custo segue o nivel, e nao e vermelha sempre", async () => {
    // 17/09, o dono: "o veredito ainda nao esta premium". Avaliando a captura dele, o defeito que
    // mais pesava era SEMANTICO e nao de tamanho: o veredito dizia "aceitavel" em ambar e o custo
    // dizia "-0.01bb" em VERMELHO, a um centimetro de distancia. Duas cores com significados
    // opostos no mesmo card.
    //
    // O guarda ancora na CONDICAO (a cor sai do nivel) e tem os dois lados: sem o controle, um
    // `text-red-400` cravado passaria no primeiro caso se eu tivesse escolhido outro tom.
    grade.mockResolvedValue({ is_correct: true, action_quality: "acceptable", nivel: "imprecisao",
                              hand_freq: { R2: 0.11, A: 0.89 }, ev_loss_bb: -0.01 });
    monta();
    const m1 = await screen.findByTestId("pratica-mesa-m1");
    fireEvent.click(within(m1).getByTestId("pratica-acao-raise"));
    const v = await within(m1).findByTestId("pratica-veredito");

    const custo = within(v).getByText(/0\.01bb/);
    expect(custo.className, "o custo de uma imprecisao saiu VERMELHO, contradizendo o veredito")
      .not.toMatch(/text-red-[45]00(?!\/)/);
    expect(custo.className, "o custo deixou de acompanhar o nivel").toContain("amber");

    // o card tambem se liga ao nivel pela borda, e ABRACA o conteudo
    expect(v.className, "o card voltou a esticar na largura do centro").toContain("w-fit");
    expect(v.className).toMatch(/border-amber/);
  });

  it("CONTROLE: num erro GRAVE o custo E vermelho", async () => {
    // Sem este, um mapa de cores que devolvesse ambar para tudo passaria verde no caso acima.
    grade.mockResolvedValue({ is_correct: false, action_quality: "clear_mistake", nivel: "grave",
                              hand_freq: { F: 1.0 }, ev_loss_bb: -3.4 });
    monta();
    const m1 = await screen.findByTestId("pratica-mesa-m1");
    fireEvent.click(within(m1).getByTestId("pratica-acao-raise"));
    const v = await within(m1).findByTestId("pratica-veredito");
    expect(within(v).getByText(/3\.40bb/).className).toMatch(/text-red-500/);
    expect(v.className).toMatch(/border-red-600/);
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

  it("no fluxo PADRAO nao existe botao de continuar", async () => {
    // O dono, rodando a tela: "aparece um botao continuar, e so aparecem novos spots apos clique
    // neste botao...eu quero que seja dinamico, a cada nova acao escolhida, cada uma das mesas
    // puxe um novo spot".
    //
    // A causa era o padrao `pausa: "erro"`: a mesa que ele errava ficava esperando o clique, e o
    // grind parava onde o jogador estava engajado. O padrao agora e "nunca", e este guarda trava
    // as duas pontas -- o valor do padrao e o efeito dele na tela, porque so o valor deixaria
    // passar uma tela que mostrasse o botao por outro caminho.
    expect(CONFIG_PADRAO.pausa).toBe("nunca");

    vi.useFakeTimers();
    try {
      monta();
      await vi.waitFor(() => expect(screen.getByTestId("pratica-mesa-m1")).toBeTruthy());

      // erra de proposito nas quatro: `leak` e o nivel que a pausa "erro" segurava
      grade.mockResolvedValue({ is_correct: false, action_quality: "leak",
                                hand_freq: { R2: 0.9, F: 0.1 }, ev_loss_bb: -1.2 });
      for (const id of ["m1", "m2", "m3", "m4"]) {
        fireEvent.click(within(screen.getByTestId(`pratica-mesa-${id}`)).getByTestId("pratica-acao-fold"));
      }
      await vi.waitFor(() => expect(grade).toHaveBeenCalledTimes(4));

      // nenhum botao de continuar, em nenhum momento
      expect(screen.queryByTestId("pratica-continuar")).toBeNull();

      // e as quatro puxam spot novo sozinhas
      let n = 0;
      tables.mockImplementation(() => {
        n += 1;
        return Promise.resolve({ tables: [MESA(`nova${n}`, "BTN", "72o", 10)], pedidas: 1, servidas: 1 });
      });
      await vi.advanceTimersByTimeAsync(2100);
      await vi.waitFor(() => expect(n).toBe(4));
      expect(screen.queryByTestId("pratica-continuar")).toBeNull();
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

  it("os BOTOES tem a vez na altura, e a mesa fica com o resto", async () => {
    // O defeito que o dono viu duas vezes, e o segundo relato foi "sumiram os botoes de acao".
    //
    // A mesa tinha `aspect-ratio: 16/10` com `shrink-0`: numa celula de 840px de largura ela
    // EXIGIA 525px de altura, estourava os ~440 do card e empurrava os controles para fora --
    // e o card e `overflow-hidden`, entao eles simplesmente desapareciam. Nao era a elipse ser
    // grande: era ela exigir altura em vez de aceitar o que sobra.
    //
    // jsdom nao faz layout, entao o guarda trava a ESTRUTURA que impede isso de voltar: quem
    // encolhe e a mesa, nunca os botoes.
    monta();
    const m1 = await screen.findByTestId("pratica-mesa-m1");

    const caixaDaMesa = m1.querySelector('[data-testid="mesa-compacta"]')!.parentElement!;
    expect(caixaDaMesa.className, "a mesa precisa ABSORVER a sobra").toContain("flex-1");
    expect(caixaDaMesa.className, "e poder encolher").toContain("min-h-0");
    expect(caixaDaMesa.className, "shrink-0 na mesa e o que empurrava os botoes")
      .not.toContain("shrink-0");
    expect(caixaDaMesa.getAttribute("style") || "",
           "aspect-ratio na mesa faz a altura ser EXIGIDA a partir da largura")
      .not.toContain("aspect-ratio");

    // e os controles nao podem ser empurrados
    const botoes = within(m1).getByTestId("pratica-acao-fold").parentElement!;
    expect(botoes.className, "a faixa de botoes precisa ser shrink-0").toContain("shrink-0");
  });

  it("a grade das mesas NAO rola quando as mesas CABEM", async () => {
    // Requisito do dono de 16/09: "as 4 mesas tem que caber na tela do usuario, sem depender de
    // barra de rolagem". Ele segue valendo, e agora com uma condicao: vale enquanto o minimo cabe.
    // Em 17/09 ele decidiu o desempate para quando nao cabe ("nao podemos reduzir a mesa desta
    // forma"), e ai rolar e melhor que achatar -- o caso seguinte cobre esse lado.
    //
    // jsdom nao faz layout, entao o guarda trava a ESTRUTURA: a faixa e overflow-hidden e a grade
    // declara as linhas (sem linhas declaradas o grid usa a altura do conteudo e estoura a faixa).
    comLargura(1440, 1000);
    try {
      monta();
      await screen.findByTestId("pratica-mesa-m1");
      const grade = screen.getByTestId("pratica-grade");
      expect(grade.style.gridTemplateRows, "a grade precisa declarar as linhas").toBe(
        "repeat(2, minmax(368px, 1fr))");
      expect(grade.className).toContain("h-full");
      const faixa = grade.parentElement!;
      expect(faixa.className).toContain("overflow-hidden");
      expect(faixa.className).not.toContain("overflow-y-auto");
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("quando nem UMA mesa alcanca o minimo, a faixa ROLA em vez de a mesa achatar", async () => {
    // O ultimo recurso, e a ordem importa: a grade tira mesa, tira coluna, e so no fim rola. Numa
    // janela de 340px de altura nem uma mesa alcanca os 300px que o medidor exige, e entre rolar
    // e mostrar um borrao o dono ja decidiu.
    comLargura(1353, 340);
    try {
      monta();
      await screen.findByTestId("pratica-mesa-m1");
      expect(screen.getAllByTestId(/^pratica-mesa-/).length, "achatou em vez de fechar mesa").toBe(1);
      const faixa = screen.getByTestId("pratica-grade").parentElement!;
      expect(faixa.className, "a faixa nao rolou, entao a mesa achatou").toContain("overflow-y-auto");
    } finally {
      comLargura(1440, 1000);
    }
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

  it("entre o clique e a resposta NAO aparece veredito nenhum", async () => {
    // O dono: "ao clicar em uma acao...antes do veredito final, esta aparecendo rapidamente o
    // veredito 'errada', e na sequencia aparece o veredito real".
    //
    // O guarda prende a resposta do servidor numa promessa que EU resolvo, e olha a tela no
    // intervalo. Sem prender, o mock resolve no mesmo tick e o intervalo nao existe para ser
    // medido -- o teste passaria verde sem nunca ver o momento do defeito.
    let solta: (g: unknown) => void = () => {};
    grade.mockImplementation(() => new Promise((res) => { solta = res; }));

    monta();
    await screen.findByTestId("pratica-mesa-m1");
    const mesa = screen.getByTestId("pratica-mesa-m1");
    fireEvent.click(within(mesa).getByRole("button", { name: /fold/i }));

    // no intervalo: "avaliando", e NENHUM veredito
    await waitFor(() => expect(within(mesa).queryByTestId("pratica-avaliando")).toBeTruthy(),
                  { timeout: 5000 });
    expect(within(mesa).queryByTestId("pratica-veredito"),
           "veredito antes da resposta e uma acusacao sem dado").toBeNull();

    solta({ is_correct: true, action_quality: "correct", nivel: "correta",
            hand_freq: { F: 0.9 }, ev_loss_bb: 0 });
    await waitFor(() => expect(within(mesa).queryByTestId("pratica-veredito")).toBeTruthy(),
                  { timeout: 5000 });
    expect(within(mesa).queryByTestId("pratica-avaliando")).toBeNull();
  });

  it("se a avaliacao FALHA, a mesa diz que nao avaliou em vez de acusar", async () => {
    // Antes deste conserto, `grade` nulo virava "errada" e ficava PARADO na tela: uma acusacao
    // inventada, que e pior que o flash. A mao tambem nao pode entrar no placar.
    grade.mockRejectedValue(new Error("500"));
    monta();
    await screen.findByTestId("pratica-mesa-m1");
    const mesa = screen.getByTestId("pratica-mesa-m1");
    fireEvent.click(within(mesa).getByRole("button", { name: /fold/i }));

    await waitFor(() => expect(within(mesa).queryByTestId("pratica-sem-avaliacao")).toBeTruthy(),
                  { timeout: 5000 });
    expect(within(mesa).queryByTestId("pratica-veredito")).toBeNull();
  });

  /**
   * ── Tela pequena (17/09) ──────────────────────────────────────────────────────────────────
   *
   * O dono abriu o Pratica no celular: quatro mesas minusculas em 2x2, os botoes da barra
   * sobrepostos, e nenhum acesso ao painel de configuracao (ele era `hidden lg:flex`). O pedido:
   * "No celular vamos ficar apenas 1 mesa, e garantir que o menu de configuracao apareca, hoje
   * isto nao esta acontecendo. Nao permitir aumentar o numero de mesas em telas pequenas".
   *
   * O jsdom tem `window.innerWidth` de 1024 por padrao, que e exatamente o corte -- os casos
   * abaixo trocam a largura ANTES de montar, porque o teto e lido na montagem.
   */
  function comLargura(px: number, altura = 1000) {
    Object.defineProperty(window, "innerWidth", { value: px, configurable: true, writable: true });
    // A ALTURA entra no teto desde 17/09 (a mesa precisa de 300px para nao colidir), e o jsdom
    // vem com 768 -- que pela regua nao cabe quatro mesas. Os casos que querem quatro precisam
    // dizer que a janela e alta.
    Object.defineProperty(window, "innerHeight", { value: altura, configurable: true, writable: true });
  }

  it("no celular pede UMA mesa, mesmo com 4 na URL", async () => {
    comLargura(390);
    try {
      render(<MemoryRouter initialEntries={["/practice?mesas=4"]}><Practice /></MemoryRouter>);
      await waitFor(() => expect(tables).toHaveBeenCalled(), { timeout: 5000 });
      // o primeiro argumento de `practice.tables` e quantas mesas
      expect(tables.mock.calls[0][0], "quatro mesas num celular").toBe(1);
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("a barra tem UM caminho de saida, e nenhum rotulo promete tela que nao existe", async () => {
    // 17/09, o dono: "encerrar e ver boletim ? acho que podemos remover este botao... ja temos um
    // botao voltar e o botao de maos".
    //
    // Ele estava certo por um motivo mais forte que a repeticao: aquele botao chamava
    // `navigate("/training")`, o MESMO que o voltar, e nunca mostrou boletim -- o
    // `BoletimDaSessao` vive no Leak Trainer. Era rotulo prometendo tela que nao existe aqui.
    //
    // Este caso ancora nas DUAS coisas: a saida duplicada e a promessa. Sem a segunda, alguem
    // reintroduz o botao com outro `data-testid` e o guarda passa.
    comLargura(1440, 1000);
    try {
      monta();
      await screen.findByTestId("pratica-mesa-m1");
      expect(screen.queryByTestId("pratica-encerrar"),
             "o botao de encerrar voltou").toBeNull();

      // e NENHUM texto da barra fala de boletim, em nenhum idioma: o `t()` dos testes devolve a
      // chave, entao a chave e o que se procura
      const barra = screen.getByTestId("pratica-abrir-relatorio").closest("div")!.parentElement!;
      expect(barra.textContent, "a barra voltou a prometer boletim").not.toMatch(/encerrar|boletim/i);

      // o caminho de volta continua existindo: um so
      const voltar = screen.getAllByRole("button")
        .filter((b) => /voltar/i.test(b.getAttribute("aria-label") || ""));
      expect(voltar.length, "sobrou mais de um caminho de saida, ou nenhum").toBe(1);
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("a POSICAO da URL chega no pedido, em ordem de acao", async () => {
    // Pedido do Rullian, trazido pelo dono (17/09). A ordem importa: `mudaOSorteio` compara as
    // listas posicao a posicao, e a mesma escolha em outra ordem diria que o sorteio mudou.
    comLargura(1440, 1000);
    try {
      render(<MemoryRouter initialEntries={["/practice?posicoes=co,btn&mesas=2"]}>
               <Practice /></MemoryRouter>);
      await waitFor(() => expect(tables).toHaveBeenCalled(), { timeout: 5000 });
      expect(tables.mock.calls[0][1].posicoes).toEqual(["CO", "BTN"]);
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("rotulo de posicao DESCONHECIDO e descartado, e nao vira filtro que nunca casa", async () => {
    // CONTROLE do caso acima, e conserto de um estado sem saida: `?posicoes=BUTTON` pediria um
    // spot que o servidor nunca devolve, e a tela ficaria pedindo mesas para sempre.
    comLargura(1440, 1000);
    try {
      render(<MemoryRouter initialEntries={["/practice?posicoes=BUTTON"]}><Practice /></MemoryRouter>);
      await waitFor(() => expect(tables).toHaveBeenCalled(), { timeout: 5000 });
      expect(tables.mock.calls[0][1].posicoes).toEqual(CONFIG_PADRAO.posicoes);
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("filtro que rende MENOS mesas do que o pedido e DECLARADO na tela", async () => {
    // Medido no servidor em 17/09: `rfi` com BB, `vs_rfi` com UTG, `vs_3bet` com SB e `vs_3bet`
    // com BB nao tem spot nenhum, e outras combinacoes tem pool pequeno e rendem menos de quatro.
    // Sem esta linha, o jogador escolhe um filtro estreito, ve uma mesa no lugar de quatro e le
    // isso como travamento -- o servidor sempre mandou `pedidas` e `servidas`, e a tela ignorava.
    comLargura(1440, 1000);
    try {
      tables.mockResolvedValue({ tables: [QUATRO[0]], pedidas: 4, servidas: 1 });
      monta();
      const aviso = await screen.findByTestId("pratica-filtro-estreito");
      expect(aviso.textContent).toContain("filtroEstreito");
      expect(aviso.textContent, "a linha precisa dizer os DOIS numeros").toContain("1,4");
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("CONTROLE: com as mesas todas servidas, a tela NAO avisa nada", async () => {
    comLargura(1440, 1000);
    try {
      tables.mockResolvedValue({ tables: QUATRO, pedidas: 4, servidas: 4 });
      monta();
      await screen.findByTestId("pratica-mesa-m1");
      expect(screen.queryByTestId("pratica-filtro-estreito"),
             "avisou de filtro estreito sem filtro estreito").toBeNull();
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("reduzir a JANELA fecha mesa, e nao encolhe a mesa", async () => {
    // 17/09, a captura do dono: ele abriu quatro mesas, reduziu a altura da janela do browser, e
    // as quatro FICARAM na tela -- cada uma um borrao ilegivel. "isto nao pode acontecer...temos
    // que ter os cuidados responsivos...se nao cabe com as condicoes minimas, deixamos apenas 1
    // coluna, ou algo do tipo...mas nao podemos reduzir a mesa desta forma".
    //
    // A regra do teto JA existia e JA dizia "duas". O defeito era de alcance: ela era consultada
    // so na hora de BUSCAR as mesas, e quem DESENHAVA usava classes fixas (`grid-rows-2`). Este
    // caso ancora no que aparece na tela, que e onde o defeito morava.
    comLargura(1440, 1000);
    try {
      tables.mockResolvedValue({ tables: QUATRO });
      render(<MemoryRouter initialEntries={["/practice?mesas=4"]}><Practice /></MemoryRouter>);
      await waitFor(() => expect(screen.getAllByTestId(/^pratica-mesa-/).length).toBe(4),
                    { timeout: 5000 });

      // a janela da captura: 1353x500
      comLargura(1353, 500);
      fireEvent(window, new Event("resize"));

      await waitFor(() => expect(
        screen.getAllByTestId(/^pratica-mesa-/).length,
        "as quatro continuaram na tela, encolhidas",
      ).toBe(2), { timeout: 5000 });

      // e a grade ficou em DUAS colunas e UMA linha, com piso de altura na celula
      const g = screen.getByTestId("pratica-grade");
      expect(g.style.gridTemplateColumns).toBe("repeat(2, minmax(0, 1fr))");
      expect(g.style.gridTemplateRows, "a celula ficou sem piso de altura")
        .toBe("repeat(1, minmax(368px, 1fr))");
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("no desktop a URL com 4 mesas continua valendo", async () => {
    // CONTROLE do caso acima: sem ele, um teto cravado em 1 passaria verde nos dois.
    comLargura(1440);
    try {
      render(<MemoryRouter initialEntries={["/practice?mesas=4"]}><Practice /></MemoryRouter>);
      await waitFor(() => expect(tables).toHaveBeenCalled(), { timeout: 5000 });
      expect(tables.mock.calls[0][0]).toBe(4);
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("no celular o painel tem acesso pela barra, e comeca fechado", async () => {
    comLargura(390);
    try {
      monta();
      await screen.findByTestId("pratica-mesa-m1");
      // fechado: a gaveta nao esta na tela cobrindo a mesa
      expect(screen.queryByTestId("pratica-painel")).toBeNull();
      // e existe um acesso -- sem ele, no celular nao havia como trocar stack nem cenario
      const botao = screen.getByTestId("pratica-abrir-painel-mobile");
      fireEvent.click(botao);
      const gaveta = await screen.findByTestId("pratica-painel");

      // A CLASSE, e nao a presenca no DOM: o jsdom nao aplica media query, entao `hidden lg:flex`
      // continua no documento e `findByTestId` o acha mesmo invisivel no celular. Verificado
      // quebrando -- com o `hidden` de volta, a versao anterior deste caso passou VERDE.
      expect(gaveta.className, "com `hidden` o painel nao existe no celular")
        .not.toMatch(/(^|\s)hidden(\s|$)/);
      // e ele e gaveta no celular, coluna no desktop
      expect(gaveta.className).toContain("absolute");
      expect(gaveta.className).toContain("lg:static");
    } finally {
      comLargura(1440, 1000);
    }
  });

  it("no celular o seletor de mesas TRAVA acima de uma, e diz por que", async () => {
    comLargura(390);
    try {
      monta();
      await screen.findByTestId("pratica-mesa-m1");
      fireEvent.click(screen.getByTestId("pratica-abrir-painel-mobile"));
      await screen.findByTestId("pratica-painel");

      // `hasAttribute` e nao `toBeDisabled`: o projeto nao usa jest-dom, e a matcher inexistente
      // faz o caso falhar por motivo errado.
      expect((screen.getByTestId("pratica-mesas-1") as HTMLButtonElement).disabled).toBe(false);
      for (const n of [2, 3, 4]) {
        expect((screen.getByTestId(`pratica-mesas-${n}`) as HTMLButtonElement).disabled,
               `${n} mesas`).toBe(true);
      }
      // e a frase explica: um botao cinza sozinho parece defeito
      expect(screen.getByTestId("pratica-so-uma-mesa")).toBeTruthy();

      // clicar no que esta travado nao muda nada
      fireEvent.click(screen.getByTestId("pratica-mesas-4"));
      expect(screen.queryByTestId("pratica-pendente")).toBeNull();
    } finally {
      comLargura(1440, 1000);
    }
  });
});
