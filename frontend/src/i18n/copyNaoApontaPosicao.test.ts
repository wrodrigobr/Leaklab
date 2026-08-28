import { describe, expect, it } from "vitest";

import landingPt from "./locales/pt-BR/landing.json";
import landingEn from "./locales/en/landing.json";
import landingEs from "./locales/es/landing.json";

/**
 * Copy não aponta para onde a coisa está na tela.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * O dono olhou a vitrine e viu: **"a grade abaixo é a de verdade", com a grade renderizada na
 * lateral**. Eu tinha escrito "abaixo" imaginando o empilhamento do mobile.
 *
 * Conferindo o componente, o defeito é maior do que uma palavra errada: `Vitrine.tsx` ALTERNA os
 * lados por bloco (prop `invertido`) e empilha abaixo de `md`. Ou seja "abaixo" está errado no
 * desktop, "do lado" está errado no mobile, e nos blocos invertidos o lado ainda troca. **Não
 * existe palavra de posição que seja verdadeira em todos os tamanhos de tela.**
 *
 * Por isso o guarda proíbe a categoria inteira em vez de corrigir a palavra: qualquer referência
 * posicional vai estar errada em algum lugar, e ninguém percebe porque cada pessoa testa num
 * tamanho só.
 *
 * ── O que ele NÃO cobre ───────────────────────────────────────────────────────────────────
 *
 * Só a landing, que é a tela com layout alternado. Copy de produto pode legitimamente dizer
 * "o botão acima" numa tela de coluna única, e proibir isso em todo lugar criaria falso positivo
 * onde a frase está certa.
 */

/** Palavras que afirmam ONDE algo está. `abaixo`/`acima` também aparecem em "acima da diagonal"
 *  (a legenda da grade), que é posição DENTRO da imagem e não na tela: por isso o padrão exige a
 *  palavra referindo-se ao layout, não a um substantivo da própria ilustração. */
const POSICIONAIS = [
  /\b(logo )?(abaixo|acima)\b(?!\s+da\s+diagonal)/i,
  /\b(à|a)\s+(direita|esquerda)\b/i,
  /\bao\s+lado\b/i,
  /\bd[oa]\s+lado\b/i,
  /\bnesta\s+(coluna|lateral)\b/i,
  /\b(below|above)\b/i,
  /\bon\s+the\s+(right|left)\b/i,
  /\bto\s+the\s+(right|left)\b/i,
  /\b(debajo|arriba)\b/i,
  /\ba\s+la\s+(derecha|izquierda)\b/i,
  /\bal\s+lado\b/i,
];

function frases(no: unknown, caminho: string[] = []): Array<[string, string]> {
  if (typeof no === "string") return [[caminho.join("."), no]];
  if (no && typeof no === "object") {
    return Object.entries(no as Record<string, unknown>).flatMap(([k, v]) =>
      frases(v, [...caminho, k]),
    );
  }
  return [];
}

describe("copy da landing não aponta para posição na tela", () => {
  const locales: Array<[string, unknown]> = [
    ["pt-BR", landingPt],
    ["en", landingEn],
    ["es", landingEs],
  ];

  it.each(locales)("%s", (nome, json) => {
    const violacoes = frases(json)
      .filter(([, texto]) => POSICIONAIS.some((re) => re.test(texto)))
      .map(([chave, texto]) => `${chave}: ${JSON.stringify(texto)}`);
    expect(
      violacoes,
      `${nome}: copy apontando para posição na tela. O layout da vitrine alterna os lados por ` +
        `bloco e empilha no mobile, então a frase está errada em algum tamanho de tela. ` +
        `Descreva a coisa em vez de onde ela está.`,
    ).toEqual([]);
  });

  /** CONTRAPROVA: sem ela um regex quebrado deixaria os três locales passarem verdes para sempre.
   *  Já aconteceu neste projeto: um guarda de copy com regex sobre-escapada passou verde com a
   *  violação plantada de volta. */
  it("o detector ACHA uma violação plantada", () => {
    const plantado = {
      vitrine: { b1: { texto: "E a grade abaixo é a de verdade: abertura do CO com 20bb." } },
    };
    const achadas = frases(plantado).filter(([, t]) => POSICIONAIS.some((re) => re.test(t)));
    expect(achadas).toHaveLength(1);

    // E a legenda REAL da grade, que fala de posição dentro da ilustração, não é violação.
    const legenda = { grade: { nota: "s = suited (acima da diagonal), o = offsuit" } };
    expect(frases(legenda).filter(([, t]) => POSICIONAIS.some((re) => re.test(t)))).toHaveLength(0);
  });
});
