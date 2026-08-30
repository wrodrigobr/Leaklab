import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * TODA chave literal passada a t() resolve no namespace que o arquivo pede, nos 3 idiomas.
 *
 * ── O que originou (30/08, terceira ocorrência da família) ────────────────────────────────
 *
 * `LEAKTRAINER.GATE.TARGETEDTITLE` cru na tela do dono — um cadeado escrito com chaves que
 * nunca foram criadas. Antes: `nav.dashboard`/`NAV.MENU` (namespace errado). O guarda de
 * nav.* era estreito demais: pegava a família só quando ela vestia `nav.`.
 *
 * Este guarda generaliza: varre TODO .tsx, extrai as chaves literais de `t("...")`, resolve
 * no namespace do `useTranslation` daquele arquivo (com fallback no defaultNS `common`), nos
 * 3 locales. Chave interpolada fica de fora (os guardas derivados de declaração cobrem as
 * suas famílias); chave literal sem tradução falha AQUI, não na tela.
 */

const SRC = path.join(__dirname, "..");
const LOCALES = ["pt-BR", "en", "es"] as const;
const dicCache = new Map<string, Record<string, unknown>>();

function dic(locale: string, ns: string): Record<string, unknown> {
  const k = `${locale}/${ns}`;
  if (!dicCache.has(k)) {
    const p = path.join(SRC, "i18n/locales", locale, `${ns}.json`);
    dicCache.set(k, fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf-8")) : {});
  }
  return dicCache.get(k)!;
}

function resolve(d: Record<string, unknown>, chave: string): boolean {
  // pluralização do i18next: `level.tournament` resolve por `tournament_one/_other`
  for (const k of [chave, `${chave}_one`, `${chave}_other`]) {
    const v = k.split(".").reduce<unknown>((o, c) => (o as Record<string, unknown>)?.[c], d);
    if (typeof v === "string" || Array.isArray(v)) return true;
  }
  return false;
}

function todosNs(): string[] {
  return fs.readdirSync(path.join(SRC, "i18n/locales/pt-BR"))
    .filter((f) => f.endsWith(".json")).map((f) => f.replace(".json", ""));
}

function arquivos(d: string): string[] {
  return fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) return arquivos(p);
    return /\.tsx$/.test(e.name) && !/\.test\./.test(e.name) ? [p] : [];
  });
}

describe("cobertura de i18n das chaves literais", () => {
  const casos: { onde: string; ns: string[]; chave: string }[] = [];
  for (const f of arquivos(SRC)) {
    const texto = fs.readFileSync(f, "utf-8");
    // TODOS os namespaces declarados no arquivo (um .tsx pode ter varios componentes, cada
    // um com o seu useTranslation) — a chave vale se resolve em QUALQUER um deles + common.
    // Aproximacao assumida: mais frouxa que o ideal, mas sem falso positivo.
    // O `t` pode vir por PROP com namespace de OUTRO arquivo (SidePanels recebe o do
    // Replayer e ainda declara academy num componente interno) — namespace estático não
    // decide. A rede assumida é global: a chave vale se existe em ALGUM namespace. Mais
    // frouxa que o ideal, e ainda assim pegou as 3 ocorrências reais da família (gate do
    // LeakTrainer, boletim.travado.*, summary.spread*): o bug típico é a chave que não
    // existe em lugar NENHUM.
    const nss = todosNs();
    // só o `t(` puro: aliases (tr, tc...) apontam para OUTRO namespace declarado à parte
    // exige fechamento logo após a string: t("chave" + sufixo) é COMPOSIÇÃO dinâmica
    // (card.cost + qualificador) e não uma chave completa — era o falso positivo.
    for (const mm of texto.matchAll(/[^a-zA-Z_.]t\(\s*"([A-Za-z0-9_.]+)"\s*[),]/g)) {
      casos.push({ onde: path.relative(SRC, f), ns: [...nss, "common"], chave: mm[1] });
    }
  }

  it("a varredura enxerga o app (senão aprova o vazio)", () => {
    expect(casos.length).toBeGreaterThan(300);
  });

  it.each(LOCALES)("todas resolvem em %s", (locale) => {
    const cruas = [...new Set(
      casos.filter((c) => !c.ns.some((ns) => resolve(dic(locale, ns), c.chave)))
        .map((c) => `${c.onde} [${c.ns[0]}] ${c.chave}`),
    )];
    expect(cruas, `chaves que vão CRUAS para a tela em ${locale}`).toEqual([]);
  });
});
