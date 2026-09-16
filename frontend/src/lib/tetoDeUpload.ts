/**
 * O teto de tamanho do arquivo, do lado do jogador.
 *
 * ── Por que a checagem existe NO FRONT, se o backend já recusa ────────────────────────────────
 *
 * Três razões, e nenhuma é desconfiança do servidor:
 *
 * 1. **Ele sabe na hora.** Barrar depois do envio significa esperar 40 MB subirem para ouvir
 *    "não cabe". Com a conta do lado do jogador, a resposta é imediata e ele já sabe o que fazer.
 * 2. **A mensagem pode dizer o tamanho do ARQUIVO.** O envio vai como JSON, então o corpo da
 *    requisição é maior que o arquivo (cada `\n` viaja escapado). O backend mede o corpo, e uma
 *    mensagem dizendo "seu arquivo tem 5,2MB" para um arquivo de 4,9MB é uma mentira pequena que
 *    faz o jogador duvidar do resto.
 * 3. **O 413 do servidor não chega inteiro.** Quando o corpo passa do `MAX_CONTENT_LENGTH`
 *    global, o Werkzeug pode cortar a conexão antes da resposta, e o `fetch` estoura com erro de
 *    rede. O jogador via "Erro do servidor (HTTP 413)", que foi exatamente a reclamação do dono:
 *    código de erro não é mensagem.
 *
 * O backend segue sendo a autoridade (ele recusa de novo, pelo header, antes de ler o corpo).
 * Isto aqui é a cortesia de dizer antes.
 */

/** O teto quando a quota ainda não chegou. O menor dos planos: nunca prometer mais do que o
 *  jogador tem, e a recusa do servidor é quem corrige para cima se ele for Pro. */
export const TETO_PADRAO_MB = 5;

const MB = 1024 * 1024;

export interface VeredictoDoTeto {
  cabe: boolean;
  /** tamanho do arquivo em MB, com uma decimal */
  arquivoMb: number;
  tetoMb: number;
}

/**
 * O arquivo cabe no teto do plano?
 *
 * `tetoMb` nulo ou ausente cai em `TETO_PADRAO_MB`: sem saber o plano, a conta usa o menor teto.
 * O contrário (assumir o maior) deixaria o jogador enviar 40 MB para ser recusado no fim.
 */
export function cabeNoTeto(bytes: number, tetoMb?: number | null): VeredictoDoTeto {
  const teto = Number(tetoMb) > 0 ? Number(tetoMb) : TETO_PADRAO_MB;
  const n = Number(bytes) || 0;
  return {
    cabe: n <= teto * MB,
    // uma decimal, como a mensagem mostra: arredondar aqui e formatar lá geraria "0.0MB" para
    // arquivo pequeno e um veredito que não bate com o número exibido
    arquivoMb: Math.round((n / MB) * 10) / 10,
    tetoMb: teto,
  };
}

/** O teto do plano, lido da quota. Uma função para o front não espalhar `limits?.upload_mb`. */
export function tetoDoPlano(quota?: { limits?: { upload_mb?: number | null } } | null): number {
  return Number(quota?.limits?.upload_mb) > 0
    ? Number(quota!.limits!.upload_mb)
    : TETO_PADRAO_MB;
}
