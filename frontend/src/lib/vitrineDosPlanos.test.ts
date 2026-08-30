import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A vitrine dos planos diz o que o PLAN_LIMITS cobra.
 *
 * ── O que originou (30/08, véspera de lançamento) ─────────────────────────────────────────
 *
 * O card Free anunciava "treino sem limite diário" — verdade por UM dia (quando o teto foi
 * desligado por engano) e mentira desde que a paridade de 20/dia voltou. Vitrine e limite
 * moram em repositórios de linguagem diferentes e divergem calados.
 *
 * O guarda lê os números DO BACKEND (PLAN_LIMITS) e exige que a copy dos 3 idiomas os
 * carregue: torneios/mês, explicações de IA, solves e o teto diário de treino — e bane a
 * promessa de "sem limite" enquanto o teto existir.
 */

// PLAN_LIMITS mora no repositories (o app.py so importa — o guarda apontou errado na 1a versao)
const BACKEND = path.join(__dirname, "../../../backend/database/repositories.py");
const LOCALES = ["pt-BR", "en", "es"] as const;

function limitesFree(): { tournaments: string; ai: string; solves: string; spots: string } {
  const s = fs.readFileSync(BACKEND, "utf-8");
  const m = s.match(/'free':\s*\{([^}]*)\}/s);
  if (!m) throw new Error("PLAN_LIMITS free não encontrado");
  // \\s no TEMPLATE (o literal resolve \s para "s" e a regex virava lixo silencioso)
  const pega = (k: string) => (m[1].match(new RegExp(`'${k}':\\s*(\\d+|None)`)) ?? [])[1];
  return {
    tournaments: pega("tournaments")!, ai: pega("ai_calls")!,
    solves: pega("solves")!, spots: pega("training_spots_per_day")!,
  };
}

describe("vitrine dos planos vs PLAN_LIMITS", () => {
  const lim = limitesFree();

  it("a leitura do backend enxerga os números", () => {
    for (const [k, v] of Object.entries(lim)) {
      expect(v, `limite ${k} não lido do backend`).toBeTruthy();
    }
  });

  it.each(LOCALES)("o card Free carrega os números reais — %s", (locale) => {
    const c = JSON.parse(fs.readFileSync(
      path.join(__dirname, "../i18n/locales", locale, "landing.json"), "utf-8"));
    const plans = c.plans ?? {};
    const linhas = Object.entries(plans)
      .filter(([k]) => k.startsWith("freeF")).map(([, v]) => String(v)).join(" | ");
    for (const [nome, valor] of Object.entries(lim)) {
      if (valor === "None") continue;
      expect(linhas, `o número de ${nome} (${valor}) sumiu da vitrine em ${locale}`)
        .toContain(valor);
    }
    if (lim.spots !== "None") {
      expect(/sem limite|no daily cap|no limit|sin tope|sin límite/i.test(linhas),
        `a vitrine promete "sem limite" com teto de ${lim.spots}/dia no backend`).toBe(false);
    }
  });
});
