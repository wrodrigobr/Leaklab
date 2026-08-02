/**
 * O resumo da lição não pode apresentar UMA categoria como o resultado das dez respostas.
 *
 * Reportado com print: 10 feitos, 100% de acerto, e "DOMÍNIO DA CATEGORIA 0% → 5%, BRONZE". O
 * jogador leu, corretamente, que acertar tudo não moveu nada.
 *
 * Não era só a tela. A lição de 10 spots se espalha por ~10 categorias diferentes — a prática é
 * INTERCALADA de propósito, é o que o protocolo de progressão manda fazer — e cada categoria
 * recebe UMA tentativa. O domínio de uma tentativa é exatamente 5%. A tela pegava a categoria do
 * último spot e a anunciava como o desfecho da lição inteira.
 *
 * Medido em produção: 54 categorias para 205 tentativas, 3,8 por categoria.
 *
 * O conserto NÃO foi mudar a unidade de medida. Tentei agregar por família (`cenário:posição:vs`,
 * sem a profundidade) e a medição derrubou a hipótese: colapsava 54 chaves em 49 famílias, porque
 * o que fragmenta a prática são os PARES DE POSIÇÃO, não o stack — e onde houve fusão ela diluiu,
 * trocando 4 ouros por pratas. Ficou o conserto honesto: a barra de domínio só aparece quando a
 * lição REALMENTE se concentrou; quando espalhou, a tela diz que espalhou.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const fonte = readFileSync(join(__dirname, "LeakTrainer.tsx"), "utf-8");
const semComentarios = fonte.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");

describe("resumo da lição", () => {
  it("a barra de domínio depende da lição ter se concentrado", () => {
    expect(semComentarios).toMatch(/licaoConcentrada/);
    // o gate tem que estar NA atribuição do que a barra lê, não só num texto ao lado
    expect(semComentarios).toMatch(/primaryMastery\s*=\s*\(licaoConcentrada/);
  });

  it("a concentração é medida contra o total da lição, não contra um limiar solto", () => {
    expect(semComentarios).toMatch(/respostasNaPrincipal\s*\/\s*totalDone/);
  });

  it("quando espalha, a tela diz quantas situações foram treinadas", () => {
    expect(semComentarios).toMatch(/summary\.spread/);
  });
});
