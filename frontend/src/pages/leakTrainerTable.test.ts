/**
 * A mesa não pode desenhar aposta que não existe.
 *
 * Reportado com print: o jogador via fichas de 1,7bb do vilão no pote e um menu de "check ou bet",
 * e concluiu que o menu estava errado. Era o MENU que estava certo — a mesa é que inventava a
 * aposta.
 *
 * A causa é um `||` com zero: `sp.facing_size_bb || 1.65`. Quando ninguém apostou, `facing_size_bb`
 * é `0`, o JavaScript trata zero como falso, e o fallback de 1,65bb entrava. Ficou invisível
 * enquanto o catálogo estático de treino tinha SEMPRE 1,65 — o acervo de nós solvados trouxe spots
 * sem aposta na mesa e o defeito apareceu.
 *
 * O teste é de texto porque jsdom não desenha a mesa: o que dá para travar é o operador, e o
 * operador é a causa.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const fonte = readFileSync(join(__dirname, "LeakTrainer.tsx"), "utf-8");
const semComentarios = fonte.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");

describe("mesa do treino postflop", () => {
  it("não usa || em campo numérico que pode ser zero legítimo", () => {
    // 0 bb enfrentados é um valor VÁLIDO (ninguém apostou), não ausência de valor.
    expect(semComentarios).not.toMatch(/facing_size_bb\s*\|\|/);
  });

  it("só desenha a aposta do vilão quando existe aposta", () => {
    expect(semComentarios).toMatch(/facing\s*>\s*0/);
  });

  it("a profundidade é formatada antes de ir para a tela", () => {
    // O acervo guarda o stack efetivo cru (38.2975); sem formatar, ele chega assim ao jogador.
    expect(semComentarios).not.toMatch(/\{spot\.stack_bb\}bb/);
    expect(semComentarios).toMatch(/fmtBb\(spot\.stack_bb\)/);
  });
});
