// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, within } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
  }),
}));

const report = vi.fn();
const history = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return {
    ...real,
    practice: {
      ...real.practice,
      report: (...a: unknown[]) => report(...a),
      history: (...a: unknown[]) => history(...a),
    },
  };
});

import { RelatorioDePratica } from "./RelatorioDePratica";

/**
 * O relatório das mãos praticadas.
 *
 * Pedido do dono: "seria interessante armazenar este treino, para ficar no historico das ultimas
 * maos treinadas, e ter a possibilidade de gerar um relatorio como o do gto wizard".
 *
 * O que estes casos protegem:
 *
 * 1. Os números são os do SERVIDOR. A tela não recalcula nada -- a régua já morou no front, e com
 *    o histórico gravando havia duas contas para o mesmo julgamento.
 * 2. Mão sem veredito aparece como tal, e separada dos quatro níveis.
 * 3. Falha de rede vira frase, e não código de erro: "nao podemos retornar codigo de erro para o
 *    usuario, temos que ter o erro tratado" (o dono, 16/09, sobre o upload).
 * 4. A paginação manda o `before` da última linha (keyset): com offset, praticar enquanto olha o
 *    histórico repetiria linha.
 * 5. Reabrir RECARREGA: o jogador abre isto depois de praticar, e cache diria menos mãos.
 */

const RELATORIO = {
  maos: 12,
  julgadas: 10,
  sem_avaliacao: 2,
  por_nivel: { correta: 6, imprecisao: 1, errada: 2, grave: 1 },
  acerto: 60.0,
  bb_perdidos: 4.53,
  bb_por_mao: 0.453,
  por_posicao: { BTN: { maos: 7, corretas: 5, bb: 1.2 }, SB: { maos: 5, corretas: 1, bb: 3.33 } },
  por_cenario: { rfi: { maos: 8, corretas: 5, bb: 2.0 }, vs_3bet: { maos: 4, corretas: 1, bb: 2.53 } },
};

function mao(id: number, extra: Record<string, unknown> = {}) {
  return {
    id,
    mao: "96s",
    posicao: "SB",
    stack_bb: 10,
    cenario: "rfi",
    resumo: "SB, RFI",
    acao: "call",
    acao_gto: "jam",
    freq_da_acao: 0,
    freq_melhor: 1,
    nivel: "errada",
    ev_loss_bb: 0.028,
    criado_em: "2026-09-16 22:00:00",
    ...extra,
  };
}

describe("o relatorio de pratica", () => {
  beforeEach(() => {
    report.mockReset();
    history.mockReset();
    report.mockResolvedValue(RELATORIO);
    history.mockResolvedValue({ maos: [mao(3), mao(2), mao(1)], proximo: 1 });
  });
  afterEach(cleanup);

  it("fechado nao busca nada", () => {
    render(<RelatorioDePratica aberto={false} onFechar={() => {}} />);
    expect(screen.queryByTestId("pratica-relatorio")).toBeNull();
    expect(report).not.toHaveBeenCalled();
    expect(history).not.toHaveBeenCalled();
  });

  it("mostra o placar do SERVIDOR, sem recalcular", async () => {
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    await screen.findByTestId("pratica-relatorio-tabela");

    // os quatro numeros do topo saem do payload, tal como vieram. Por testid e nao por texto:
    // "60%" tambem aparece nos cortes por posicao, e o guarda por texto achava dois elementos --
    // um teste que falha por ambiguidade nao diz nada sobre o produto.
    expect(screen.getByTestId("placar-maos").textContent).toContain("12");
    expect(screen.getByTestId("placar-acerto").textContent).toContain("60%");
    expect(screen.getByTestId("placar-bb").textContent).toContain("−4.53");
    expect(screen.getByTestId("placar-bb-mao").textContent).toContain("−0.453");

    // e a distribuicao por nivel tambem
    const corpo = screen.getByTestId("pratica-relatorio");
    expect(within(corpo).getByText("nivel.correta")).toBeTruthy();
    expect(within(corpo).getByText("nivel.grave")).toBeTruthy();
  });

  it("as maos SEM veredito aparecem separadas dos quatro niveis", async () => {
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    const chip = await screen.findByTestId("pratica-relatorio-sem-avaliacao");
    expect(chip.textContent).toContain("2");
    // e a soma dos quatro niveis continua sendo as JULGADAS, e nao o total
    expect(RELATORIO.por_nivel.correta + RELATORIO.por_nivel.imprecisao
           + RELATORIO.por_nivel.errada + RELATORIO.por_nivel.grave).toBe(RELATORIO.julgadas);
  });

  it("a tabela mostra a mao, o que ele fez e o que o GTO faz", async () => {
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    const tabela = await screen.findByTestId("pratica-relatorio-tabela");
    const linhas = tabela.querySelectorAll("tr");
    expect(linhas.length).toBe(3);

    const primeira = linhas[0].textContent || "";
    expect(primeira).toContain("96s");
    expect(primeira).toContain("SB, RFI");
    expect(primeira).toContain("call");
    expect(primeira).toContain("jam");
    expect(primeira).toContain("nivel.errada");
    // o custo aparece como PERDA, com o sinal na tela e nao no dado
    expect(primeira).toContain("−0.03");
  });

  it("uma mao sem veredito na tabela nao vira acusacao", async () => {
    history.mockResolvedValue({ maos: [mao(9, { nivel: null, ev_loss_bb: null })], proximo: null });
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    const tabela = await screen.findByTestId("pratica-relatorio-tabela");
    const texto = tabela.textContent || "";
    expect(texto).toContain("relatorio.semAvaliacao");
    expect(texto, "sem veredito nao se pinta nivel nenhum").not.toContain("nivel.errada");
  });

  it("nivel desconhecido do servidor nao pinta veredito errado", async () => {
    // Backend mais novo que o bundle: um rotulo que a tela nao conhece tem de cair no "sem
    // avaliacao", e nao num nivel qualquer por descuido de indexacao.
    history.mockResolvedValue({ maos: [mao(9, { nivel: "catastrofica" })], proximo: null });
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    const tabela = await screen.findByTestId("pratica-relatorio-tabela");
    expect(tabela.textContent).toContain("relatorio.semAvaliacao");
  });

  it("sem nenhuma mao praticada, explica em vez de mostrar tabela vazia", async () => {
    report.mockResolvedValue({ ...RELATORIO, maos: 0, julgadas: 0, sem_avaliacao: 0 });
    history.mockResolvedValue({ maos: [], proximo: null });
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    expect(await screen.findByTestId("pratica-relatorio-vazio")).toBeTruthy();
    expect(screen.queryByTestId("pratica-relatorio-tabela")).toBeNull();
  });

  it("falha de rede vira FRASE, e nao codigo de erro", async () => {
    // O dono, sobre o upload: "nao podemos retornar codigo de erro para o usuario, temos que ter
    // o erro tratado". Vale para toda tela, e nao so para aquela.
    report.mockRejectedValue(new Error("500 Internal Server Error"));
    history.mockRejectedValue(new Error("500 Internal Server Error"));
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    const erro = await screen.findByTestId("pratica-relatorio-erro");
    expect(erro.textContent).toContain("relatorio.erro");
    expect(erro.textContent, "codigo de erro na cara do jogador").not.toContain("500");
  });

  it("carregar mais pagina pelo ID da ultima linha, e nao por offset", async () => {
    // Pagina CHEIA: o botao de carregar mais so aparece quando vieram 50 maos, senao a tela
    // ofereceria "mais" sobre uma lista que ja terminou.
    const cheia = Array.from({ length: 50 }, (_, i) => mao(100 - i));
    history.mockResolvedValue({ maos: cheia, proximo: cheia[cheia.length - 1].id });
    render(<RelatorioDePratica aberto onFechar={() => {}} />);
    await screen.findByTestId("pratica-relatorio-tabela");
    expect(history).toHaveBeenLastCalledWith(50);

    history.mockResolvedValue({ maos: [mao(0, { id: 0 })], proximo: null });
    fireEvent.click(screen.getByTestId("pratica-relatorio-mais"));

    await waitFor(() => expect(history).toHaveBeenCalledTimes(2));
    // o `before` e o id da ULTIMA linha que a tela ja tem (keyset). Com offset, uma mao nova
    // praticada no meio empurraria a lista e a pagina 2 repetiria o que a 1 mostrou.
    expect(history).toHaveBeenLastCalledWith(50, 51);
  });

  it("reabrir RECARREGA: o jogador consulta isto DEPOIS de praticar", async () => {
    const { rerender } = render(<RelatorioDePratica aberto onFechar={() => {}} />);
    await screen.findByTestId("pratica-relatorio-tabela");
    expect(report).toHaveBeenCalledTimes(1);

    rerender(<RelatorioDePratica aberto={false} onFechar={() => {}} />);
    rerender(<RelatorioDePratica aberto onFechar={() => {}} />);
    await waitFor(() => expect(report).toHaveBeenCalledTimes(2));
  });

  it("o botao de fechar avisa quem abriu", async () => {
    const fechar = vi.fn();
    render(<RelatorioDePratica aberto onFechar={fechar} />);
    await screen.findByTestId("pratica-relatorio-tabela");
    fireEvent.click(screen.getByTestId("pratica-relatorio-fechar"));
    expect(fechar).toHaveBeenCalled();
  });
});
