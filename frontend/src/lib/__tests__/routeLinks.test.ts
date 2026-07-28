import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Link interno tem que apontar para uma rota que existe.
 *
 * O caso que originou (produção, 2026-07-28): o botão "ver mão" do relatório de evolução apontava
 * para `/replay?t=...`, mas a rota é `/replayer`. Deu 404 para o usuário.
 *
 * **Nada pega isso hoje**: para o TypeScript e para o bundler é uma string comum. Só o clique
 * revela — e o clique acontece em produção.
 *
 * A checagem é pelo PRIMEIRO segmento, não pelo caminho inteiro: rotas com parâmetro
 * (`/coach-replay/:id`) são montadas por template no código, e comparar o caminho completo daria
 * falso positivo em todas.
 */

const RAIZ = join(__dirname, "..", "..");

function fontes(dir: string): string[] {
  const out: string[] = [];
  for (const nome of readdirSync(dir)) {
    if (nome === "node_modules" || nome === "__tests__") continue;
    const p = join(dir, nome);
    if (statSync(p).isDirectory()) out.push(...fontes(p));
    else if (/\.tsx?$/.test(nome)) out.push(p);
  }
  return out;
}

function primeiroSegmento(caminho: string): string {
  return caminho.replace(/^\//, "").split(/[/?#]/)[0];
}

describe("links internos apontam para rotas existentes", () => {
  it("todo destino tem rota declarada em App.tsx", () => {
    const app = readFileSync(join(RAIZ, "App.tsx"), "utf-8");
    const rotas = new Set(
      [...app.matchAll(/path="([^"]+)"/g)]
        .map((m) => primeiroSegmento(m[1]))
        .filter((s) => s && s !== "*"),
    );
    expect(rotas.size, "nenhuma rota lida de App.tsx — o teste ficaria inócuo").toBeGreaterThan(5);

    const ofensores: string[] = [];
    for (const arquivo of fontes(RAIZ)) {
      if (arquivo.endsWith("App.tsx")) continue;
      const src = readFileSync(arquivo, "utf-8");
      // to="/x" | to={`/x...`} | navigate("/x") | navigate(`/x...`)
      const alvos = [
        ...src.matchAll(/\bto=\{?["'`](\/[^"'`{}\s]*)/g),
        ...src.matchAll(/\bnavigate\(\s*["'`](\/[^"'`{}\s]*)/g),
      ];
      for (const m of alvos) {
        const seg = primeiroSegmento(m[1]);
        if (!seg) continue;                       // "/" é a raiz, sempre existe
        if (!rotas.has(seg)) {
          ofensores.push(`${arquivo.replace(RAIZ, "src")}: "${m[1]}" → rota "/${seg}" não existe`);
        }
      }
    }
    expect(
      ofensores,
      `link para rota inexistente (404 na cara do usuário):\n  ${ofensores.join("\n  ")}`,
    ).toEqual([]);
  });
});
