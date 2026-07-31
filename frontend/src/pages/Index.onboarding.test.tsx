// @vitest-environment jsdom
/**
 * O modal de PRIMEIRO ACESSO tem que chegar ao DOM.
 *
 * Ele existia só dentro do `return` do dashboard clássico, e `dashV2` é fixo em `true` — ou
 * seja, o ramo que renderizava o modal nunca rodava. O jogador novo caía num dashboard vazio
 * sem nenhuma orientação, e a leitura de fora era "o onboarding não funciona".
 *
 * Por isso o teste monta a página INTEIRA e olha o DOM, em vez de testar o estado: o bug não
 * estava no estado (que era `true` corretamente), estava no caminho de renderização. Um teste
 * de `showOnboarding` teria passado com o bug em produção.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { UserProfile } from "@/lib/api";

// --- dublês -----------------------------------------------------------------
// O V2 real arrasta a árvore inteira do dashboard (charts, dnd, i18n). Aqui o que importa é
// só QUEM é renderizado junto dele.
vi.mock("@/components/hud/DashboardV2", () => ({
  DashboardV2: () => <div data-testid="dash-v2" />,
}));
vi.mock("@/components/hud/OnboardingModal", () => ({
  OnboardingModal: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="onboarding-modal">
      <button onClick={onClose}>fechar</button>
    </div>
  ),
}));
vi.mock("@/components/hud/AcceptCoachModal", () => ({
  AcceptCoachModal: () => <div data-testid="accept-coach-modal" />,
}));
vi.mock("@/components/hud/HudHeader", () => ({
  HudHeader: () => <div data-testid="hud-header" />,
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: "pt-BR" } }),
}));

const vazio = () => new Promise(() => {});   // promessa que nunca resolve = "ainda carregando"
vi.mock("@/lib/api", () => {
  const nunca = () => vazio();
  return {
    metrics: new Proxy({}, { get: () => nunca }),
    tournaments:  { list: nunca },
    support:      { unreadCount: nunca },
    preferences:  { get: nunca, save: nunca },
  };
});

let usuarioAtual: UserProfile | null = null;
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: usuarioAtual, refreshUser: vi.fn(), isLoading: false }),
}));

import Index from "./Index";

const jogador = (onboarding_completed: boolean): UserProfile => ({
  user_id: 1,
  username: "novato",
  email: "novato@example.com",
  role: "player",
  plan: "free",
  onboarding_completed,
} as UserProfile);

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Index />
    </QueryClientProvider>,
  );
}

beforeEach(() => { usuarioAtual = null; });
afterEach(() => cleanup());

describe("modal de primeiro acesso no dashboard", () => {
  it("aparece para quem ainda não completou o onboarding", () => {
    usuarioAtual = jogador(false);
    montar();
    // O ramo V2 é o que roda de verdade: se o modal só existir no clássico, isto falha.
    expect(screen.getByTestId("dash-v2")).toBeTruthy();
    expect(screen.getByTestId("onboarding-modal")).toBeTruthy();
  });

  it("não aparece para quem já completou", () => {
    usuarioAtual = jogador(true);
    montar();
    expect(screen.queryByTestId("onboarding-modal")).toBeNull();
  });

  it("aparece mesmo quando o usuário chega DEPOIS da primeira renderização", async () => {
    // Cobre o inicializador congelado do useState: monta sem `user` (como se o /auth/me ainda
    // estivesse no ar) e só então entrega o perfil. Sem o efeito de sincronia, o valor `false`
    // da primeira renderização ficaria preso e o modal nunca abriria.
    usuarioAtual = null;
    const { rerender } = montar();
    expect(screen.queryByTestId("onboarding-modal")).toBeNull();

    usuarioAtual = jogador(false);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    rerender(
      <QueryClientProvider client={qc}>
        <Index />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("onboarding-modal")).toBeTruthy());
  });
});
