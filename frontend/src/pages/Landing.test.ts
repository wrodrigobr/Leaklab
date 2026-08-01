import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";

/**
 * Copy escrita e nunca renderizada é trabalho que não chegou a ninguém.
 *
 * Foi o que aconteceu com a seção do diferencial: o texto entrou nas 3 locales, com o argumento
 * que o produto tem e os concorrentes não, e a seção nunca foi renderizada em `Landing.tsx`. Nada
 * quebrou, nenhum teste caiu, e a landing ficou pela metade sem sinal nenhum.
 *
 * O guarda varre TODOS os grupos de `landing.json` em vez de conferir só o novo: o próximo grupo
 * órfão se denuncia sozinho.
 */
const LOCALES = ["pt-BR", "en", "es"] as const;
const PAGINA = "src/pages/Landing.tsx";

const json = (loc: string) =>
  JSON.parse(readFileSync(`src/i18n/locales/${loc}/landing.json`, "utf-8")) as Record<string, unknown>;

const fonte = () => readFileSync(PAGINA, "utf-8");

/** Chaves folha de um grupo, no formato `grupo.chave` que o `t()` usa. */
function chavesDoGrupo(grupo: string, valor: unknown): string[] {
  if (typeof valor !== "object" || valor === null) return [grupo];
  return Object.entries(valor as Record<string, unknown>)
    .flatMap(([k, v]) => chavesDoGrupo(`${grupo}.${k}`, v));
}

describe("landing — copy escrita chega à tela", () => {
  it("o diferencial está nas 3 locales e inteiro", () => {
    const esperadas = ["eyebrow", "heading", "sub", "c1Title", "c1Desc",
                       "c2Title", "c2Desc", "c3Title", "c3Desc", "nota"];
    for (const loc of LOCALES) {
      const prova = json(loc).prova as Record<string, string> | undefined;
      expect(prova, `${loc}: bloco 'prova' ausente`).toBeTruthy();
      for (const k of esperadas) {
        expect(prova![k], `${loc}: prova.${k} ausente ou vazia`).toBeTruthy();
      }
    }
  });

  it("a página renderiza todas as chaves do diferencial", () => {
    const src = fonte();
    for (const k of chavesDoGrupo("prova", json("pt-BR").prova)) {
      expect(src, `${k} existe na copy mas a página não a usa`).toContain(k);
    }
  });

  it("nenhum grupo de copy da landing ficou órfão", () => {
    // A varredura inteira, não só o grupo novo. Um grupo é considerado usado quando a página
    // cita qualquer chave dele — seções montam o texto por partes, e exigir chave a chave aqui
    // daria falso positivo em copy usada por outro componente.
    const src = fonte();
    const grupos = Object.entries(json("pt-BR"));
    expect(grupos.length, "landing.json vazio — o seletor quebrou").toBeGreaterThan(3);

    const orfaos = grupos
      .filter(([grupo, valor]) =>
        !chavesDoGrupo(grupo, valor).some((k) => src.includes(k)))
      .map(([grupo]) => grupo);

    expect(orfaos, "grupo de copy que nenhuma seção renderiza").toEqual([]);
  });
});
