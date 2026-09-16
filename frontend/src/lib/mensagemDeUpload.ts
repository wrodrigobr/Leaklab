/**
 * A frase que a fila de upload mostra quando um envio falha (hotfix 07/09).
 *
 * O caso que originou: um fundador subindo o mês inteiro de histórico viu "Erro do servidor
 * (HTTP 429)" em dezenas de arquivos. O backend agora responde JSON com `code`,
 * `limite` e `retry_after`; aqui a frase é composta no idioma do jogador, honesta: qual
 * limite, e quanto esperar.
 *
 * ── Arquivo grande demais (16/09) ─────────────────────────────────────────────────────────────
 *
 * O dono: "a mensagem de tamanho excedido tem que ser intuitiva, nao podemos retornar codigo de
 * erro para o usuario, temos que ter o erro tratado".
 *
 * O 413 chega de TRÊS formas diferentes, e as três precisavam de tratamento:
 *
 * 1. Recusa pelo plano, na rota: vem JSON com `erro_de_tamanho` e uma frase pronta.
 * 2. Recusa pelo `MAX_CONTENT_LENGTH` global: vem JSON do `errorhandler(413)`.
 * 3. **Sem corpo nenhum:** o Werkzeug corta a conexão quando o corpo passa do teto global, e o
 *    `fetch` volta com uma resposta que não é JSON. Este era o caminho que produzia "Erro do
 *    servidor (HTTP 413)" na tela, e é o que o `semCorpo` do `request()` agora marca.
 *
 * Em todos, a frase fala de arquivo e de caminho de saída, nunca de código. O tamanho e o teto
 * vêm do backend quando ele os manda; quando não manda (caso 3), a frase é a genérica do tamanho,
 * que ainda diz o que fazer.
 */
type Traduz = (chave: string, opcoes?: Record<string, unknown>) => string;

interface ErroDeUpload extends Error {
  code?: string;
  status?: number;
  semCorpo?: true;
  data?: Record<string, unknown>;
}

export function mensagemDeErroDeUpload(e: unknown, t: Traduz): string {
  const err = e as ErroDeUpload | undefined;

  if (err?.code === "upload_rate_limit") {
    const segundos = Number(err.data?.retry_after ?? 0);
    const minutos = Math.max(1, Math.ceil(segundos / 60));
    return t("uploadQueue.rateLimit", { limite: Number(err.data?.limite ?? 0), count: minutos });
  }

  // ── arquivo grande demais ────────────────────────────────────────────────────────────────
  if (err?.status === 413) {
    const d = (err.data?.erro_de_tamanho ?? null) as
      { bytes?: number; limite_mb?: number; plano?: string } | null;
    const tetoMb = Number(d?.limite_mb) || 0;
    const mb = Number(d?.bytes) ? Number(d!.bytes) / (1024 * 1024) : 0;
    if (tetoMb && mb) {
      // O backend sabe o plano: a frase do free oferece o Pro, a do pro pede para dividir.
      const chave = d?.plano === "free" ? "uploadQueue.grandeFree" : "uploadQueue.grandePro";
      return t(chave, { arquivo: mb.toFixed(1), teto: tetoMb });
    }
    // Sem os números (caso 3, e o `errorhandler` global): a frase genérica do tamanho, que
    // continua dizendo o que fazer em vez de mostrar o código.
    return t("uploadQueue.grandeSemNumero");
  }

  const raw = err instanceof Error ? err.message : "";
  // `semCorpo` e mensagem vazia caem no genérico: o `request()` deixou o texto vazio de propósito
  // para que nenhum "HTTP 500" chegue à tela por uma superfície que só mostre `message`.
  return raw && !/^HTTP \d+$/.test(raw)
    ? raw
    : t("uploadQueue.genericError", { raw: t("uploadQueue.errorFallback") });
}
