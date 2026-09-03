import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Todo flag direcional (nit/loose/teimoso/...) que o backend pode mandar tem tradução nos
 * 3 idiomas.
 *
 * ── O que originou (03/09) ──────────────────────────────────────────────────────────────────
 *
 * `opponent_stats.STAT_REFERENCES` guarda os flags como STRING LITERAL, e boa parte deles
 * (teimoso, passivo, folda demais, paga demais, só value, largo) era texto em português puro
 * — o front (`PlayerStatsCard.tsx`) renderizava `flag.flag` CRU, sem nenhum `t()`. O dono
 * trocou o idioma pra inglês e "teimoso" continuava na tela. Os flags viraram chaves
 * (stubborn/passive/...) e passam por `t(\`playerStats.flags.${flag.flag}\`)` — este guarda
 * lê o backend de verdade e exige que TODA chave usada lá exista nos 3 `dashboard.json`.
 */

const BACKEND = path.join(__dirname, "../../../../backend/leaklab/opponent_stats.py");
const LOCALES = ["pt-BR", "en", "es"] as const;

describe("flags do HUD de oponente traduzidos nos 3 idiomas", () => {
  const py = fs.readFileSync(BACKEND, "utf-8");

  // STAT_REFERENCES: par (cutoff, 'flag') dentro de 'below'/'above' — dois grupos por linha.
  const doTabela = [...py.matchAll(/'(?:below|above)':\s*\([^,]+,\s*'([a-z-]+)'\)/g)]
    .map((m) => m[1]);
  // O flag solto do gap VPIP-PFR (fora da tabela, mesmo arquivo).
  const doGap = [...py.matchAll(/'flag':\s*\('([a-z-]+)'/g)].map((m) => m[1]);

  const flags = [...new Set([...doTabela, ...doGap])];

  it("a varredura enxerga o backend (senão aprova o vazio)", () => {
    expect(flags.length, "nenhum flag lido de opponent_stats.py").toBeGreaterThan(10);
  });

  it.each(LOCALES)("todo flag do backend existe em playerStats.flags — %s", (locale) => {
    const p = path.join(__dirname, `../../i18n/locales/${locale}/dashboard.json`);
    const dict = JSON.parse(fs.readFileSync(p, "utf-8"));
    const mapa = dict.playerStats?.flags ?? {};
    for (const flag of flags) {
      expect(mapa[flag], `flag "${flag}" sem tradução em ${locale}`).toBeTruthy();
    }
  });

  it("nenhum flag do backend é texto em português cru (a causa do bug original)", () => {
    // Heurística simples: acento ou espaço = não é uma chave/slug neutro.
    const suspeitos = flags.filter((f) => /[à-ú ]/i.test(f));
    expect(suspeitos, `flags que parecem texto solto, não chave: ${suspeitos}`).toEqual([]);
  });
});
