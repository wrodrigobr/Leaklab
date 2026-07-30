// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { V2EvTrendCard } from "./V2EvTrendCard";
import type { EvSummary } from "@/lib/api";

/**
 * O card de tendência responde "estou melhorando ou piorando?".
 *
 * ── O que o usuário reportou ──────────────────────────────────────────────────────────────────
 *
 * "este gráfico não é tão intuitivo, não sei se estou melhorando ou piorando na perda de EV".
 * O gráfico invertia a convenção (subir = perder mais = pior), avisava disso em 9px cinza no
 * canto, plotava um torneio por ponto (ruído, não tendência) e não respondia a pergunta.
 *
 * ── O que este arquivo trava ──────────────────────────────────────────────────────────────────
 *
 * Que a RESPOSTA apareça em texto, com a direção correta, e que ela venha da comparação do
 * SERVIDOR (`ev_per_100_recent` vs `ev_per_100_prev`) — inclusive o caso em que o servidor diz
 * "não sei" devolvendo `null`, onde o card não pode inventar direção.
 *
 * Direção é o detalhe que mais fácil se inverte num refactor: EV perdido MENOR é MELHOR, então
 * `recent < prev` significa melhora. Um sinal trocado aqui elogiaria quem está piorando.
 */
afterEach(cleanup);

// O `ResponsiveContainer` do recharts usa ResizeObserver, que o jsdom nao implementa. O stub
// devolve 0x0, e por isso o teste afirma sobre o TEXTO do card (veredito, legenda, dica) e nunca
// sobre geometria do SVG — que num container de tamanho zero nao existiria de qualquer forma.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;

const serie = [0.4, 3.1, 10.2, 5.2, 7.1, 3.4, 0.6, 1.9, 12.0, 8.9, 5.9, 11.2];

function base(extra: Partial<EvSummary> = {}): EvSummary {
  return {
    has_data: true,
    series: serie.map((v, i) => ({ tournament_id: i + 1, name: "MTT $1.10", ev_per_100: v })),
    ...extra,
  } as EvSummary;
}

describe("V2EvTrendCard — a resposta em texto", () => {
  it("diz MELHORANDO quando o EV perdido recente é menor", () => {
    const { container } = render(
      <V2EvTrendCard evSummary={base({ ev_per_100_recent: 4.2, ev_per_100_prev: 8.1 })} />);
    const txt = container.textContent ?? "";
    expect(txt).toContain("v2.trendBetter");
    expect(txt).not.toContain("v2.trendWorse");
  });

  it("diz PIORANDO quando o EV perdido recente é maior", () => {
    const { container } = render(
      <V2EvTrendCard evSummary={base({ ev_per_100_recent: 9.4, ev_per_100_prev: 5.0 })} />);
    const txt = container.textContent ?? "";
    expect(txt).toContain("v2.trendWorse");
    expect(txt).not.toContain("v2.trendBetter");
  });

  it("não inventa direção com diferença abaixo de 1bb/100", () => {
    const { container } = render(
      <V2EvTrendCard evSummary={base({ ev_per_100_recent: 5.2, ev_per_100_prev: 5.6 })} />);
    const txt = container.textContent ?? "";
    expect(txt).toContain("v2.trendStable");
    expect(txt).not.toContain("v2.trendBetter");
    expect(txt).not.toContain("v2.trendWorse");
  });

  it("respeita o 'não sei' do servidor em vez de calcular por conta própria", () => {
    // O servidor devolve null abaixo de 10 decisões ("amostra pequena demais pra taxa honesta").
    // O card tem a série inteira em mãos e NÃO pode usar isso para afirmar tendência.
    const { container } = render(
      <V2EvTrendCard evSummary={base({ ev_per_100_recent: 4.2, ev_per_100_prev: null })} />);
    const txt = container.textContent ?? "";
    expect(txt).toContain("v2.trendNoSample");
    expect(txt).not.toContain("v2.trendBetter");
    expect(txt).not.toContain("v2.trendWorse");
  });
});

describe("V2EvTrendCard — leitura do gráfico", () => {
  it("nomeia as duas linhas e diz que subir é melhorar", () => {
    const { container } = render(
      <V2EvTrendCard evSummary={base({ ev_per_100_recent: 4.2, ev_per_100_prev: 8.1 })} />);
    const txt = container.textContent ?? "";
    expect(txt).toContain("v2.trendAvgLabel");   // a média móvel, linha principal
    expect(txt).toContain("v2.trendRawLabel");   // a série crua, ao fundo
    expect(txt).toContain("v2.trendHintUp");     // "linha subindo = melhorando"
  });

  it("não renderiza com menos de 2 pontos (nada a comparar)", () => {
    const um = { has_data: true, series: [{ tournament_id: 1, name: "x", ev_per_100: 5 }] } as EvSummary;
    const { container } = render(<V2EvTrendCard evSummary={um} />);
    expect(container.textContent).toBe("");
  });

  it("ignora torneios sem EV medido em vez de tratá-los como zero", () => {
    const comNulo = {
      has_data: true,
      ev_per_100_recent: 4.2, ev_per_100_prev: 8.1,
      series: [
        { tournament_id: 1, name: "a", ev_per_100: 5 },
        { tournament_id: 2, name: "b", ev_per_100: null },
        { tournament_id: 3, name: "c", ev_per_100: 7 },
      ],
    } as EvSummary;
    const { container } = render(<V2EvTrendCard evSummary={comNulo} />);
    // a referencia de media usa 6 (media dos dois MEDIDOS), nao 4 (que seria (5+0+7)/3)
    expect(container.innerHTML).toContain("6");
  });
});

describe("V2EvTrendCard — a copy diz a direção certa", () => {
  // O teste acima prova qual CHAVE o componente escolhe; este prova o que a chave DIZ. Separado
  // porque o i18n nao roda em teste unitario (t() devolve a chave), e porque um texto invertido
  // na traducao elogiaria quem esta piorando sem nenhum teste de logica falhar.
  it("melhorando fala de menos perda; piorando fala de mais perda (3 locales)", async () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = (await import(`@/i18n/locales/${loc}/dashboard.json`)).default as
        { v2: Record<string, string> };
      const v2 = d.v2;
      expect(v2.trendBetter, loc).toBeTruthy();
      expect(v2.trendWorse, loc).toBeTruthy();
      expect(v2.trendNoSample, loc).toBeTruthy();
      expect(v2.trendStable, loc).toBeTruthy();
      // as duas frases de direcao tem que ser DIFERENTES entre si
      expect(v2.trendBetter, loc).not.toBe(v2.trendWorse);
      // e ambas tem que citar os dois numeros comparados
      for (const k of ["trendBetter", "trendWorse"]) {
        expect(v2[k], `${loc}.${k}`).toContain("{{rec}}");
        expect(v2[k], `${loc}.${k}`).toContain("{{ant}}");
      }
      // regra do projeto: sem travessao na copy visivel
      for (const k of Object.keys(v2).filter((x) => x.startsWith("trend"))) {
        expect(v2[k], `${loc}.${k}`).not.toContain("—");
      }
    }
  });
});
