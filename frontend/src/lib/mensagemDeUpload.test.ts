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

  it("no 413 a frase do FRONT manda, e não a do backend", () => {
    // Mudou em 16/09, e este caso travava o contrário: ele exigia que a mensagem do backend
    // ("Arquivo muito grande (limite: 5MB)") passasse inteira para a tela.
    //
    // Agora o 413 é tratado aqui, por três razões: a frase do front é traduzida nos três
    // idiomas, ela diz o que FAZER (exportar período menor, ou o Pro) e ela cobre o caso em que
    // o servidor não manda corpo nenhum -- o Werkzeug corta a conexão quando o corpo passa do
    // teto global, e era esse caminho que produzia "Erro do servidor (HTTP 413)" na tela.
    //
    // A mensagem do backend segue existindo para quem chama a API fora do nosso front.
    expect(mensagemDeErroDeUpload(erro("Arquivo muito grande (limite: 5MB)", { status: 413 }), t))
      .toBe("uploadQueue.grandeSemNumero");
  });

  it("nenhum erro traz o código para a frase", () => {
    // O pedido do dono: "nao podemos retornar codigo de erro para o usuario". Vale também para
    // o que o backend devolve como texto: "HTTP 404" vindo de lá não vira frase.
    expect(mensagemDeErroDeUpload(erro("HTTP 404", { status: 404 }), t))
      .toBe("uploadQueue.genericError:raw=uploadQueue.errorFallback");
    expect(mensagemDeErroDeUpload(undefined, t))
      .toBe("uploadQueue.genericError:raw=uploadQueue.errorFallback");
    // e a mensagem HONESTA do backend continua passando inteira: ela é melhor que a genérica
    expect(mensagemDeErroDeUpload(erro("Você já tem 5 arquivos esperando.", { status: 429 }), t))
      .toBe("Você já tem 5 arquivos esperando.");
  });
});
