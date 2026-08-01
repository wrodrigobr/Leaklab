// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { sample } from "./api";

/**
 * A chamada do exemplo NÃO pode disparar preflight.
 *
 * Ela nasceu passando pelo `request()` comum, que manda sempre `Content-Type: application/json`
 * (e `Authorization`, se houver sessão). Num GET sem corpo esse cabeçalho não serve para nada, e
 * torna a requisição "não-simples": o navegador manda um `OPTIONS` antes.
 *
 * O preço apareceu em produção. O Cloudflare Pages publica o frontend a cada push sem esperar o
 * deploy do backend, então houve uma janela com a rota ainda inexistente. Em vez de um 404 que o
 * componente trata em silêncio, o preflight falhou e o console exibiu um erro de CORS — que
 * aponta para o lugar errado e faz parecer configuração quebrada.
 *
 * Um GET simples falha de um jeito honesto: 404.
 */
afterEach(() => vi.unstubAllGlobals());

function fetchEspiao(resposta: Partial<Response> = {}) {
  const espiao = vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => ({ decision: {} }), ...resposta,
  });
  vi.stubGlobal("fetch", espiao);
  return espiao;
}

describe("decisão de exemplo — requisição simples, sem preflight", () => {
  it("não manda cabeçalho nenhum", async () => {
    const espiao = fetchEspiao();
    await sample.decision();

    expect(espiao).toHaveBeenCalledTimes(1);
    const [url, init] = espiao.mock.calls[0];
    expect(String(url)).toContain("/sample/decision");
    // Sem `init`, ou com um `init` sem headers: os dois deixam a requisição simples. Qualquer
    // cabeçalho aqui (Content-Type, Authorization) reintroduz o OPTIONS.
    const headers = (init as RequestInit | undefined)?.headers;
    expect(headers, "cabeçalho de volta na chamada pública — volta o preflight").toBeUndefined();
  });

  it("não manda credenciais mesmo com sessão aberta", async () => {
    // Um usuário logado que visita a landing passaria a mandar `Authorization`, e o preflight
    // voltaria só para ele — a pior classe de bug, porque não reproduz deslogado.
    sessionStorage.setItem("ll_token", "token-de-teste");
    const espiao = fetchEspiao();
    await sample.decision();
    sessionStorage.removeItem("ll_token");

    const init = espiao.mock.calls[0][1] as RequestInit | undefined;
    expect(JSON.stringify(init ?? {})).not.toContain("token-de-teste");
  });

  it("erro de rede/404 vira exceção para o chamador tratar", async () => {
    fetchEspiao({ ok: false, status: 404 });
    await expect(sample.decision()).rejects.toThrow(/404/);
  });
});
