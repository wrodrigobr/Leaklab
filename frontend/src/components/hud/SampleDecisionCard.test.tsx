// @vitest-environment jsdom
/**
 * O exemplo de análise tem que ser a análise de verdade.
 *
 * O que havia aqui era um card escrito à mão: equity 34% contra 42%, uma frase, e nada da
 * evidência que o produto produz. Quem o via não via o produto, via uma maquete dele.
 *
 * Dois guardas, e o segundo é o que envelhece bem:
 *
 * 1. **O dado é real.** O teste lê a MESMA fixture que o backend serve (o arquivo, não uma
 *    cópia), então uma fixture que empobreça derruba o teste do frontend também.
 * 2. **A vitrine não é uma cópia.** O exemplo é renderizado pelo `SidePanels`, o mesmo
 *    componente do Replayer. Uma cópia da apresentação passa a mentir sozinha no dia em que o
 *    card real muda, e ninguém percebe porque nada quebra.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const FIXTURE = "../backend/fixtures/decisao_exemplo.json";
const decisao = JSON.parse(readFileSync(FIXTURE, "utf-8"));

// O `t` devolve a chave E os valores interpolados: posição e stack chegam ao card por dentro de
// `card.ctxVs`, então um mock que descarta as opções esconderia justamente o que se quer medir.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k} ${Object.values(o).join(" ")}` : k,
    i18n: { language: "pt-BR" },
  }),
}));

const pedir = vi.fn();
vi.mock("@/lib/api", () => ({
  sample: { decision: () => pedir() },
  coachDashboard: { improveAnnotation: vi.fn() },
}));

import { SampleDecisionCard } from "./SampleDecisionCard";

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SampleDecisionCard />
    </QueryClientProvider>,
  );
}

beforeEach(() => { pedir.mockReset(); });
afterEach(() => cleanup());

describe("exemplo de análise — o dado é real", () => {
  it("renderiza a evidência da decisão que o backend serve", async () => {
    pedir.mockResolvedValue({ decision: decisao });
    montar();

    const pg = decisao.preflop_gto;
    // A mão e o contexto vêm da fixture, não de constantes deste teste: trocar a mão escolhida
    // não quebra o teste, empobrecê-la quebra.
    await waitFor(() => expect(screen.getAllByText(new RegExp(pg.hand_type)).length).toBeGreaterThan(0));

    const texto = document.body.textContent ?? "";
    // A posição do HERÓI não aparece no card de preflop: num cenário `vs_rfi` o contexto é
    // "vs CO", e a do herói fica implícita. Medido, não suposto — a primeira versão deste teste
    // cobrava `pg.position` e falhou por isso.
    expect(texto, "posição do vilão").toContain(pg.vs_position);
    expect(texto, "profundidade de referência").toContain(pg.stack_bucket);
    // % da range de defesa, com uma casa — é a barra que o card desenha
    expect(texto, "range de defesa").toContain((pg.range_pct * 100).toFixed(0));
    // equity da mão vs range
    expect(texto, "equity").toContain((decisao.hand_equity * 100).toFixed(1));
  });

  it("mostra as frequências por ação, que é o que o exemplo antigo não tinha", async () => {
    pedir.mockResolvedValue({ decision: decisao });
    montar();

    const freq: Record<string, number> = decisao.preflop_gto.hand_freq;
    const comFreq = Object.entries(freq).filter(([, v]) => v > 0.001);
    expect(comFreq.length, "a fixture não tem frequência nenhuma").toBeGreaterThan(0);

    await waitFor(() => {
      const texto = document.body.textContent ?? "";
      for (const [, v] of comFreq) {
        expect(texto, `frequência ${(v * 100).toFixed(1)}% ausente`).toContain((v * 100).toFixed(1));
      }
    });
  });

  it("não renderiza nada quando o backend não tem exemplo", async () => {
    // A landing é vitrine, não caminho crítico: sem exemplo, sai de cena em silêncio. Uma
    // mensagem de erro numa landing é pior do que a ausência do card.
    pedir.mockRejectedValue(new Error("HTTP 404"));
    const { container } = montar();
    await waitFor(() => expect(container.textContent).toBe(""));
  });
});

describe("exemplo de análise — a vitrine não é uma cópia", () => {
  it("usa o mesmo componente que renderiza a análise real", () => {
    const src = readFileSync("src/components/hud/SampleDecisionCard.tsx", "utf-8");
    expect(src, "o exemplo tem que consumir o SidePanels do replayer")
      .toContain('from "@/components/replayer/SidePanels"');
  });

  it("não escreve evidência à mão", () => {
    // O card antigo montava a própria evidência em JSX (equity/necessária em <span>). Se isso
    // voltar, a vitrine volta a divergir do produto sem quebrar nada — a falha silenciosa.
    const src = readFileSync("src/components/hud/SampleDecisionCard.tsx", "utf-8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(src, "evidência montada à mão de volta no exemplo").not.toMatch(/evidence\s*=/);
    expect(src, "número cravado na vitrine").not.toMatch(/\b\d{2}%/);
  });
});
