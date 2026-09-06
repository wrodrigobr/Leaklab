import { describe, it, expect } from "vitest";
import { ultimosTorneios } from "./ultimosTorneios";

/**
 * O dono viu "50 torneios" no histórico e desconfiou do número cravado (06/09). Era: a lista
 * chegava capada em 50 pelo backend E o dashboard cortava "últimos N" pelo FIM de uma lista
 * ordenada por importação DESC — os N mais ANTIGOS. Os dois defeitos somados: "Histórico" era
 * 50, e "últimos 30" eram os 30 mais velhos desses 50.
 */
const t = (id: string, played_at: string | null, imported_at: string) =>
  ({ id, played_at, imported_at }) as unknown as { id: string; played_at: string | null; imported_at: string };

// como o backend entrega: importação DESC. O mais recente por JOGO está no meio.
const LISTA = [
  t("c", "2026-01-10", "2026-09-06"),   // importado hoje, jogado em janeiro
  t("a", "2026-09-01", "2026-09-02"),   // o mais recente por jogo
  t("b", "2026-08-15", "2026-08-16"),
];

describe("ultimosTorneios", () => {
  it("corta os N mais RECENTES por data de jogo, nao o fim da lista", () => {
    expect(ultimosTorneios(LISTA, 1).map((x) => x.id)).toEqual(["a"]);
    expect(ultimosTorneios(LISTA, 2).map((x) => x.id)).toEqual(["a", "b"]);
  });

  it("0 e null sao o historico inteiro", () => {
    expect(ultimosTorneios(LISTA, 0)).toHaveLength(3);
    expect(ultimosTorneios(LISTA, null)).toHaveLength(3);
  });

  it("sem data de jogo, a de importacao vale como eixo (COALESCE do backend)", () => {
    const lista = [t("x", null, "2026-09-05"), t("y", "2026-09-04", "2026-01-01")];
    expect(ultimosTorneios(lista, 1).map((x) => x.id)).toEqual(["x"]);
  });

  it("nao muda a lista original (tourns[0] continua sendo o ultimo IMPORTADO)", () => {
    const copia = [...LISTA];
    ultimosTorneios(LISTA, 2);
    expect(LISTA.map((x) => x.id)).toEqual(copia.map((x) => x.id));
  });
});
