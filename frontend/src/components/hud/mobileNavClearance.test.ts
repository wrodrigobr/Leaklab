import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * A barra de navegação do mobile é `fixed bottom-0` e some só no `lg`. Todo container de página
 * precisa reservar espaço embaixo até ESSE mesmo breakpoint.
 *
 * Os cinco containers escreviam `pb-28 md:pb-8`: o recuo caía para 32px a partir de 768px, mas a
 * barra (57px de altura, mais o safe-area do aparelho) continua na tela até 1023px. Na faixa entre
 * os dois, o fim da página fica atrás da barra.
 *
 * Medido no app rodando, a 820x700 e com a página rolada até o fim: o link "Ver exemplo de
 * análise" ocupava y=646..662 e a barra começava em y=643 — o link inteiro coberto. Ele é a saída
 * de quem ainda não subiu arquivo nenhum, e estava escondido justamente dela.
 *
 * O par de classes vivia copiado em CINCO arquivos, então o guarda varre a árvore em vez de
 * conferir os cinco: o sexto container nasce coberto.
 */
const RAIZ = "src";

function arquivos(dir: string, out: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const p = join(dir, nome);
    if (statSync(p).isDirectory()) arquivos(p, out);
    else if (/\.tsx?$/.test(nome) && !/\.test\.tsx?$/.test(nome)) out.push(p);
  }
  return out;
}

/** Toda string literal (aspas ou template) que contenha a classe procurada. */
function classesCom(src: string, classe: string): string[] {
  const achados: string[] = [];
  for (const re of [/"([^"\n]*)"/g, /'([^'\n]*)'/g, /`([^`]*)`/g]) {
    for (const m of src.matchAll(re)) {
      if (m[1].includes(classe)) achados.push(m[1]);
    }
  }
  return achados;
}

describe("espaço para a barra de navegação do mobile", () => {
  it("nenhum container reduz o recuo de baixo antes do lg", () => {
    const ofensores: string[] = [];
    let containers = 0;

    for (const f of arquivos(RAIZ)) {
      const src = readFileSync(f, "utf-8");
      if (!src.includes("pb-28")) continue;
      for (const cls of classesCom(src, "pb-28")) {
        containers++;
        // `md:pb-*` volta a esconder o fim da página entre 768px e 1023px, onde a barra ainda
        // está na tela. O override tem que ser `lg:`, igual ao `lg:hidden` da barra.
        if (/\bmd:pb-/.test(cls)) ofensores.push(`${f}: ${cls}`);
      }
    }

    // Sem esta linha, um seletor quebrado devolveria "zero ofensores" e passaria dizendo o
    // contrário do que mediu. Zero tranquilizador é o pior resultado de uma ferramenta de medição.
    expect(containers, "a varredura nao achou container nenhum — o seletor quebrou")
      .toBeGreaterThanOrEqual(5);
    expect(ofensores, "container escondido atras da barra entre 768px e 1023px").toEqual([]);
  });

  it("a barra continua sendo lg:hidden, que é o que amarra a regra acima", () => {
    // Se a barra passar a sumir noutro breakpoint, o recuo dos containers tem que acompanhar.
    // O teste falha aqui para obrigar a revisita, em vez de deixar os dois valores divergirem.
    const header = readFileSync("src/components/hud/HudHeader.tsx", "utf-8");
    const nav = header.split("\n").find((l) => l.includes("fixed bottom-0") && l.includes("z-50"));
    expect(nav, "nao achei a barra fixa no HudHeader").toBeTruthy();
    expect(nav!, "a barra mudou de breakpoint — revise o pb dos containers").toContain("lg:hidden");
  });
});
