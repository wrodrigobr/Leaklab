import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cabeNoTeto, tetoDoPlano, TETO_PADRAO_MB } from "./tetoDeUpload";
import { mensagemDeErroDeUpload } from "./mensagemDeUpload";

/**
 * O teto do arquivo e a frase que ele produz.
 *
 * ── O pedido do dono (16/09) ──────────────────────────────────────────────────────────────────
 *
 * "a mensagem de tamanho excedido tem que ser intuitiva, nao podemos retornar codigo de erro para
 * o usuario, temos que ter o erro tratado."
 *
 * O que ele viu foi "Erro do servidor (HTTP 413)", e esse texto nascia de DOIS lugares do
 * `request()`: o ramo de resposta sem JSON e o `?? \`HTTP ${status}\`` quando o corpo não trazia
 * `error`. O 413 chega de três formas (recusa pelo plano, recusa pelo teto global, e conexão
 * cortada sem corpo), e as três terminavam na tela de um jeito diferente.
 *
 * O último teste deste arquivo é o que amarra o pedido: varre as frases de upload e recusa
 * qualquer código de status no texto.
 */

const MB = 1024 * 1024;

/** `t` de teste: devolve a chave e os valores, para o assert ver o que foi composto. */
const t = (k: string, o?: Record<string, unknown>) =>
  o ? `${k}:${Object.entries(o).map(([a, b]) => `${a}=${b}`).join(",")}` : k;

describe("o teto do arquivo", () => {
  it("compara o tamanho com o teto do plano", () => {
    expect(cabeNoTeto(4 * MB, 5).cabe).toBe(true);
    expect(cabeNoTeto(5 * MB, 5).cabe).toBe(true);        // no limite exato, cabe
    expect(cabeNoTeto(5.1 * MB, 5).cabe).toBe(false);
    expect(cabeNoTeto(15 * MB, 40).cabe).toBe(true);      // o export do Rullian, no Pro
    expect(cabeNoTeto(15 * MB, 5).cabe).toBe(false);      // o mesmo arquivo, no Free
  });

  it("sem saber o plano usa o MENOR teto, nunca o maior", () => {
    // Assumir 40 MB deixaria o jogador esperar o upload inteiro para ser recusado no fim. O
    // servidor corrige para cima se ele for Pro; prometer a mais é que não dá.
    expect(tetoDoPlano(null)).toBe(TETO_PADRAO_MB);
    expect(tetoDoPlano({})).toBe(TETO_PADRAO_MB);
    expect(tetoDoPlano({ limits: {} })).toBe(TETO_PADRAO_MB);
    expect(tetoDoPlano({ limits: { upload_mb: null } })).toBe(TETO_PADRAO_MB);
    expect(cabeNoTeto(10 * MB, null).cabe).toBe(false);
    // e com o plano lido, vale o dele
    expect(tetoDoPlano({ limits: { upload_mb: 40 } })).toBe(40);
  });

  it("o tamanho exibido bate com o veredito", () => {
    // Arredondar aqui e formatar lá geraria "0.0MB" num arquivo pequeno, e um número que não
    // explica a recusa.
    const v = cabeNoTeto(15.04 * MB, 5);
    expect(v.arquivoMb).toBe(15);
    expect(v.tetoMb).toBe(5);
    expect(cabeNoTeto(5.25 * MB, 5).arquivoMb).toBe(5.3);
  });
});

describe("a frase do arquivo grande", () => {
  it("no FREE, diz o tamanho, o teto e oferece o Pro", () => {
    const e = Object.assign(new Error(""), {
      status: 413,
      data: { erro_de_tamanho: { bytes: 15 * MB, limite_mb: 5, plano: "free" } },
    });
    const frase = mensagemDeErroDeUpload(e, t);
    expect(frase).toContain("uploadQueue.grandeFree");
    expect(frase).toContain("arquivo=15.0");
    expect(frase).toContain("teto=5");
  });

  it("no PRO, pede para dividir em vez de oferecer upgrade", () => {
    const e = Object.assign(new Error(""), {
      status: 413,
      data: { erro_de_tamanho: { bytes: 45 * MB, limite_mb: 40, plano: "pro" } },
    });
    expect(mensagemDeErroDeUpload(e, t)).toContain("uploadQueue.grandePro");
  });

  it("413 SEM corpo ainda diz o que fazer", () => {
    // O caminho que produzia "Erro do servidor (HTTP 413)": o Werkzeug corta a conexão quando o
    // corpo passa do teto global, e não há JSON nenhum para ler.
    const e = Object.assign(new Error(""), { status: 413, semCorpo: true as const });
    const frase = mensagemDeErroDeUpload(e, t);
    expect(frase).toBe("uploadQueue.grandeSemNumero");
    expect(frase).not.toContain("413");
  });

  it("erro sem mensagem cai no generico, e nao no status", () => {
    const e = Object.assign(new Error(""), { status: 500, semCorpo: true as const });
    const frase = mensagemDeErroDeUpload(e, t);
    expect(frase).toContain("uploadQueue.genericError");
    expect(frase).not.toContain("500");
  });

  it("a mensagem do backend, quando existe, passa inteira", () => {
    const e = Object.assign(new Error("Você já tem 5 arquivos esperando a vez."), { status: 429 });
    expect(mensagemDeErroDeUpload(e, t)).toBe("Você já tem 5 arquivos esperando a vez.");
  });

  it("NENHUMA frase de upload mostra codigo de status", () => {
    // O guarda do pedido do dono. Ele varre as fontes que compõem o que o jogador lê no upload,
    // e recusa `HTTP ${...}`, `(HTTP` e `status` interpolado em texto.
    //
    // Verificado quebrando: com o `?? \`HTTP ${res.status}\`` de volta no `request`, este teste
    // acusa.
    const raiz = join(import.meta.dirname, "..");
    const fontes = [
      join(raiz, "lib", "api.ts"),
      join(raiz, "lib", "mensagemDeUpload.ts"),
      join(raiz, "components", "hud", "UploadQueue.tsx"),
    ];
    const achados: string[] = [];
    for (const f of fontes) {
      const texto = readFileSync(f, "utf-8");
      const linhas = texto.split("\n");
      linhas.forEach((linha, i) => {
        // Prosa que EXPLICA a regra não vaza para a tela, e o guarda não pode confundir as duas
        // — esta casa já tropeçou nisso três vezes hoje. Cobre `//` e a coluna de `*` do bloco.
        const cru = linha.trimStart();
        if (cru.startsWith("//") || cru.startsWith("*") || cru.startsWith("/*")) return;
        const codigo = linha.split("//")[0];
        if (!/`[^`]*HTTP \$\{/.test(codigo) && !/"[^"]*\(HTTP /.test(codigo)) return;
        // EXCEÇÃO declarada: as rotas de /admin. Quem lê aquele erro é o admin, que é técnico e
        // usa o código para diagnosticar; silenciar ali tiraria informação de quem precisa dela.
        // Declarada como exceção, e não excluída da varredura, para continuar visível.
        const vizinhanca = linhas.slice(Math.max(0, i - 8), i + 1).join("\n");
        if (vizinhanca.includes("/admin/")) return;
        achados.push(`${f.split(/[\\/]/).pop()}:${i + 1}: ${linha.trim().slice(0, 90)}`);
      });
    }
    expect(achados, `frase com codigo de status:\n  ${achados.join("\n  ")}`).toEqual([]);
  });

  it("NAO barra quando o teto do plano ainda NAO se sabe", () => {
    // O bug do Rullian (16/09): ele e Pro com 40MB e a tela recusou 15MB dizendo "o seu plano
    // aceita ate 5MB". O backend estava certo; o defeito era o estado comecar em
    // `TETO_PADRAO_MB` e a fila BARRAR com esse valor.
    //
    // A causa de nunca sair de 5: o `UploadQueueProvider` envolve TODAS as rotas, inclusive a
    // landing publica -- ele monta antes do login, a consulta da quota volta 401, cai no catch,
    // e o efeito tinha `[]` como dependencia.
    //
    // A regra que este guarda trava: **nunca barrar por falta de informacao**. O servidor e a
    // autoridade e tem a mensagem certa. Duas pontas: a checagem e condicional ao teto ser
    // conhecido, e o estado inicial e nulo (e nao um numero pessimista).
    const fonte = readFileSync(
      join(import.meta.dirname, "..", "components", "hud", "UploadQueue.tsx"), "utf-8");
    expect(fonte, "a checagem precisa ser condicional ao teto ser conhecido")
      .toMatch(/if \(tetoMb != null\) \{/);
    expect(fonte, "o estado do teto comeca NULO, e nao num numero pessimista")
      .toMatch(/useState<number \| null>\(null\)/);
    expect(fonte, "e a consulta refaz quando o login acontece")
      .toMatch(/\}, \[user\]\);/);
  });

  it("o UploadQueue barra ANTES de enviar", () => {
    // Sem isto o jogador espera 40 MB subirem para ouvir "não cabe", e a frase do servidor só
    // pode falar do CORPO da requisição (o envio é JSON, maior que o arquivo).
    const fonte = readFileSync(
      join(import.meta.dirname, "..", "components", "hud", "UploadQueue.tsx"), "utf-8");
    const i = fonte.indexOf("cabeNoTeto(file.size");
    expect(i, "a fila precisa medir o arquivo antes de ler o conteudo").toBeGreaterThan(0);
    // e a medida vem ANTES do envio, senão ela não economiza nada
    expect(i).toBeLessThan(fonte.indexOf("tournaments.receber("));
  });
});
