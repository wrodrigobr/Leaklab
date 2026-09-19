// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
  }),
}));

import { GtoStrategyPanel } from "./GtoStrategyPanel";

/**
 * As duas frases de EV do painel de estratégia.
 *
 * ── "Frequência não é ordem" ──────────────────────────────────────────────────────────────
 *
 * O jogador lê "70%" e passa a fazer aquilo sempre, o que destrói o equilíbrio que o número
 * descreve. A frase só aparece no spot MISTO, pelo mesmo corte de 10% do selo que já existia:
 * num nó puro ela não teria o que avisar e seria ruído.
 *
 * ── O custo de oportunidade ───────────────────────────────────────────────────────────────
 *
 * Estava CRAVADO em português dentro do componente. Jogador em inglês e espanhol lia aquela
 * linha em português no meio da própria tela traduzida.
 */
const MISTO = [
  { action: "check", frequency: 0.62, ev_bb: 4.0, ev_loss_bb: 0 },
  { action: "bet_75pct", frequency: 0.38, ev_bb: 3.0, ev_loss_bb: 1.0 },
];
const PURO = [
  { action: "check", frequency: 0.97, ev_bb: 4.0, ev_loss_bb: 0 },
  { action: "bet_75pct", frequency: 0.03, ev_bb: 1.0, ev_loss_bb: 3.0 },
];

describe("frequencia nao e ordem", () => {
  afterEach(cleanup);

  it("aparece no spot MISTO", () => {
    render(<GtoStrategyPanel strategy={MISTO as never} playedAction="check" />);
    expect(screen.getByTestId("gto-freq-nao-e-ordem").textContent).toBe("gtoMixed.naoEhOrdem");
  });

  it("NAO aparece no spot puro: ali ela nao teria o que avisar", () => {
    render(<GtoStrategyPanel strategy={PURO as never} playedAction="check" />);
    expect(screen.queryByTestId("gto-freq-nao-e-ordem")).toBeNull();
  });

  it("NAO aparece no card compacto, onde a largura e o recurso escasso", () => {
    render(<GtoStrategyPanel strategy={MISTO as never} playedAction="check" compact />);
    expect(screen.queryByTestId("gto-freq-nao-e-ordem")).toBeNull();
  });
});

describe("o custo de oportunidade saiu do codigo", () => {
  afterEach(cleanup);

  it("usa a chave de i18n com o valor, e nao texto cravado", () => {
    const { container } = render(
      <GtoStrategyPanel strategy={MISTO as never} playedAction="bet_75pct" />);
    const txt = container.textContent || "";
    expect(txt).toContain("gtoMixed.custoDeOportunidade:1.00");
    // o texto que estava cravado nao pode voltar
    expect(txt).not.toContain("vs linha ótima");
  });
});
