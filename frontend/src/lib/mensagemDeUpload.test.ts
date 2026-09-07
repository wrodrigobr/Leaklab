import { describe, it, expect } from "vitest";
import { mensagemDeErroDeUpload } from "./mensagemDeUpload";

const t = (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.entries(o).map(([a, b]) => `${a}=${b}`).join(",")}` : k);

function erro(msg: string, extra: Record<string, unknown> = {}) {
  return Object.assign(new Error(msg), extra);
}

describe("mensagem de erro da fila de upload", () => {
  it("429 do limite vira a frase honesta, com o limite e os minutos arredondados para cima", () => {
    const e = erro("Você ultrapassou…", { code: "upload_rate_limit", status: 429, data: { limite: 300, retry_after: 1501 } });
    expect(mensagemDeErroDeUpload(e, t)).toBe("uploadQueue.rateLimit:limite=300,count=26");
  });

  it("retry_after de poucos segundos ainda diz 1 minuto, nunca 0", () => {
    const e = erro("x", { code: "upload_rate_limit", data: { limite: 300, retry_after: 5 } });
    expect(mensagemDeErroDeUpload(e, t)).toContain("count=1");
  });

  it("os outros erros seguem como antes: mensagem do backend, ou o genérico sem HTTP cru", () => {
    expect(mensagemDeErroDeUpload(erro("Arquivo muito grande (limite: 5MB)", { status: 413 }), t)).toBe("Arquivo muito grande (limite: 5MB)");
    expect(mensagemDeErroDeUpload(erro("HTTP 404", { status: 404 }), t)).toBe("uploadQueue.genericError:raw=HTTP 404");
    expect(mensagemDeErroDeUpload(undefined, t)).toBe("uploadQueue.genericError:raw=uploadQueue.errorFallback");
  });
});
