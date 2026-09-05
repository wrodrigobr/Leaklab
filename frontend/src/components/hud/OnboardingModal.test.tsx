// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

/**
 * O X do onboarding fecha? (AY-5, 05/09)
 *
 * O dono reportou que "o onboarding nao esta fechando ao clicar no x" e depois achou que era
 * alarme falso. O teste de onboarding existente (`Index.onboarding.test.tsx`) MOCKA o modal
 * inteiro, entao o X nunca foi exercitado por teste nenhum.
 *
 * O caminho do X: `complete()` -> await completeOnboarding() -> await refreshUser() -> onClose().
 * Tres cenarios, porque o sintoma depende do que a API faz:
 *   1. API responde     -> fecha
 *   2. API falha        -> fecha mesmo assim (o catch engole; o estado sincroniza no proximo login)
 *   3. API NUNCA responde -> NAO fecha. Este e o unico jeito de reproduzir o sintoma reportado:
 *      o modal fica preso esperando a rede. Se o dono viu isso, foi API lenta/travada — nao
 *      bug do botao. Documentado aqui para a proxima vez que alguem reportar.
 */
const completeOnboarding = vi.fn();
const refreshUser = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o && "current" in o ? `${k}` : k) }),
}));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@/lib/api", () => ({ auth: { completeOnboarding: (...a: unknown[]) => completeOnboarding(...a) } }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ refreshUser: (...a: unknown[]) => refreshUser(...a) }) }));
vi.mock("@/components/hud/HandExportGuide", () => ({ HandExportGuide: () => null }));

import { OnboardingModal } from "./OnboardingModal";

beforeEach(() => { completeOnboarding.mockReset(); refreshUser.mockReset(); });
afterEach(cleanup);

const clicaNoX = () => fireEvent.click(screen.getByLabelText("skip"));

describe("o X do onboarding", () => {
  it("fecha quando a API responde", async () => {
    completeOnboarding.mockResolvedValue({});
    refreshUser.mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(<OnboardingModal onClose={onClose} />);
    clicaNoX();
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(completeOnboarding).toHaveBeenCalledTimes(1);
  });

  it("fecha mesmo quando a API falha", async () => {
    completeOnboarding.mockRejectedValue(new Error("rede"));
    const onClose = vi.fn();
    render(<OnboardingModal onClose={onClose} />);
    clicaNoX();
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("NAO fecha enquanto a API nao responde — o unico jeito de reproduzir o sintoma", async () => {
    completeOnboarding.mockReturnValue(new Promise(() => {}));   // pendura para sempre
    const onClose = vi.fn();
    render(<OnboardingModal onClose={onClose} />);
    clicaNoX();
    await new Promise((r) => setTimeout(r, 50));
    expect(onClose).not.toHaveBeenCalled();
    // e um 2o clique e ignorado pelo `if (saving) return`: nao ha como o usuario forcar
    clicaNoX();
    await new Promise((r) => setTimeout(r, 50));
    expect(completeOnboarding).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });
});
