// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Card "Aproveitamento do solver" (AY-28): os quatro numeros e a tabela semanal saem do payload,
 * o reaproveitamento baixo e a fila cheia ficam em destaque, e a semana sem dado nao vira zero
 * mudo. A conta e do backend; aqui esta travada a leitura.
 */
const { solverAproveitamento } = vi.hoisted(() => ({ solverAproveitamento: vi.fn() }));
vi.mock("@/lib/api", () => ({ adminDashboard: { solverAproveitamento } }));

import { AproveitamentoDoSolver } from "./AproveitamentoDoSolver";

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AproveitamentoDoSolver /></QueryClientProvider>);
}
beforeEach(() => solverAproveitamento.mockReset());
afterEach(() => cleanup());

describe("aproveitamento do solver", () => {
  it("mostra reaproveitamento, semelhanca, fila e espera, e a tabela por semana", async () => {
    solverAproveitamento.mockResolvedValue({
      acervo: { nos: 37144, arvores: 36707 },
      fila: { pending: 2197, running: 4, done: 32233, failed: 465, rejected: 137 },
      espera: { n: 25439, media_h: 14.2, mediana_h: 6.5 },
      semanas: [
        { semana: "2026-08-31", decisoes: 16721, spots: 16700, reaproveitadas: 500, resolvidas_depois: 10000, sem_no: 6221, enviados: 17000, pct_reaproveitado: 3 },
        { semana: "2026-09-07", decisoes: 7301, spots: 7300, reaproveitadas: 220, resolvidas_depois: 3900, sem_no: 3181, enviados: 7400, pct_reaproveitado: 3 },
      ],
      semelhanca: { sem_no: 8862, com_vizinho: 5323, pct: 60, assinaturas_conhecidas: 4100 },
    });
    montar();
    const card = await screen.findByTestId("aproveitamento-solver");
    expect(within(card).getByTestId("tile-reaproveitado").textContent).toContain("3%");
    expect(within(card).getByTestId("tile-reaproveitado").textContent).toContain("220 de 7301");
    expect(within(card).getByTestId("tile-reaproveitado").className).toContain("amber");       // abaixo de 10%: destaque
    expect(within(card).getByTestId("tile-semelhanca").textContent).toContain("60%");
    expect(within(card).getByTestId("tile-semelhanca").textContent).toContain("5323 de 8862");
    expect(within(card).getByTestId("tile-fila").textContent).toContain("2197");
    expect(within(card).getByTestId("tile-fila").className).toContain("amber");
    expect(within(card).getByTestId("tile-espera").textContent).toContain("6.5 h");
    expect(within(card).getByTestId("tile-espera").textContent).toContain("37.144");
    const linha = within(card).getByTestId("semana-2026-08-31");
    expect(linha.textContent).toContain("16721");
    expect(linha.textContent).toContain("17000");
    expect(linha.textContent).toContain("3%");
  });

  it("sem semanas, diz que nao ha decisoes em vez de mostrar zeros", async () => {
    solverAproveitamento.mockResolvedValue({
      acervo: { nos: 0, arvores: 0 }, fila: {}, espera: { n: 0, media_h: null, mediana_h: null },
      semanas: [], semelhanca: { sem_no: 0, com_vizinho: 0, pct: 0, assinaturas_conhecidas: 0 },
    });
    montar();
    const card = await screen.findByTestId("aproveitamento-solver");
    expect(card.textContent).toContain("Sem decisões pós-flop no período");
    expect(within(card).getByTestId("tile-reaproveitado").textContent).toContain("—");
    expect(within(card).getByTestId("tile-espera").textContent).toContain("—");
  });
});
