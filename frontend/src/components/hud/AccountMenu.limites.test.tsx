// @vitest-environment jsdom
/**
 * O menu da conta nao inventa teto de plano.
 *
 * Auditoria NLU-10 (15/09): sem `plan_limits` no payload, o menu caia em
 * `{ tournaments: 3, ai_calls: 10 }`, que nao e o limite de plano nenhum. O free do backend e
 * 30 torneios e 15 analises (`PLAN_LIMITS` em `database/repositories.py`), entao a barra
 * desenhava "2/3 usado, quase no teto" em vermelho para quem tinha 28 torneios de folga.
 *
 * Agora: teto conhecido mostra o numero, `null` mostra "ilimitado" e ausente mostra "…".
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const usuario = vi.hoisted(() => ({ atual: null as unknown }));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: usuario.atual,
    logout: () => {},
    refreshUser: async () => {},
  }),
}));

import { AccountMenu } from "@/components/hud/AccountMenu";

const BASE = {
  user_id: 1, username: "rullian", email: "r@x.com", role: "player",
  coach_id: null, coach_username: null, plan: "free",
  tournaments_used: 2, ai_calls_used: 1,
};

function montar(user: Record<string, unknown>) {
  usuario.atual = user;
  render(<MemoryRouter><AccountMenu /></MemoryRouter>);
  // o menu comeca fechado; o gatilho e o primeiro botao (o nome do usuario)
  fireEvent.click(screen.getAllByRole("button")[0]);
}

afterEach(() => { cleanup(); usuario.atual = null; });

describe("AccountMenu: o teto vem do backend ou nao vem", () => {
  it("sem plan_limits nao inventa 3/10: mostra o usado e reticencias", () => {
    montar({ ...BASE });
    expect(screen.getByText("2/…")).toBeTruthy();
    expect(screen.getByText("1/…")).toBeTruthy();
    expect(screen.queryByText("2/3")).toBeNull();
    expect(screen.queryByText("1/10")).toBeNull();
  });

  it("com os limites do free do backend mostra 2/30 e 1/15", () => {
    montar({ ...BASE, plan_limits: { tournaments: 30, ai_calls: 15 } });
    expect(screen.getByText("2/30")).toBeTruthy();
    expect(screen.getByText("1/15")).toBeTruthy();
  });

  it("teto null (coach, pro) segue escrito como ilimitado", () => {
    montar({ ...BASE, plan: "pro", plan_limits: { tournaments: null, ai_calls: null } });
    expect(screen.getAllByText(/ilimitado/i).length).toBe(2);
  });
});
