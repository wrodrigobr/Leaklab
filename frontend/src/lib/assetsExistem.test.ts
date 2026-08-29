import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Todo import estático de `@/assets/...` aponta para um arquivo que EXISTE.
 *
 * ── O que originou (30/08) ────────────────────────────────────────────────────────────────
 *
 * A página da mão compartilhada importou `grindlab-logo-horizontal.svg` — o arquivo real é
 * `grindlab_final_horizontal.svg`. O `tsc` passou verde (o ambiente declara `*.svg` como
 * módulo, qualquer caminho casa) e quem morreu foi o `vite build`... do Cloudflare Pages.
 * O deploy do frontend ficou 40 minutos "no ar" servindo o bundle ANTIGO, sem erro em lugar
 * nenhum visível daqui. O bundle publicado é que denunciou (a lição do artefato publicado).
 *
 * O tsc não cobre isto por construção; a suíte agora cobre.
 */

const SRC = path.join(__dirname, "..");

function arquivos(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return arquivos(p);
    return /\.tsx?$/.test(e.name) && !/\.test\./.test(e.name) ? [p] : [];
  });
}

describe("imports de assets", () => {
  const fontes = arquivos(SRC);
  const refs: { onde: string; alvo: string }[] = [];
  for (const f of fontes) {
    const texto = fs.readFileSync(f, "utf-8");
    for (const m of texto.matchAll(/from\s+["']@\/(assets\/[^"']+)["']/g)) {
      refs.push({ onde: path.relative(SRC, f), alvo: m[1] });
    }
  }

  it("a varredura enxerga imports (senão aprova o vazio)", () => {
    expect(refs.length, "nenhum import de @/assets achado — o varredor está cego").toBeGreaterThan(3);
  });

  it("todo asset importado existe no disco", () => {
    // sufixo de query do Vite (?raw, ?url) nao faz parte do caminho no disco
    const mortos = refs.filter((r) => !fs.existsSync(path.join(SRC, r.alvo.split("?")[0])))
      .map((r) => `${r.onde} -> ${r.alvo}`);
    expect(mortos, "import de asset inexistente: o tsc passa e o vite build de DEPLOY morre")
      .toEqual([]);
  });
});
