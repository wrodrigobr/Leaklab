// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const importar = vi.fn();
vi.mock("@/lib/api", () => ({
  adminDashboard: { importarSharkscope: (...a: unknown[]) => importar(...a) },
}));

import { SharkscopeTab } from "./SharkscopeTab";

/**
 * A tela de importação do SharkScope.
 *
 * ── O que ela protege ─────────────────────────────────────────────────────────────────────
 *
 * O risco desta importação não é o número, é o PAREAMENTO: casar o resultado de um torneio com
 * outro. Na primeira comparação entre o JSON e produção, um pareamento por dia mais buy-in trocou
 * os pares em dias com dois torneios do mesmo valor, e as "divergências" que apareceram eram do
 * medidor, não do dado.
 *
 * Por isso a regra da tela: **não existe caminho que escreva sem o plano ter sido visto**. O botão
 * de aplicar não nasce antes da simulação, e não nasce quando não há o que aplicar.
 */
const PLANO = {
  user_id: 3, origem: "sharkscope", aplicado: false,
  atualizar: [{ quando: "2026-09-17T21:25:00", torneio: "8-Max Deepstack: $100 Gtd", buy_in: 1.1,
                premio: 6.16, lucro: 5.06, colocacao: 5, field: 92, freeroll: false, entradas: 1,
                casou_por: "dia+colocacao", motivo: null, torneio_id: "T-2287", torneio_db_id: 2287 }],
  iguais: [], protegidos: [], sem_par: [],
  nossos_sem_correspondencia: [
    { id: 2283, tournament_id: "T-2283", nome: "SNG $0.25", quando: "2026-09-13", maos: 1 },
  ],
};

function monta() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(<QueryClientProvider client={qc}><SharkscopeTab /></QueryClientProvider>);
}

function preenche(json = '{"Response":{}}') {
  fireEvent.change(screen.getByTestId("sharkscope-user"), { target: { value: "3" } });
  fireEvent.change(screen.getByTestId("sharkscope-json"), { target: { value: json } });
}

describe("a tela do importador", () => {
  beforeEach(() => importar.mockReset());
  afterEach(cleanup);

  it("NAO oferece aplicar antes de simular", () => {
    monta();
    preenche();
    expect(screen.queryByTestId("sharkscope-aplicar")).toBeNull();
  });

  it("simula SECO: a chamada vai com aplicar=false", async () => {
    importar.mockResolvedValue(PLANO);
    monta();
    preenche();
    fireEvent.click(screen.getByTestId("sharkscope-simular"));
    await waitFor(() => expect(importar).toHaveBeenCalled());
    const [uid, , aplicar] = importar.mock.calls[0];
    expect(uid).toBe(3);
    expect(aplicar).toBe(false);
  });

  it("depois do plano, o aplicar aparece e vai com aplicar=true", async () => {
    importar.mockResolvedValue(PLANO);
    monta();
    preenche();
    fireEvent.click(screen.getByTestId("sharkscope-simular"));
    const botao = await screen.findByTestId("sharkscope-aplicar");
    expect(botao.textContent).toContain("1");
    importar.mockClear();
    importar.mockResolvedValue({ ...PLANO, aplicado: true, atualizados: 1, falhos: 0 });
    fireEvent.click(botao);
    await waitFor(() => expect(importar).toHaveBeenCalled());
    expect(importar.mock.calls[0][2]).toBe(true);
  });

  it("plano SEM nada a atualizar nao oferece aplicar", async () => {
    importar.mockResolvedValue({ ...PLANO, atualizar: [] });
    monta();
    preenche();
    fireEvent.click(screen.getByTestId("sharkscope-simular"));
    await waitFor(() => expect(importar).toHaveBeenCalled());
    expect(screen.queryByTestId("sharkscope-aplicar")).toBeNull();
  });

  /**
   * JSON torto vira FRASE, e não código de erro.
   *
   * "nao podemos retornar codigo de erro para o usuario, temos que ter o erro tratado" (o dono,
   * 16/09). E o parse acontece antes da rede: não faz sentido gastar uma ida ao servidor para
   * descobrir que o texto colado não fecha as chaves.
   */
  it("JSON invalido vira frase, e nao chega a chamar a API", async () => {
    monta();
    preenche("isto nao e json {{{");
    fireEvent.click(screen.getByTestId("sharkscope-simular"));
    const erro = await screen.findByTestId("sharkscope-erro");
    expect(erro.textContent).toMatch(/JSON válido/i);
    expect(importar).not.toHaveBeenCalled();
  });

  it("mostra os nossos torneios sem correspondencia, que foi o que achou o AY-46", async () => {
    importar.mockResolvedValue(PLANO);
    monta();
    preenche();
    fireEvent.click(screen.getByTestId("sharkscope-simular"));
    expect(await screen.findByText(/sem correspondência/i)).toBeTruthy();
    expect(screen.getByText(/1 mãos/)).toBeTruthy();
  });

  it("sem user_id ou sem JSON, o simular fica travado", () => {
    monta();
    expect((screen.getByTestId("sharkscope-simular") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByTestId("sharkscope-user"), { target: { value: "3" } });
    expect((screen.getByTestId("sharkscope-simular") as HTMLButtonElement).disabled).toBe(true);
  });
});
