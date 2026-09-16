import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { cardSrc, ordenarMao } from "./PlayingCard";

/**
 * A carta de baralho tem UM caminho e UMA ordem.
 *
 * ── O que originou (16/09) ────────────────────────────────────────────────────────────────────
 *
 * O caminho do SVG era montado em dois lugares (`LessonKit`, `PokerTableV3`) e a lista de mãos
 * do leak ia ser o terceiro. E a ordem das cartas vinha crua do parser: a lista mostrava `4dAd`,
 * com o quatro na frente do ás, e o dono viu na tela.
 */

const SRC = join(import.meta.dirname, "..");

function arquivosDeCodigo(dir: string, acc: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      if (nome === "node_modules" || nome === "__tests__") continue;
      arquivosDeCodigo(caminho, acc);
    } else if (/\.(ts|tsx)$/.test(nome) && !/\.test\.tsx?$/.test(nome)) {
      acc.push(caminho);
    }
  }
  return acc;
}

describe("PlayingCard", () => {
  it("monta o caminho do baralho do produto, com o T virando 10", () => {
    expect(cardSrc("Ah")).toBe("/cards/AH.svg");
    expect(cardSrc("Kd")).toBe("/cards/KD.svg");
    expect(cardSrc("2c")).toBe("/cards/2C.svg");
    // O detalhe que uma cópia esquece: o arquivo do dez é `10`, não `T`.
    expect(cardSrc("Ts")).toBe("/cards/10S.svg");
    expect(cardSrc("td")).toBe("/cards/10D.svg");
  });

  it("os arquivos existem de verdade em public/cards", () => {
    // CONTROLE do caminho: sem isto, um caminho errado passaria no teste de string e a tela
    // mostraria imagem quebrada. É o mesmo princípio de perguntar ao sistema em vez de supor.
    const publico = join(SRC, "..", "public");
    for (const code of ["Ah", "Ts", "2c", "Kd"]) {
      const arq = join(publico, cardSrc(code));
      expect(statSync(arq).isFile(), `${cardSrc(code)} não existe em public/`).toBe(true);
    }
  });

  it("carta alta primeiro, seja par, suited ou offsuit", () => {
    expect(ordenarMao("4dAd")).toEqual(["Ad", "4d"]);   // o caso que o dono viu na tela
    expect(ordenarMao("AdKd")).toEqual(["Ad", "Kd"]);   // já ordenado, não mexe
    expect(ordenarMao("3h3c")).toEqual(["3h", "3c"]);   // par: mantém a ordem recebida
    expect(ordenarMao("2sTh")).toEqual(["Th", "2s"]);   // o T é mais alto que o 2
    expect(ordenarMao("9h6d")).toEqual(["9h", "6d"]);
  });

  it("sem dado não desenha carta nenhuma", () => {
    // A régua da casa: célula sem dado não finge informação.
    for (const ruim of [null, undefined, "", "Ah", "AhKhQh", "  ", "ZZ99"]) {
      expect(ordenarMao(ruim as string | null), `${JSON.stringify(ruim)}`).toBeNull();
    }
  });

  /** Tira comentário de linha e de bloco. Sem isto o guarda acusa quem só FALA do caminho. */
  function semComentario(codigo: string): string {
    return codigo.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|[^:])\/\/.*$/gm, "$1");
  }

  it("nenhum outro arquivo monta o caminho de /cards/ por conta própria", () => {
    // A varredura N+1. Eram dois antes deste componente; o `PokerTableV3` monta o SVG de forma
    // imperativa e por isso usa `cardSrc`, não o componente React.
    //
    // A primeira versão lia o arquivo inteiro e acusou o PokerTableV3 por um COMENTÁRIO que
    // menciona `<image href="/cards/XX.svg">`. É o mesmo erro que cometi horas antes no guarda
    // da paleta de ações: guarda que não separa código de comentário obriga a apagar a
    // explicação para ficar verde, e a explicação é o que impede o defeito de voltar.
    const suspeitos: string[] = [];
    for (const f of arquivosDeCodigo(SRC)) {
      if (f.endsWith(join("components", "PlayingCard.tsx"))) continue;   // a definição mora aqui
      const codigo = semComentario(readFileSync(f, "utf-8"));
      if (/["'`]\/cards\/|\/cards\/\$\{/.test(codigo)) suspeitos.push(f.slice(SRC.length + 1));
    }
    expect(suspeitos, "caminho de /cards/ montado fora de PlayingCard.tsx").toEqual([]);
  });

  it("o guarda ACUSA quem monta o caminho em CÓDIGO, e ignora quem só comenta", () => {
    // CONTROLE dos dois lados, que é o que faltava na primeira versão.
    const comentario = ['// o baralho vem de "/cards/AH.svg" desde sempre',
                        'const x = cardSrc("Ah");'].join("\n");
    const codigo     = 'const src = `/cards/${rank}${suit}.svg`;';
    expect(/["'`]\/cards\//.test(semComentario(comentario))).toBe(false);
    expect(/\/cards\/\$\{/.test(semComentario(codigo))).toBe(true);
  });

  it("nenhuma lista encolhe a carta por conta própria", () => {
    // O dono reprovou a primeira versão na tela: "as cartas ficaram muito pequenas". Elas estavam
    // em 22px na lista do dashboard e 20px na coluna do leak, cada uma com o seu número. O padrão
    // agora é `ALTURA_DA_CARTA` (36px) e mora no componente.
    //
    // Este guarda não julga tamanho, que é gosto: ele recusa a ALTURA SOLTA. Quem achar 36px
    // grande muda o padrão e todas as listas acompanham, em vez de deixar cada tela com o seu
    // número e a próxima nascer pequena de novo.
    const comAlturaSolta: string[] = [];
    for (const f of arquivosDeCodigo(SRC)) {
      const codigo = readFileSync(f, "utf-8");
      const usos = codigo.match(/<HeroHand[^>]*>/g) ?? [];
      for (const uso of usos) {
        if (/className=\{?"[^"]*(?:^|\s)?h-(?:\[|\d)/.test(uso)) comAlturaSolta.push(f.slice(SRC.length + 1));
      }
    }
    expect(comAlturaSolta, "altura de carta cravada no uso; mude ALTURA_DA_CARTA").toEqual([]);
  });

  it("o guarda ACUSA a altura solta", () => {
    // CONTROLE, porque uma regex errada aqui deixaria o guarda acima verde para sempre.
    const solto = '<HeroHand cards={m.hero_cards} className="h-[22px]" />';
    const certo = '<HeroHand cards={m.hero_cards} />';
    const re = /className=\{?"[^"]*(?:^|\s)?h-(?:\[|\d)/;
    expect(re.test(solto)).toBe(true);
    expect(re.test(certo)).toBe(false);
  });

  it("a varredura está de fato varrendo o repositório", () => {
    expect(arquivosDeCodigo(SRC).length).toBeGreaterThan(100);
  });
});
