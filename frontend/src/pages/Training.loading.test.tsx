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
// O mock resolve a chave contra o BUNDLE pt-BR de verdade, em vez de devolver o
// `defaultValue`. Antes ele era `(k, d) => d ?? k`, e por isso este teste passou a depender de
// uma cópia da copy cravada no componente: quando o `defaultValue` saiu (a chave já existia,
// com o texto idêntico), o teste caiu sem que nada mudasse para o jogador. Lendo o bundle, ele
// verifica o texto que a pessoa REALMENTE vê — e cai se a chave sumir do locale.
vi.mock("react-i18next", async () => {
  const bundle = (await import("@/i18n/locales/pt-BR/training.json")).default as
    Record<string, unknown>;
  const resolve = (chave: string) => {
    let no: unknown = bundle;
    for (const parte of chave.split(".")) {
      if (typeof no === "object" && no !== null && parte in no) {
        no = (no as Record<string, unknown>)[parte];
      } else {
        return chave;
      }
    }
    return typeof no === "string" ? no : chave;
  };
  return {
    useTranslation: () => ({ t: (k: string) => resolve(k), i18n: { language: "pt-BR" } }),
  };
});
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
    /* O esqueleto não pode bloquear quem já sabe onde quer ir. O contrato mudou TRÊS vezes, e
     * as três por decisão de produto, nunca por defeito:
     *   19/08 — a Academia saiu desta tela (foi para /study: estudar ≠ treinar);
     *   20/08 — a TRILHA foi promovida a /training e esta virou o legado (/training/classic),
     *           com um convite discreto apontando para a trilha;
     *   28/08 — REVERTIDO: esta voltou a ser /training, por decisão do dono ("a princípio não
     *           iremos mais utilizar" a beta). O convite saiu junto, e não por estilo: com
     *           /training servindo esta tela, o link apontaria para ela mesma. A trilha
     *           sobrevive em /training/trilha, sem link em lugar nenhum.
     *
     * Por isso a asserção agora é NEGATIVA nos dois: nem /training (auto-link) nem
     * /training/trilha (a beta oculta) podem aparecer aqui. */
    const { container } = montar();
    const destinos = [...container.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
    expect(destinos).toEqual(expect.arrayContaining(["/ghost", "/leak-trainer"]));
    expect(destinos).not.toContain("/academy");
    expect(destinos).not.toContain("/training");         // esta tela É /training: não se auto-linka
    expect(destinos).not.toContain("/training-v2");      // a rota do beta virou redirect
    expect(destinos).not.toContain("/training/trilha");  // a beta está oculta, sem porta de entrada
  });
});
