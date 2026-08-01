import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";

/**
 * A tela de quem ainda não subiu nada não pode restringir nem prometer.
 *
 * O dropzone exibia uma linha de chips ".txt · .log · PokerStars · AES-256". Três defeitos:
 *
 * 1. **Citava UMA sala.** A frase logo acima já lista as quatro. Um jogador de GGPoker que
 *    lesse os chips concluiria que o produto não serve para ele — na tela cujo trabalho é
 *    justamente convencê-lo a subir o arquivo.
 * 2. **"AES-256" era um selo sem lastro.** Não existe uma linha de cifragem no backend
 *    (`grep -i "aes\|encrypt" backend/**.py` = zero). Alegação de segurança que não se
 *    sustenta é passivo, não reforço.
 * 3. Repetia a extensão que a frase acima já dizia.
 *
 * Os guardas abaixo defendem o que sobrou: a frase precisa nomear TODAS as salas suportadas
 * (a lista sai do guia de exportação, não de uma cópia), e a tela não volta a cravar sala
 * solta nem selo de segurança.
 */
const LOCALES = ["pt-BR", "en", "es"] as const;
const TELA = "src/components/hud/EmptyDashboard.tsx";

/** Salas suportadas segundo o GUIA — fonte única. Se nascer uma quinta, este teste cobra a copy. */
function salasSuportadas(): string[] {
  const src = readFileSync("src/components/hud/HandExportGuide.tsx", "utf-8");
  const m = src.match(/const SITES = \[([^\]]+)\]/);
  expect(m, "nao achei a lista de salas no HandExportGuide").toBeTruthy();
  return m![1].split(",").map((s) => s.trim().replace(/["']/g, "")).filter(Boolean);
}

const desc = (loc: string): string =>
  JSON.parse(readFileSync(`src/i18n/locales/${loc}/dashboard.json`, "utf-8")).empty.desc;

describe("dashboard vazio — o que a tela promete", () => {
  it("a chamada do upload nomeia TODAS as salas suportadas, nas 3 locales", () => {
    const salas = salasSuportadas();
    expect(salas.length, "a varredura nao achou sala nenhuma").toBeGreaterThanOrEqual(4);
    for (const loc of LOCALES) {
      const texto = desc(loc).toLowerCase().replace(/[\s/]/g, "");
      for (const sala of salas) {
        expect(texto, `${loc}: a copy nao cita ${sala}`).toContain(sala);
      }
    }
  });

  it("a chamada do upload cita as duas extensões aceitas pelo input", () => {
    // O input aceita .txt E .log. A copy dizia só .txt, e o .log só existia nos chips que
    // saíram — sem esta linha, a extensão teria sumido junto com eles.
    const src = readFileSync(TELA, "utf-8");
    const accept = src.match(/accept="([^"]+)"/);
    expect(accept, "nao achei o accept do input").toBeTruthy();
    const exts = accept![1].split(",").map((e) => e.trim());
    for (const loc of LOCALES) {
      for (const ext of exts) {
        expect(desc(loc), `${loc}: a copy nao cita ${ext}`).toContain(ext);
      }
    }
  });

  it("a tela não crava uma sala nem exibe selo de segurança", () => {
    const src = readFileSync(TELA, "utf-8")
      .replace(/\/\*[\s\S]*?\*\//g, "")   // o comentário que explica a remoção cita os termos
      .replace(/\/\/.*$/gm, "");
    for (const proibido of ["PokerStars", "GGPoker", "CoinPoker", "AES"]) {
      expect(src, `${proibido} de volta na tela — a copy i18n é o lugar disso`)
        .not.toContain(proibido);
    }
  });
});
