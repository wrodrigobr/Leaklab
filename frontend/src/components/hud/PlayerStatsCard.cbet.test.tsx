// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { PlayerStatsCard } from "./PlayerStatsCard";

/**
 * Tooltip estruturado em TODOS os stats do HUD (dono, 07/09: "o mesmo padrao do C-Bet"):
 * definicao e formula lidas de `docs:hud_defs` (a mesma fonte da pagina /docs), "Voce" com o
 * numero, "Ref MTT" com a referencia. O C-Bet e o unico que acrescenta IP / OOP com a amostra
 * (AY-19, sugestao do Rullian), e SEM referencia: os 60-75 / 45-60 nao tinham fonte.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);
vi.setConfig({ testTimeout: 30000 });

const STATS = {
  total_hands: 6029, vpip: 25.3, pfr: 17.8, af: 3.2, cbet_pct: 77.4, fold_to_flop_bet: 40, bb_defense: 38,
  steal_pct: 44, open_limp_pct: 3.7, fold_to_3bet: 56.9, wtsd: 38, three_bet: 8, w_at_sd: 54,
  cbet_ip: 91.2, cbet_oop: 73.4, cbet_ip_opp: 215, cbet_oop_opp: 94,
  // a referencia do solver nos proprios spots (AY-23): IP fora (91,2 > 88,5), OOP dentro
  cbet_ip_ref: { lo: 48.9, hi: 88.5, folga: 3, pesos: { "20-40 vs BB": 100 }, cobertura: 86 },
  cbet_oop_ref: { lo: 60.0, hi: 80.0, folga: 3, pesos: { "20-40 vs BB": 100 }, cobertura: 100 },
  cbet_ip_cobertura: 86, cbet_oop_cobertura: 100,
  // RFI no HUD (07/09): referencia do solver = media nos assentos e stacks do jogador
  rfi: 26.9, rfi_ref: { lo: 26.0, hi: 30.0, folga: 2, pesos: {}, cobertura: 100, tipo: "media", n: 12460 },
  flags: { vpip: { band: "above", flag: "loose", healthy: [18, 24] } },
};

async function abre(rotulo: string, testid: string) {
  const botao = screen.getByText(rotulo).parentElement!.querySelector("button")!;
  fireEvent.pointerMove(botao); fireEvent.focus(botao);
  return (await screen.findAllByTestId(testid))[0];   // o Radix duplica o conteudo para leitor de tela
}

describe("tooltip estruturado do HUD", () => {
  it("VPIP: definicao e formula de docs:hud_defs, Voce com o numero, Ref MTT com a faixa do backend", async () => {
    render(<PlayerStatsCard stats={STATS as never} v2 />);
    const tip = await abre("VPIP", "tooltip-vpip");
    const txt = tip.textContent!;
    expect(txt).toContain("docs:hud_defs.vpip.def");
    expect(txt).toContain("docs:hud_defs.vpip.formula");
    expect(txt).toContain("playerStats.tip.formula");
    expect(txt).toContain("playerStats.tip.you");
    expect(txt).toContain("25.3%");
    expect(txt).toContain("playerStats.tip.ref");
    expect(txt).toContain("18–24%");                    // a faixa corrigida do backend, nao a inline
    expect(txt).not.toContain("playerStats.cbetSplitIp");
  });

  it("cada stat le a SUA definicao (a chave do hud_defs, nao a do card)", async () => {
    const pares: [string, string, string][] = [
      ["RFI", "tooltip-rfi", "rfi"], ["Fold vs Bet", "tooltip-fold_to_flop_bet", "fold_to_flop_bet"],
      ["Fold to 3BET", "tooltip-fold_to_3bet", "fold_to_3bet"], ["W$SD", "tooltip-w_at_sd", "w_at_sd"],
    ];
    for (const [rotulo, testid, chave] of pares) {
      render(<PlayerStatsCard stats={STATS as never} v2 />);
      const tip = await abre(rotulo, testid);
      expect(tip.textContent).toContain(`docs:hud_defs.${chave}.def`);
      expect(tip.textContent).toContain(`docs:hud_defs.${chave}.formula`);
      cleanup();
    }
  });

  it("o AF saiu do HUD e o RFI entrou, com a referencia do solver nos assentos do jogador", async () => {
    render(<PlayerStatsCard stats={STATS as never} v2 />);
    expect(screen.queryByText("AF")).toBeNull();
    expect(screen.getAllByText(/Fold to 3BET|Steal|Open Limp|BB Defense|C-Bet|Fold vs Bet|WTSD|W\$SD|VPIP|PFR|RFI|3BET/)).toHaveLength(12);
    const tip = await abre("RFI", "tooltip-rfi");
    expect(tip.textContent).toContain("playerStats.tip.solverSeats");
    expect(tip.textContent).toContain("26–30%");
    expect(tip.textContent).toContain("playerStats.tip.solverSeatsNote:12460,100");   // n e cobertura
    expect(tip.textContent).not.toContain("playerStats.tip.ref");                       // nao e a faixa fixa
    // o rodape da celula diz Solver, e o numero esta dentro (26,9 em 26-30): cor ok (primary)
    expect(screen.getAllByText("playerStats.refSolver:26–30%").length).toBeGreaterThan(0);
  });

  it("RFI sem referencia do solver (cobertura baixa): numero sem veredito e o tooltip diz por que", async () => {
    render(<PlayerStatsCard stats={{ ...STATS, rfi: 40, rfi_ref: null } as never} v2 />);
    const tip = await abre("RFI", "tooltip-rfi");
    expect(tip.textContent).toContain("playerStats.tip.solverSeatsNone");
    expect(screen.queryByText(/playerStats.refSolver/)).toBeNull();
  });

  it("o C-Bet acrescenta IP e OOP com a amostra e a referencia do SOLVER nos proprios spots", async () => {
    render(<PlayerStatsCard stats={STATS as never} v2 />);
    const tip = await abre("C-Bet", "tooltip-cbet_pct");
    const txt = tip.textContent!;
    expect(txt).toContain("docs:hud_defs.cbet.def");
    expect(txt).toContain("playerStats.cbetSplitIp");
    expect(txt).toContain("91.2%");
    expect(txt).toContain("playerStats.cbetSplitOpps:215");
    expect(txt).toContain("playerStats.cbetSplitOop");
    expect(txt).toContain("73.4%");
    expect(txt).toContain("playerStats.cbetSplitOpps:94");
    expect(txt).not.toMatch(/60–75|45–60/);                       // nada inventado
    // a referencia vem do backend, e a cor do numero compara com ela
    const ip = tip.querySelector("[data-testid=cbet-cbetSplitIp]")!;
    expect(ip.textContent).toContain("playerStats.cbetSolver");
    expect(ip.textContent).toContain("48.9–88.5%");
    expect(ip.textContent).toContain("playerStats.cbetSolverCoverage:86");   // cobre 86%: dito
    expect(ip.querySelector("b")!.className).toContain("text-red-400");      // 91,2 > 88,5
    const oop = tip.querySelector("[data-testid=cbet-cbetSplitOop]")!;
    expect(oop.textContent).toContain("60–80%");
    expect(oop.textContent).not.toContain("playerStats.cbetSolverCoverage");  // 100%: nao repete
    expect(oop.querySelector("b")!.className).toContain("text-emerald-400");  // 73,4 dentro
  });

  it("sem referencia (cobertura abaixo do piso), o numero fica sem cor e o tooltip diz a cobertura", async () => {
    render(<PlayerStatsCard stats={{ ...STATS, cbet_oop_ref: null, cbet_oop_cobertura: 41 } as never} v2 />);
    const tip = await abre("C-Bet", "tooltip-cbet_pct");
    const oop = tip.querySelector("[data-testid=cbet-cbetSplitOop]")!;
    expect(oop.textContent).toContain("playerStats.cbetSolverNone:41");
    expect(oop.querySelector("b")!.className).not.toMatch(/emerald|red-400/);
  });

  it("sem potes heads-up, o C-Bet diz que IP/OOP aparecem depois", async () => {
    render(<PlayerStatsCard stats={{ ...STATS, cbet_ip: null, cbet_oop: null, cbet_ip_opp: 0, cbet_oop_opp: 0 } as never} v2 />);
    const tip = await abre("C-Bet", "tooltip-cbet_pct");
    expect(tip.textContent).toContain("playerStats.cbetSplitNone");
  });
});
