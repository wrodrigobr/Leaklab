import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Ícone do lucide-react não pode sombrear um global — o erro só aparece em RUNTIME.
 *
 * O caso que originou (2026-07-28, tela branca em produção):
 *
 *     import { Map } from "lucide-react";      // ícone
 *     const grade = new Map(...);              // TypeError: Map is not a constructor
 *
 * O `Map` importado passa a ser o componente React, e o construtor global some do escopo do
 * módulo. **Nem o `tsc --noEmit` nem o `vite build` pegam**: o nome é válido nos dois mundos, e a
 * chamada só falha quando a linha executa. Chegou ao usuário como página em branco com
 * "o2 is not a constructor" no console minificado.
 *
 * O teste bloqueia o import cru desses nomes, mesmo sem uso do global no arquivo: hoje é risco
 * latente, e a próxima linha que alguém escrever no arquivo é que vira o bug. `Map as MapIcon`
 * custa nada e fecha a porta.
 */

// Nomes que o lucide-react exporta E que existem como global no browser.
const PERIGOSOS = [
  "Map", "Set", "Image", "Text", "Menu", "Link", "Option",
  "History", "Navigation", "Radio", "Table",
];

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

describe("ícones do lucide-react não sombreiam globais", () => {
  it("todo import perigoso usa alias", () => {
    const ofensores: string[] = [];
    for (const arquivo of fontes(RAIZ)) {
      const src = readFileSync(arquivo, "utf-8");
      const imports = src.matchAll(/import\s*\{([^}]+)\}\s*from\s*["']lucide-react["']/g);
      for (const m of imports) {
        const crus = m[1]
          .split(",")
          .map((x) => x.trim())
          .filter((x) => x && !x.includes(" as "));
        for (const nome of crus) {
          if (PERIGOSOS.includes(nome)) {
            ofensores.push(`${arquivo.replace(RAIZ, "src")}: \`${nome}\``);
          }
        }
      }
    }
    expect(
      ofensores,
      `import de ícone sombreando global (use \`X as XIcon\`):\n  ${ofensores.join("\n  ")}`,
    ).toEqual([]);
  });
});
