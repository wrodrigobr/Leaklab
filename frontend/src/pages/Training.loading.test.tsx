// @vitest-environment jsdom
/**
 * Enquanto o /training carrega, a página não pode parecer PRONTA e vazia.
 *
 * Reportado: "primeiro ela carrega só os 3 botões de revisão, treino e academia, e só depois
 * carrega as outras coisas (...) muitas vezes a demora é tanta que parece que não tem mais nada
 * na página (...) isso pode direcionar o usuário a clicar em algo antes de ver o conteúdo".
 *
 * A causa era estrutural: TODO o conteúdo abaixo dos atalhos estava atrás de `{overview && ...}`,
 * com fallbacks `?? []`. Sem `overview` a página renderizava três links e nada mais — e três
 * links e nada mais é indistinguível de uma página que terminou de carregar. Página vazia é uma
 * afirmação, e era a afirmação errada.
 *
 * O teste monta a página com a consulta PENDENTE (promessa que nunca resolve) e cobra o
 * esqueleto no DOM. Testar o estado (`isPending === true`) não serviria: o estado sempre esteve
 * certo, o que faltava era alguém renderizar alguma coisa a partir dele.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const pendenteParaSempre = () => new Promise(() => {});

const respostas = vi.hoisted(() => ({ overview: null as unknown }));

vi.mock("@/lib/api", () => ({
  training: {
    overview: () => (respostas.overview === null
      ? pendenteParaSempre()
      : Promise.resolve(respostas.overview)),
    proof: () => pendenteParaSempre(),
  },
  progression: { status: () => pendenteParaSempre() },
}));

vi.mock("@/components/hud/HudLayout", () => ({
  HudLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/training/DailyChallengeCard", () => ({
  DailyChallengeCard: () => <div data-testid="daily" />,
}));
vi.mock("@/components/training/MasteryGate", () => ({ MasteryGate: () => null }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, d?: string) => d ?? k, i18n: { language: "pt-BR" } }),
}));
vi.mock("@/lib/spotLabel", () => ({ useSpotLabel: () => (k: string) => k }));

import Training from "./Training";

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <Training />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => { cleanup(); respostas.overview = null; });

describe("carregamento do /training", () => {
  it("mostra esqueleto enquanto o overview não chega", () => {
    const { container } = montar();
    const ocupado = container.querySelector('[aria-busy="true"]');
    expect(ocupado, "nada no DOM diz que a página ainda está carregando").not.toBeNull();
    expect(screen.getByText("Carregando seu treino…")).toBeTruthy();
  });

  it("o esqueleto não é um traço fino: ocupa o lugar do conteúdo que vem", () => {
    // Esqueleto menor que o conteúdo empurra a página quando os dados chegam, e o clique do
    // jogador cai noutro lugar — a versão PIOR do problema relatado.
    const { container } = montar();
    const blocos = container.querySelectorAll('[aria-busy="true"] .animate-pulse');
    expect(blocos.length).toBeGreaterThanOrEqual(8);
  });

  it("os atalhos continuam clicáveis durante o carregamento", () => {
    // O esqueleto não pode bloquear quem já sabe onde quer ir. A Academia SAIU desta tela
    // em 19/08 (mudou para /study — separar estudar de treinar foi decisão de produto), então
    // o contrato dos atalhos é: revisão, treino e o convite da trilha.
    const { container } = montar();
    const destinos = [...container.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
    expect(destinos).toEqual(expect.arrayContaining(["/ghost", "/leak-trainer", "/training-v2"]));
    expect(destinos).not.toContain("/academy");
  });
});
