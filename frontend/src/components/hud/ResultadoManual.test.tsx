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
    // o corpo NAO leva lucro: quem calcula e o servidor
    expect(resultadoManual).toHaveBeenCalledWith("PARTY-13165152578",
      { place: 6, prize: 12.4, buy_in: 5.5, field_size: 180 });
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
