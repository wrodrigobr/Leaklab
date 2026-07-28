import { describe, it, expect } from "vitest";
import { parseApiDate, formatApiDate } from "../apiDate";

/**
 * O formato da data muda com o BACKEND, e o dev roda o backend errado.
 *
 * O bug ("Invalid Date" no histórico de relatórios, visto em produção): o Flask serializa
 * `datetime` do Postgres como HTTP date, e o SQLite devolve a coluna como string crua. O código
 * assumia o segundo. Em dev — SQLite — funcionava; em produção, não.
 */
describe("parseApiDate", () => {
  it("lê o formato do Postgres via Flask (HTTP date)", () => {
    const d = parseApiDate("Tue, 28 Jul 2026 10:21:26 GMT");
    expect(d).not.toBeNull();
    expect(d!.getUTCFullYear()).toBe(2026);
    expect(d!.getUTCMonth()).toBe(6);      // julho
    expect(d!.getUTCDate()).toBe(28);
    expect(d!.getUTCHours()).toBe(10);
  });

  it("lê o formato do SQLite (string crua, sem T nem timezone)", () => {
    const d = parseApiDate("2026-07-28 10:21:26");
    expect(d).not.toBeNull();
    expect(d!.getUTCFullYear()).toBe(2026);
    expect(d!.getUTCDate()).toBe(28);
    expect(d!.getUTCHours()).toBe(10);     // o backend grava em UTC
  });

  it("lê ISO com e sem microssegundos", () => {
    expect(parseApiDate("2026-07-28T10:21:26Z")!.getUTCHours()).toBe(10);
    expect(parseApiDate("2026-07-28 10:21:26.123456")!.getUTCDate()).toBe(28);
  });

  it("devolve null no ilegível, em vez de uma data inventada", () => {
    // Data inválida silenciosa é pior que ausência: vira "01/01/1970" na tela, e ninguém
    // desconfia de um número plausível.
    for (const lixo of ["", null, undefined, "amanhã", "0000-00-00 00:00:00"]) {
      expect(parseApiDate(lixo as string)).toBeNull();
    }
  });

  it("formatApiDate devolve null quando não dá para ler", () => {
    expect(formatApiDate("quebrado")).toBeNull();
    expect(formatApiDate("Tue, 28 Jul 2026 10:21:26 GMT")).toBeTruthy();
  });
});
