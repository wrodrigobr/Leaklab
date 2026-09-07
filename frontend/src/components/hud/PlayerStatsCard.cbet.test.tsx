// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { PlayerStatsCard } from "./PlayerStatsCard";

/**
 * C-Bet IP / OOP no hover do C-Bet (AY-19, sugestao do Rullian). Sem coluna nova: as duas
 * taxas e a amostra vao no tooltip do C-Bet, e so dele.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);

const STATS = {
  total_hands: 6029, vpip: 25.3, pfr: 17.8, af: 3.2, cbet_pct: 77.4, fold_to_flop_bet: 40, bb_defense: 38,
  steal_pct: 44, open_limp_pct: 3.7, fold_to_3bet: 56.9, wtsd: 38, three_bet: 8, w_at_sd: 54,
  cbet_ip: 91.2, cbet_oop: 73.4, cbet_ip_opp: 215, cbet_oop_opp: 94, flags: {},
};

describe("C-Bet IP / OOP", () => {
  it("o tooltip do C-Bet traz IP e OOP com a amostra; o do VPIP nao", async () => {
    render(<PlayerStatsCard stats={STATS as never} v2 />);
    // so um tooltip aberto por vez: foca SO o botao de info do tile do C-Bet
    const botaoCbet = screen.getByText("C-Bet").parentElement!.querySelector("button")!;
    fireEvent.pointerMove(botaoCbet); fireEvent.focus(botaoCbet);
    expect((await screen.findAllByText(/playerStats\.cbetSplit:91\.2%,215,73\.4%,94/)).length).toBeGreaterThan(0);
    cleanup();
    render(<PlayerStatsCard stats={STATS as never} v2 />);
    const botaoVpip = screen.getByText("VPIP").parentElement!.querySelector("button")!;
    fireEvent.pointerMove(botaoVpip); fireEvent.focus(botaoVpip);
    await screen.findAllByText(/playerStats\.tooltip\.vpip/);
    expect(screen.queryByText(/cbetSplit/)).toBeNull();
  });

  it("sem potes heads-up, o tooltip diz que IP/OOP aparecem depois", async () => {
    render(<PlayerStatsCard stats={{ ...STATS, cbet_ip: null, cbet_oop: null, cbet_ip_opp: 0, cbet_oop_opp: 0 } as never} v2 />);
    const botaoCbet = screen.getByText("C-Bet").parentElement!.querySelector("button")!;
    fireEvent.pointerMove(botaoCbet); fireEvent.focus(botaoCbet);
    expect((await screen.findAllByText(/playerStats\.cbetSplitNone/)).length).toBeGreaterThan(0);
  });
});
