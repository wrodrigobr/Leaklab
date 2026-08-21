// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor, within, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * A vitrine do programa de fundadores.
 *
 * Por que teste de componente e não só de API: o backend pode devolver os números certos e a
 * tela ainda assim contar a história errada — foi por isso que este projeto já colocou 90
 * vereditos errados na tela com o cálculo correto por trás. Aqui o que está travado é a
 * LEITURA:
 *
 *   1. os três estados do trato são visualmente distintos e nomeados pelo que significam;
 *   2. quem usa muito e não fala NÃO aparece como se estivesse honrando (é o caso que a
 *      métrica de engajamento apagaria);
 *   3. quem vence primeiro aparece primeiro — a ordem da lista é a ordem da ação;
 *   4. vencimento próximo e vencido são visualmente diferentes de prazo folgado.
 */

const { founders, grantFounders, revokeFounder, users, founderCandidates } = vi.hoisted(() => ({
  founders: vi.fn(), grantFounders: vi.fn(), revokeFounder: vi.fn(), users: vi.fn(),
  founderCandidates: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  adminDashboard: { founders, grantFounders, revokeFounder, users, founderCandidates },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));

import { FoundersTab } from "./FoundersTab";

function fundador(over: Partial<Record<string, unknown>> = {}) {
  return {
    user_id: 1, username: "ana", email: "ana@t.com",
    desde: "2026-08-01T00:00:00", expira_em: "2027-02-01T00:00:00",
    dias_restantes: 164, ultimo_acesso: "2026-08-20T00:00:00",
    torneios: 3, ultimo_import: "2026-08-19T00:00:00",
    treinos: 40, dias_treinados: 5,
    feedbacks: 2, ultimo_feedback: "2026-08-18T00:00:00",
    usou: true, honrando: true, ...over,
  };
}

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><FoundersTab /></QueryClientProvider>);
}

beforeEach(() => {
  founders.mockReset(); grantFounders.mockReset(); revokeFounder.mockReset();
  users.mockReset(); users.mockResolvedValue({ users: [] });
  founderCandidates.mockReset(); founderCandidates.mockResolvedValue({ candidatos: [] });
});
afterEach(() => cleanup());

describe("programa de fundadores — a vitrine", () => {
  it("sem fundadores, explica o que a tela vai mostrar em vez de ficar vazia", async () => {
    founders.mockResolvedValue({
      founders: [], resumo: { total: 0, honrando: 0, silenciosos: 0, vencendo_em_30d: 0 },
    });
    montar();
    expect(await screen.findByText(/Nenhum fundador ainda/i)).toBeTruthy();
    expect(screen.getByText(/o que cada um usou e o que devolveu/i)).toBeTruthy();
  });

  it("separa na tela quem honra o trato de quem só usa", async () => {
    founders.mockResolvedValue({
      founders: [
        fundador({ user_id: 1, username: "honra", honrando: true, usou: true, feedbacks: 2 }),
        fundador({ user_id: 2, username: "sousa", honrando: false, usou: true, feedbacks: 0,
                   dias_restantes: 165 }),
        fundador({ user_id: 3, username: "sumiu", honrando: false, usou: false, feedbacks: 0,
                   torneios: 0, treinos: 0, dias_treinados: 0, dias_restantes: 166 }),
      ],
      resumo: { total: 3, honrando: 1, silenciosos: 1, vencendo_em_30d: 0 },
    });
    montar();
    await screen.findByText("honra");

    const linha = (nome: string) => screen.getByText(nome).closest("tr")!;
    expect(within(linha("honra")).getByText(/Honrando/i)).toBeTruthy();
    // O caso que uma métrica de engajamento apagaria: usa MUITO e não devolve nada.
    expect(within(linha("sousa")).getByText(/Usa, não fala/i)).toBeTruthy();
    expect(within(linha("sousa")).queryByText(/Honrando/i)).toBeNull();
    expect(within(linha("sumiu")).getByText(/Silencioso/i)).toBeTruthy();
  });

  it("põe quem vence primeiro no topo — a ordem da lista é a ordem da ação", async () => {
    founders.mockResolvedValue({
      founders: [
        fundador({ user_id: 1, username: "folgado", dias_restantes: 150 }),
        fundador({ user_id: 2, username: "urgente", dias_restantes: 4 }),
        fundador({ user_id: 3, username: "medio",   dias_restantes: 60 }),
      ],
      resumo: { total: 3, honrando: 3, silenciosos: 0, vencendo_em_30d: 1 },
    });
    montar();
    await screen.findByText("urgente");
    const nomes = screen.getAllByRole("row").slice(1)
      .map((tr) => within(tr).getAllByRole("cell")[0].textContent || "");
    expect(nomes[0]).toContain("urgente");
    expect(nomes[2]).toContain("folgado");
  });

  it("mostra vencido como vencido, não como prazo restante negativo", async () => {
    founders.mockResolvedValue({
      founders: [fundador({ username: "expirou", dias_restantes: -5 })],
      resumo: { total: 1, honrando: 1, silenciosos: 0, vencendo_em_30d: 0 },
    });
    montar();
    expect(await screen.findByText(/venceu há 5d/i)).toBeTruthy();
    expect(screen.queryByText(/-5d restantes/)).toBeNull();
  });

  it("busca sem resultado DIZ que não achou, em vez de ficar muda", async () => {
    // O caso real: digitar um e-mail válido devolvia lista vazia e silêncio, indistinguível
    // de "ainda carregando" — parecia tela quebrada.
    founders.mockResolvedValue({
      founders: [], resumo: { total: 0, honrando: 0, silenciosos: 0, vencendo_em_30d: 0 },
    });
    users.mockResolvedValue({ users: [] });
    const { container } = montar();
    await screen.findByText(/Nenhum fundador ainda/i);

    const campo = container.querySelector('input[placeholder*="nome ou email"]') as HTMLInputElement;
    fireEvent.change(campo, { target: { value: "naoexiste@t.com" } });

    await waitFor(() => expect(screen.getByText(/Nenhuma conta encontrada/i)).toBeTruthy());
    // E precisa dizer o PORQUÊ, senão quem opera não sabe qual é o próximo passo.
    expect(screen.getByText(/já ter conta/i)).toBeTruthy();
  });

  it("não esconde conta por causa do papel — mostra o papel e deixa decidir", async () => {
    founders.mockResolvedValue({
      founders: [], resumo: { total: 0, honrando: 0, silenciosos: 0, vencendo_em_30d: 0 },
    });
    users.mockResolvedValue({ users: [{ id: 9, username: "phpro", email: "eu@t.com", role: "admin" }] });
    const { container } = montar();
    await screen.findByText(/Nenhum fundador ainda/i);

    const campo = container.querySelector('input[placeholder*="nome ou email"]') as HTMLInputElement;
    fireEvent.change(campo, { target: { value: "eu@t.com" } });

    await waitFor(() => expect(screen.getByText("phpro")).toBeTruthy());
    expect(screen.getByText("admin")).toBeTruthy();
    // A chamada não pode filtrar por papel: era isso que sumia com a conta sem avisar.
    expect(users).toHaveBeenCalledWith(expect.not.objectContaining({ role: expect.anything() }));
  });

  it("a fila mostra a posição e o que o candidato já fez antes de aprovar", async () => {
    // Aprovar às cegas é o que enche o programa de silencioso: 6 meses de Pro para quem
    // nunca abriu nada. A fila precisa dar o sinal ANTES do clique.
    founders.mockResolvedValue({
      founders: [], resumo: { total: 0, honrando: 0, silenciosos: 0, vencendo_em_30d: 0 },
    });
    founderCandidates.mockResolvedValue({
      candidatos: [
        { id: 1, username: "chegou1o", email: "a@t.com", founder_applied_at: "2026-08-01T10:00:00",
          created_at: null, acquisition_source: "instagram", email_verified: 1,
          torneios: 2, treinos: 30, posicao: 1 },
        { id: 2, username: "naoconfirmou", email: "b@t.com", founder_applied_at: "2026-08-01T11:00:00",
          created_at: null, acquisition_source: null, email_verified: 0,
          torneios: 0, treinos: 0, posicao: 2 },
      ],
    });
    montar();
    await screen.findByText("chegou1o");

    expect(screen.getByText(/2 candidato\(s\) esperando/i)).toBeTruthy();
    const linha = (n: string) => screen.getByText(n).closest("tr")!;
    expect(within(linha("chegou1o")).getByText(/2 torneio/)).toBeTruthy();
    expect(within(linha("chegou1o")).getByText("instagram")).toBeTruthy();
    // Conta não confirmada não recebe e-mail nem entra: aprovar gastaria a vaga com quem
    // ainda está preso na porta.
    expect(within(linha("naoconfirmou")).getByText(/não confirmou/i)).toBeTruthy();
    expect(within(linha("chegou1o")).queryByText(/não confirmou/i)).toBeNull();
  });

  it("sem candidatos, a fila não ocupa espaço na tela", async () => {
    founders.mockResolvedValue({
      founders: [], resumo: { total: 0, honrando: 0, silenciosos: 0, vencendo_em_30d: 0 },
    });
    founderCandidates.mockResolvedValue({ candidatos: [] });
    montar();
    await screen.findByText(/Nenhum fundador ainda/i);
    expect(screen.queryByText(/candidato\(s\) esperando/i)).toBeNull();
  });

  it("o resumo mostra os quatro números que decidem a renovação", async () => {
    founders.mockResolvedValue({
      founders: [fundador()],
      resumo: { total: 7, honrando: 3, silenciosos: 2, vencendo_em_30d: 1 },
    });
    montar();
    await waitFor(() => expect(screen.getByText("7")).toBeTruthy());
    expect(screen.getByText(/honrando o trato/i)).toBeTruthy();
    expect(screen.getByText(/nunca usaram nada/i)).toBeTruthy();
    expect(screen.getByText(/vencem em 30 dias/i)).toBeTruthy();
  });
});
