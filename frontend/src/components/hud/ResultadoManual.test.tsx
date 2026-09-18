// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
  }),
}));

const resultadoManual = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return {
    ...real,
    tournaments: { ...real.tournaments, resultadoManual: (...a: unknown[]) => resultadoManual(...a) },
  };
});

import { MarcaDeProcedencia, ResultadoManual } from "./ResultadoManual";
import type { Tournament } from "@/lib/api";

/**
 * O formulário de resultado, para as salas que não publicam o Tournament Summary (PartyPoker).
 *
 * O que estes casos protegem:
 *
 * 1. O LUCRO não é digitado: ele é `prêmio - buy-in`, e a tela mostra a conta antes de salvar para
 *    o número não ser surpresa. Se ele fosse um campo, três valores poderiam não fechar entre si.
 * 2. As validações falam PORTUGUÊS, e não código: "nao podemos retornar codigo de erro para o
 *    usuario, temos que ter o erro tratado" (o dono, 16/09).
 * 3. Reabrir com OUTRO torneio não herda os números do anterior -- seria o jogador salvando o
 *    resultado de um torneio nos campos de outro.
 */

function torneio(extra: Partial<Tournament> = {}): Tournament {
  return {
    id: 1,
    tournament_id: "PARTY-13165152578",
    site: "partypoker",
    hero: "Hero",
    played_at: "2026-09-10",
    imported_at: "2026-09-11",
    hands_count: 120,
    decisions_count: 40,
    avg_score: null,
    standard_pct: null,
    clear_pct: null,
    result: null,
    place: null,
    buy_in: null,
    prize: null,
    profit: null,
    llm_summary: null,
    ...extra,
  } as Tournament;
}

describe("o formulario de resultado manual", () => {
  beforeEach(() => {
    resultadoManual.mockReset();
    resultadoManual.mockResolvedValue({
      tournament_id: "PARTY-13165152578", place: 6, prize: 12.4, buy_in: 5.5, profit: 6.9,
      field_size: 180, financeiro_origem: "manual",
    });
  });
  afterEach(cleanup);

  it("sem torneio nao aparece", () => {
    render(<ResultadoManual torneio={null} onFechar={() => {}} onSalvo={() => {}} />);
    expect(screen.queryByTestId("resultado-manual")).toBeNull();
  });

  it("o campo NAO perde o foco a cada tecla", () => {
    // 17/09, o dono: "o formulario está estranho também...a cada digitação, ele perde o foco".
    //
    // A causa era de React: o `Campo` era declarado DENTRO de `ResultadoManual`, entao ele tinha
    // identidade nova em cada render. O React compara tipos por identidade, via um componente
    // diferente, e em vez de atualizar o `input` DESMONTAVA a arvore e montava outra -- o elemento
    // com o cursor deixava de existir a cada tecla.
    //
    // Os oito casos que existiam aqui nao pegaram isso porque `fireEvent.change` nao olha o foco:
    // o valor chegava certo no estado e o teste passava verde com o formulario inutilizavel. Este
    // ancora no que o jogador sente.
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);
    const alvo = screen.getByTestId("manual-prize") as HTMLInputElement;
    alvo.focus();
    expect(document.activeElement).toBe(alvo);

    for (const v of ["1", "12", "12.", "12.4"]) {
      fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: v } });
      // o MESMO elemento continua no DOM e com o foco: se a arvore remontar, o `alvo` sai do
      // documento e o `activeElement` volta para o body
      expect(alvo.isConnected, `o input foi remontado ao digitar "${v}"`).toBe(true);
      expect(document.activeElement, `o foco saiu ao digitar "${v}"`).toBe(alvo);
    }
    expect((screen.getByTestId("manual-prize") as HTMLInputElement).value).toBe("12.4");
  });

  it("as ENTRADAS entram no custo, e o buy-in segue sendo o da etiqueta", () => {
    // Achado com os dados reais do dono (sete torneios, um com re-entrada): o lucro so fechava se
    // o buy-in digitado ja fosse o total, e ai a etiqueta do torneio ficava errada e o `re_entries`
    // nao era registrado -- enquanto o caminho do ARQUIVO registra os dois.
    const onSalvo = vi.fn();
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={onSalvo} />);
    fireEvent.change(screen.getByTestId("manual-place"), { target: { value: "22" } });
    fireEvent.change(screen.getByTestId("manual-field"), { target: { value: "94" } });
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "1.10" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "2.08" } });
    fireEvent.change(screen.getByTestId("manual-entradas"), { target: { value: "2" } });

    // o custo aparece SO quando ha mais de uma entrada, e o lucro passa por ele
    expect(screen.getByTestId("manual-custo").textContent).toBe("$2.20");
    expect(screen.getByTestId("manual-lucro").textContent).toBe("$0.12");

    fireEvent.click(screen.getByTestId("resultado-manual-salvar"));
    // o corpo leva o buy-in de UMA entrada e o numero de entradas: o custo e conta do servidor
    expect(resultadoManual).toHaveBeenCalledWith("PARTY-13165152578",
      { place: 22, prize: 2.08, buy_in: 1.1, field_size: 94, entradas: 2 });
  });

  it("CONTROLE: com UMA entrada o custo nem aparece", () => {
    // Sem este, um campo de custo sempre visivel passaria no caso acima, e a tela ganharia uma
    // linha de ruido em todo torneio sem re-entrada (a maioria).
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "1.10" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "6.16" } });
    expect((screen.getByTestId("manual-entradas") as HTMLInputElement).value,
           "o padrao de entradas tem de ser 1").toBe("1");
    expect(screen.queryByTestId("manual-custo")).toBeNull();
    expect(screen.getByTestId("manual-lucro").textContent).toBe("+$5.06");
  });

  it("reabrir um torneio com re-entrada mostra o buy-in da ETIQUETA, e nao o custo", () => {
    // O `buy_in` guardado e o custo total (convencao do caminho do arquivo). Sem dividir pelas
    // entradas ao reabrir, o formulario mostraria 2,20 como etiqueta de um torneio de 1,10 -- e
    // salvar de novo DOBRARIA o custo, para 4,40.
    render(<ResultadoManual torneio={torneio({ buy_in: 2.2, re_entries: 1, prize: 2.08, place: 22 })}
                            onFechar={() => {}} onSalvo={() => {}} />);
    expect((screen.getByTestId("manual-entradas") as HTMLInputElement).value).toBe("2");
    expect((screen.getByTestId("manual-buyin") as HTMLInputElement).value,
           "o formulario mostrou o custo total no lugar da etiqueta").toBe("1.1");
    expect(screen.getByTestId("manual-custo").textContent).toBe("$2.20");
  });

  it("o lucro e CALCULADO enquanto ele digita", () => {
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);
    expect(screen.getByTestId("manual-lucro").textContent).toBe("—");

    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "5.50" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "12.40" } });
    expect(screen.getByTestId("manual-lucro").textContent).toBe("+$6.90");

    // prejuizo: o sinal e a cor mudam, e o valor e o modulo
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "0" } });
    expect(screen.getByTestId("manual-lucro").textContent).toBe("$5.50");
  });

  it("aceita virgula como separador decimal", () => {
    // O jogador brasileiro digita 12,40. Recusar isso seria pedir que ele adivinhe o formato.
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "5,50" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "12,40" } });
    expect(screen.getByTestId("manual-lucro").textContent).toBe("+$6.90");
  });

  it("salva e devolve o que o servidor calculou, e nao o que a tela mostrou", async () => {
    const onSalvo = vi.fn();
    const onFechar = vi.fn();
    render(<ResultadoManual torneio={torneio()} onFechar={onFechar} onSalvo={onSalvo} />);
    fireEvent.change(screen.getByTestId("manual-place"), { target: { value: "6" } });
    fireEvent.change(screen.getByTestId("manual-field"), { target: { value: "180" } });
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "5.50" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "12.40" } });
    fireEvent.click(screen.getByTestId("resultado-manual-salvar"));

    await waitFor(() => expect(onSalvo).toHaveBeenCalled());
    // o corpo NAO leva lucro: quem calcula e o servidor. `entradas: 1` vai sempre, para o
    // servidor nunca ter de adivinhar o padrao.
    expect(resultadoManual).toHaveBeenCalledWith("PARTY-13165152578",
      { place: 6, prize: 12.4, buy_in: 5.5, field_size: 180, entradas: 1 });
    expect(onSalvo.mock.calls[0][0]).toEqual({ place: 6, prize: 12.4, buy_in: 5.5, profit: 6.9 });
    expect(onFechar).toHaveBeenCalled();
  });

  it("as validacoes falam PORTUGUES, e nao mandam o pedido", async () => {
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);

    // sem colocacao
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "5.5" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "0" } });
    fireEvent.click(screen.getByTestId("resultado-manual-salvar"));
    expect(screen.getByTestId("resultado-manual-erro").textContent).toContain("manual.erroColocacao");
    expect(resultadoManual, "nao se manda pedido que ja se sabe invalido").not.toHaveBeenCalled();

    // colocacao maior que o campo
    fireEvent.change(screen.getByTestId("manual-place"), { target: { value: "200" } });
    fireEvent.change(screen.getByTestId("manual-field"), { target: { value: "180" } });
    fireEvent.click(screen.getByTestId("resultado-manual-salvar"));
    expect(screen.getByTestId("resultado-manual-erro").textContent)
      .toContain("manual.erroColocacaoMaior");
    expect(resultadoManual).not.toHaveBeenCalled();
  });

  it("falha do servidor vira a frase DELE, e nao um codigo", async () => {
    resultadoManual.mockRejectedValue(new Error(
      "Este torneio ja tem o resultado do arquivo da sala, que e a fonte mais confiavel."));
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);
    fireEvent.change(screen.getByTestId("manual-place"), { target: { value: "6" } });
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "5.5" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "12.4" } });
    fireEvent.click(screen.getByTestId("resultado-manual-salvar"));

    const erro = await screen.findByTestId("resultado-manual-erro");
    expect(erro.textContent).toContain("fonte mais confiavel");
  });

  it("erro NUMERICO do servidor nao vaza para a tela", async () => {
    // Um `Error("500")` e codigo, e o dono foi explicito: o jogador nao ve codigo de erro.
    resultadoManual.mockRejectedValue(new Error("500"));
    render(<ResultadoManual torneio={torneio()} onFechar={() => {}} onSalvo={() => {}} />);
    fireEvent.change(screen.getByTestId("manual-place"), { target: { value: "6" } });
    fireEvent.change(screen.getByTestId("manual-buyin"), { target: { value: "5.5" } });
    fireEvent.change(screen.getByTestId("manual-prize"), { target: { value: "12.4" } });
    fireEvent.click(screen.getByTestId("resultado-manual-salvar"));

    const erro = await screen.findByTestId("resultado-manual-erro");
    expect(erro.textContent).toContain("manual.erroSalvar");
    expect(erro.textContent).not.toContain("500");
  });

  it("reabrir com OUTRO torneio nao herda os numeros do anterior", () => {
    const { rerender } = render(
      <ResultadoManual torneio={torneio({ place: 6, prize: 12.4, buy_in: 5.5 })}
                       onFechar={() => {}} onSalvo={() => {}} />);
    expect((screen.getByTestId("manual-place") as HTMLInputElement).value).toBe("6");

    rerender(<ResultadoManual torneio={torneio({ id: 2, tournament_id: "PARTY-999" })}
                              onFechar={() => {}} onSalvo={() => {}} />);
    expect((screen.getByTestId("manual-place") as HTMLInputElement).value,
           "os campos do torneio anterior ficaram").toBe("");
    expect((screen.getByTestId("manual-prize") as HTMLInputElement).value).toBe("");
  });
});

describe("a marca de procedencia", () => {
  afterEach(cleanup);

  it("aparece SO no numero digitado", () => {
    // Comportamento, e nao o fonte: o guarda anterior lia o arquivo da tela e exigia a palavra
    // `financeiro_origem` nele. Quebrando a condicao de proposito (`false &&`), a palavra
    // continuou no comentario e o guarda passou VERDE.
    const { rerender } = render(<MarcaDeProcedencia origem="manual" />);
    expect(screen.getByTestId("lucro-digitado").textContent).toContain("manual.digitado");

    rerender(<MarcaDeProcedencia origem="arquivo" />);
    expect(screen.queryByTestId("lucro-digitado"),
           "numero de arquivo nao pode parecer digitado").toBeNull();

    rerender(<MarcaDeProcedencia origem={null} />);
    expect(screen.queryByTestId("lucro-digitado")).toBeNull();

    rerender(<MarcaDeProcedencia />);
    expect(screen.queryByTestId("lucro-digitado")).toBeNull();
  });
});
