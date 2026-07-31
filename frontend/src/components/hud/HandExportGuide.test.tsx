import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";

/**
 * Guia "Como exportar suas mãos": o caminho tem que estar certo e o RESUMO tem que ser pedido.
 *
 * ── Dois problemas reais ──────────────────────────────────────────────────────────────────────
 *
 * 1. **O caminho do PokerStars estava desatualizado.** O guia dizia
 *    `C:\Program Files\PokerStars\HandHistory\`. Verificado no disco de uma máquina real em
 *    2026-07-31: a pasta é `C:\Users\<usuário>\AppData\Local\PokerStars\HandHistory\<nick>`.
 *    Caminho errado no guia de ativação é pior que caminho ausente: manda a pessoa procurar onde
 *    não tem, e ela conclui que o produto não funciona antes de usar.
 *
 * 2. **O guia só pedia as MÃOS.** O resumo do torneio é um arquivo separado, e é dele que saem
 *    colocação, prêmio, ROI e field size. Desde 2026-07-30 ele também é o que permite detectar
 *    MESA FINAL, que é onde o ICM muda a decisão certa. Só a instrução da ACR mencionava isso.
 */
const LOCALES = ["pt-BR", "en", "es"] as const;
const SITES = ["pokerstars", "ggpoker", "acr", "coinpoker"] as const;

function guia(loc: string) {
  const j = JSON.parse(readFileSync(`src/i18n/locales/${loc}/onboarding.json`, "utf-8"));
  return j.exportGuide as {
    sites: Record<string, { name: string; where: string; summary: string }>;
    summaryTitle: string; summaryWhy: string;
  };
}

describe("guia de exportação — o caminho do PokerStars", () => {
  it("aponta para AppData, e não mais para Program Files", () => {
    for (const loc of LOCALES) {
      const w = guia(loc).sites.pokerstars.where;
      expect(w, `${loc}: caminho antigo de volta`).not.toContain("Program Files");
      expect(w, loc).toContain("AppData");
      expect(w, loc).toContain("HandHistory");
    }
  });
});

describe("o modal de boas-vindas também pede os dois arquivos", () => {
  it("o passo de upload cita o resumo, e não só as mãos", () => {
    // Mesmo gap, em segundo lugar: o guia por sala passou a pedir o resumo, mas o modal que o
    // usuário vê PRIMEIRO continuava falando de um arquivo só. Quem segue o modal e não abre o
    // guia sobe metade do necessário e perde colocação, prêmio, ROI e mesa final.
    for (const loc of LOCALES) {
      const j = JSON.parse(readFileSync(`src/i18n/locales/${loc}/onboarding.json`, "utf-8"));
      const d = (j.steps.upload.desc as string).toLowerCase();
      expect(d, `${loc}: modal nao cita o resumo`).toMatch(/resumo|summary|resumen/);
    }
  });
});

describe("guia de exportação — o resumo do torneio", () => {
  it("todo site pede o resumo, não só a ACR", () => {
    for (const loc of LOCALES) {
      const g = guia(loc);
      for (const s of SITES) {
        expect(g.sites[s]?.summary, `${loc}.${s}.summary`).toBeTruthy();
        expect(g.sites[s].summary.length, `${loc}.${s}`).toBeGreaterThan(30);
      }
      expect(g.summaryTitle, loc).toBeTruthy();
      expect(g.summaryWhy, loc).toBeTruthy();
    }
  });

  it("explica POR QUE o resumo importa, citando mesa final", () => {
    // Sem o porquê, "mande outro arquivo" é só mais trabalho e a pessoa pula.
    const pt = guia("pt-BR").summaryWhy.toLowerCase();
    expect(pt).toContain("mesa final");
    expect(pt).toContain("roi");
  });

  it("os caminhos verificados aparecem no texto do resumo", () => {
    // Lidos do disco: PokerStars TournSummary e ACR TournamentSummary.
    expect(guia("pt-BR").sites.pokerstars.summary).toContain("TournSummary");
    expect(guia("pt-BR").sites.acr.summary).toContain("TournamentSummary");
  });

  it("a tela renderiza a linha do resumo para cada site", () => {
    const src = readFileSync("src/components/hud/HandExportGuide.tsx", "utf-8");
    expect(src).toContain("exportGuide.summaryTitle");
    expect(src).toMatch(/exportGuide\.sites\.\$\{s\}\.summary/);
  });
});
