import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { GRUPOS, ITEM_COACH, type Capacidade } from "./navGrupos";

/**
 * Nenhuma chave `nav.*` chega crua à tela, em nenhum idioma.
 *
 * ── O que originou (29/08) ────────────────────────────────────────────────────────────────
 *
 * O dono abriu o menu no celular e fotografou `nav.dashboard`, `nav.tournaments`, `nav.study`,
 * `nav.leaderboard`, `nav.coaches` — e, no print seguinte, `NAV.MENU` na barra de baixo.
 *
 * Não faltava tradução. Os rótulos antigos sempre moraram em `common.json`, que é o `defaultNS`;
 * eu escrevi os componentes novos com `useTranslation("dashboard")` e pus lá as chaves que criei.
 * Metade do menu resolvia, metade caía no literal — no i18next, chave sem tradução **não é erro**:
 * ela vira o próprio texto. O `NAV.MENU` é a mesma falha num TERCEIRO arquivo (`HudHeader`, que
 * usa `useTranslation()` sem argumento, portanto `common`).
 *
 * ── Por que a varredura, e não a lista ────────────────────────────────────────────────────
 *
 * Meu primeiro guarda afirmava "MenuDeGrupo e FolhaDeMenu leem de common" — os dois arquivos que
 * eu tinha na cabeça. Passou verde com o `NAV.MENU` quebrado na tela do dono. É a regra 5 do
 * CLAUDE.md: regra que vale em N lugares precisa de varredura que ache o N+1.
 *
 * Este teste não sabe quais arquivos existem. Ele lê a fonte inteira, extrai toda chave `nav.*`
 * passada a `t()`, descobre o namespace QUE AQUELE ARQUIVO pede, e confere nos três locales.
 * Arquivo novo entra na varredura sozinho.
 */

const LOCALES = ["pt-BR", "en", "es"] as const;
const SRC = path.join(__dirname, "../..");

function arquivos(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return arquivos(p);
    return /\.tsx?$/.test(e.name) && !/\.test\./.test(e.name) ? [p] : [];
  });
}

function dicionario(locale: string, ns: string): Record<string, unknown> {
  const p = path.join(SRC, "i18n/locales", locale, `${ns}.json`);
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf-8")) : {};
}

function resolve(dic: Record<string, unknown>, chave: string): string | undefined {
  const v = chave.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], dic);
  return typeof v === "string" ? v : undefined;
}

/** O namespace que o arquivo pede. `useTranslation()` sem argumento = `defaultNS` = common. */
function namespaceDe(fonte: string): string[] {
  const m = fonte.match(/useTranslation\(\s*(\[[^\]]*\]|"[^"]*"|'[^']*')?\s*\)/);
  if (!m || !m[1]) return ["common"];
  return [...m[1].matchAll(/["']([^"']+)["']/g)].map((x) => x[1]);
}

/** Toda chave `nav.*` LITERAL passada a t() naquele arquivo. Interpoladas ficam de fora aqui. */
function chavesLiterais(fonte: string): string[] {
  return [...fonte.matchAll(/\bt\(\s*["'](nav\.[A-Za-z0-9_.]+)["']/g)].map((m) => m[1]);
}

/** Tudo que o MENU manda para o t(), derivado da declaração — cobre o caminho interpolado. */
function chavesDoMenu(): string[] {
  const itens = [...GRUPOS.flatMap((g) => g.itens), ITEM_COACH];
  const exigidas = new Set<Capacidade>(itens.map((i) => i.exige).filter(Boolean) as Capacidade[]);
  return [
    ...GRUPOS.map((g) => g.chave),
    ...itens.map((i) => i.chave),
    ...itens.map((i) => i.desc),
    ...[...exigidas].map((c) => `nav.motivo.${c}`),
  ];
}

describe("rótulos de navegação", () => {
  const fontes = arquivos(SRC).map((p) => ({ p, texto: fs.readFileSync(p, "utf-8") }))
    .filter((f) => chavesLiterais(f.texto).length > 0);

  it("a varredura enxerga os arquivos (senão ela aprova o vazio)", () => {
    // Controle de detecção: um varredor que lê zero arquivos devolve "nenhuma suspeita" e encerra
    // a investigação. Já aconteceu neste projeto.
    expect(fontes.length, "a varredura não achou nenhum consumidor de nav.*").toBeGreaterThan(3);
  });

  it.each(LOCALES)("resolvem no namespace que cada arquivo pede — %s", (locale) => {
    const cruas: string[] = [];
    for (const { p, texto } of fontes) {
      const nss = namespaceDe(texto);
      for (const chave of new Set(chavesLiterais(texto))) {
        if (!nss.some((ns) => resolve(dicionario(locale, ns), chave))) {
          cruas.push(`${path.basename(p)} [${nss.join("+")}] ${chave}`);
        }
      }
    }
    expect(cruas, `chave sem tradução — vai para a tela como texto cru em ${locale}`).toEqual([]);
  });

  it.each(LOCALES)("as chaves interpoladas do menu resolvem — %s", (locale) => {
    // `t(item.chave)` e `t(\`nav.motivo.${...}\`)` não aparecem na varredura de literais: vêm da
    // declaração. Item novo em GRUPOS sem tradução para `es` falha aqui.
    const dic = dicionario(locale, "common");
    expect(chavesDoMenu().filter((c) => !resolve(dic, c))).toEqual([]);
  });

  it("nenhum rótulo do menu tem DOIS donos", () => {
    // CONTRAPROVA do conserto: as chaves foram MOVIDAS para common, não copiadas. Se alguém
    // "consertar" o próximo rótulo cru copiando para o outro namespace, os dois divergem calados —
    // o padrão que custou o dia quando o preço morava em seis lugares.
    for (const locale of LOCALES) {
      const dash = dicionario(locale, "dashboard");
      expect(chavesDoMenu().filter((c) => resolve(dash, c) !== undefined),
             `${locale}: rótulo do menu duplicado em dashboard.json`).toEqual([]);
    }
  });
});
