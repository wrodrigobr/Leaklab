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
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";
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

/** O olho de detalhes, sem depender de qual é o estado inicial. Desde 08/08 os INDICADORES
 *  (cenário, posição do vilão, barra de frequência por ação) vivem atrás dele — o usuário pediu
 *  que o ícone tivesse trabalho, e a divisão ficou "leitura sempre visível, auditoria no toggle".
 *  O `t` mockado devolve a chave, então o título do botão é a chave crua. Escrever
 *  `getByTitle("card.toggleShow")` cravaria o padrão fechado, que nesta superfície não é o caso —
 *  e um teste que crava o default quebra na próxima vez que o default mudar, sem nada de errado
 *  no produto. Foi assim que este arquivo quebrou. */
function alternarDetalhes() {
  fireEvent.click(screen.getByTitle(/^card\.toggle(Show|Hide)$/));
}

/** Garante o olho ABERTO, seja qual for o default. */
function abrirDetalhes() {
  if (screen.queryByTitle("card.toggleShow")) alternarDetalhes();
}

describe("exemplo de análise — o dado é real", () => {
  it("renderiza a evidência da decisão que o backend serve", async () => {
    pedir.mockResolvedValue({ decision: decisao });
    montar();

    const pg = decisao.preflop_gto;
    // A mão e o contexto vêm da fixture, não de constantes deste teste: trocar a mão escolhida
    // não quebra o teste, empobrecê-la quebra.
    await waitFor(() => expect(screen.getAllByText(new RegExp(pg.hand_type)).length).toBeGreaterThan(0));

    // CONTROLE, e ele vem primeiro: a LEITURA do card não depende do olho. Se um dia isto
    // quebrar, o problema é o card ter escondido o que se propõe a responder, não este teste.
    expect(document.body.textContent ?? "", "profundidade de referência")
      .toContain(pg.stack_bucket);

    // Os DADOS de auditoria abrem no olho desde 08/08 — a primeira versão deste teste media o
    // card fechado e passou a falhar ali, sem que nada estivesse errado no produto.
    abrirDetalhes();
    const texto = document.body.textContent ?? "";
    // A posição do HERÓI não aparece no card de preflop: num cenário `vs_rfi` o contexto é
    // "vs CO", e a do herói fica implícita. Medido, não suposto — a primeira versão deste teste
    // cobrava `pg.position` e falhou por isso.
    expect(texto, "posição do vilão").toContain(pg.vs_position);
    // % da range de defesa, com uma casa — é a barra que o card desenha
    expect(texto, "range de defesa").toContain((pg.range_pct * 100).toFixed(0));
    // equity da mão vs range
    expect(texto, "equity").toContain((decisao.hand_equity * 100).toFixed(1));
  });

  it("mostra as frequências por ação, que é o que o exemplo antigo não tinha", async () => {
    // Desde 17/08 a vitrine mostra o layout V2 por padrão (`defaultCardV2` — decisão do dono:
    // a landing vende o card novo). No v2 as barras de frequência são SEMPRE visíveis, sem
    // olho, com percentual inteiro. A versão anterior deste teste media o clássico (uma casa
    // decimal atrás do olho) e quebrou exatamente quando o default mudou — como avisado no
    // comentário do `alternarDetalhes`.
    pedir.mockResolvedValue({ decision: decisao });
    montar();

    const freq: Record<string, number> = decisao.preflop_gto.hand_freq;
    const comFreq = Object.entries(freq).filter(([, v]) => v > 0.001);
    expect(comFreq.length, "a fixture não tem frequência nenhuma").toBeGreaterThan(0);

    await waitFor(() => expect(
      screen.getAllByText(new RegExp(decisao.preflop_gto.hand_type)).length).toBeGreaterThan(0));

    const texto = document.body.textContent ?? "";
    // GUARDA do "força o v2 no sample": o rótulo de frequência do v2 presente prova que a
    // vitrine está no layout novo. Se o default regredir para o clássico, isto acusa.
    expect(texto, "a vitrine não está no layout v2").toContain("card.v2Freq");
    for (const [, v] of comFreq) {
      expect(texto, `frequência ${(v * 100).toFixed(0)}% ausente`)
        .toContain(`${(v * 100).toFixed(0)}%`);
    }
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
