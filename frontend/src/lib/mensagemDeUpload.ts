/**
 * A frase que a fila de upload mostra quando um envio falha (hotfix 07/09).
 *
 * O caso que originou: um fundador subindo o mês inteiro de histórico viu "Erro do servidor
 * (HTTP 429)" em dezenas de arquivos. O backend agora responde JSON com `code`,
 * `limite` e `retry_after`; aqui a frase é composta no idioma do jogador, honesta: qual
 * limite, e quanto esperar. Os outros erros seguem como antes: a mensagem do backend
 * quando existe, senão o genérico legível (nunca "HTTP 404" cru).
 */
type Traduz = (chave: string, opcoes?: Record<string, unknown>) => string;

export function mensagemDeErroDeUpload(e: unknown, t: Traduz): string {
  const err = e as (Error & { code?: string; data?: Record<string, unknown> }) | undefined;
  if (err?.code === "upload_rate_limit") {
    const segundos = Number(err.data?.retry_after ?? 0);
    const minutos = Math.max(1, Math.ceil(segundos / 60));
    return t("uploadQueue.rateLimit", { limite: Number(err.data?.limite ?? 0), count: minutos });
  }
  const raw = err instanceof Error ? err.message : "";
  return raw && !/^HTTP \d+$/.test(raw)
    ? raw
    : t("uploadQueue.genericError", { raw: raw || t("uploadQueue.errorFallback") });
}
