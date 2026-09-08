// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import i18n from "@/i18n";
import { PlayerStatsCard } from "./PlayerStatsCard";

/**
 * Com o i18n DE VERDADE (sem mock): o tooltip do HUD le a definicao e a formula do namespace
 * `docs` (a mesma fonte da pagina /docs). O teste com mock prova a chave; este prova que a
 * chave RESOLVE nos 3 idiomas, porque `docs:` e outro namespace e um prefixo errado cai em
 * silencio no texto cru da chave.
 */
afterEach(cleanup);
// tooltips do Radix e duas grades de 169 celulas passam de 5s com a suite inteira em paralelo
vi.setConfig({ testTimeout: 30000 });

const STATS = {
  total_hands: 6029, vpip: 25.3, pfr: 17.8, af: 3.2, cbet_pct: 77.4, fold_to_flop_bet: 40, bb_defense: 38,
  steal_pct: 44, open_limp_pct: 3.7, fold_to_3bet: 56.9, wtsd: 38, three_bet: 8, w_at_sd: 54,
  cbet_ip: 91.2, cbet_oop: 73.4, cbet_ip_opp: 215, cbet_oop_opp: 94, flags: {},
};

const ESPERADO: Record<string, [string, string]> = {
  "pt-BR": ["mãos com call/raise preflop ÷ mãos jogadas", "Fórmula"],
  en: ["preflop", "Formula"],
  es: ["preflop", "Fórmula"],
};

describe("tooltip do HUD com o i18n real", () => {
  for (const [lng, [formula, rotulo]] of Object.entries(ESPERADO)) {
    it(`${lng}: VPIP mostra a formula do docs:hud_defs e o rotulo das linhas`, async () => {
      await i18n.changeLanguage(lng);
      render(<PlayerStatsCard stats={STATS as never} v2 />);
      const botao = screen.getByText("VPIP").parentElement!.querySelector("button")!;
      fireEvent.pointerMove(botao); fireEvent.focus(botao);
      const tip = (await screen.findAllByTestId("tooltip-vpip"))[0];
      expect(tip.textContent).toContain(formula);
      expect(tip.textContent).toContain(rotulo);
      expect(tip.textContent).not.toMatch(/hud_defs|playerStats\./);   // nenhuma chave crua
    });
  }
});
