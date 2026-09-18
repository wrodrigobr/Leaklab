// De `./escopo` e nao de `./api`: quem mocka a API nao pode perder as constantes junto.
import { MESES_MAXIMOS_DO_ESCOPO, TETO_DE_MAOS_DO_ESCOPO, type EscopoDoDashboard } from "./escopo";

/**
 * O escopo do dashboard, GUARDADO por usuário.
 *
 * ── O pedido (17/09) ──────────────────────────────────────────────────────────────────────────
 *
 * "e devemos manter sessao, sempre usar a ultima escolha dele".
 *
 * Hoje o filtro é um `useState` que nasce em "histórico" a cada recarga: o jogador escolhe
 * "últimos 50", atualiza a página e volta para o acervo inteiro sem nada ter mudado na tela.
 *
 * ── Por que `localStorage` e não `sessionStorage` ─────────────────────────────────────────────
 *
 * "sempre usar a última escolha" atravessa o fechar do navegador. `sessionStorage` morre com a
 * aba, e aí a promessa valeria só até ele fechar o computador.
 *
 * ── Por que por USUÁRIO ───────────────────────────────────────────────────────────────────────
 *
 * Mesmo motivo do aviso de drift e do convite do coach, que já são por usuário: dois jogadores na
 * mesma máquina (o dono e um aluno, num teste) herdariam o filtro um do outro, e o escopo decide o
 * NÚMERO que a tela mostra. Preferência de tela pode vazar; escopo de dado não.
 */

const PREFIXO = "escopo_dashboard_v1";

function chave(userId: number | string): string {
  return `${PREFIXO}:${userId}`;
}

/** O escopo padrão: HISTÓRICO genuíno, que é o que a tela abria antes de existir persistência. */
export const ESCOPO_PADRAO: EscopoDoDashboard = { tipo: "torneios", n: 0 };

/**
 * Valida o que veio do storage. Nada aqui confia no conteúdo: `localStorage` é editável pelo
 * jogador, sobrevive a deploy e guarda o formato de uma versão anterior do código. Um escopo
 * inválido volta como padrão em vez de virar uma query que o servidor ignora em silêncio -- e
 * silêncio aqui significa a tela mostrando um número de escopo diferente do que ela declara.
 */
export function escopoValido(bruto: unknown): EscopoDoDashboard | null {
  if (!bruto || typeof bruto !== "object") return null;
  const o = bruto as Record<string, unknown>;
  if (o.tipo === "torneios" || o.tipo === "maos") {
    const n = Number(o.n);
    if (!Number.isFinite(n) || n < 0) return null;
    if (o.tipo === "maos") {
      // zero mãos não é escopo, é tela vazia; e o teto é o mesmo do servidor
      if (n < 1) return null;
      return { tipo: "maos", n: Math.min(Math.floor(n), TETO_DE_MAOS_DO_ESCOPO) };
    }
    return { tipo: "torneios", n: Math.floor(n) };
  }
  if (o.tipo === "periodo") {
    const de = String(o.de ?? "");
    const ate = String(o.ate ?? "");
    const data = /^\d{4}-\d{2}-\d{2}$/;
    if (!data.test(de) || !data.test(ate)) return null;
    // faixa invertida é erro de quem escreveu, e não um escopo vazio: corrige em vez de descartar
    return de <= ate ? { tipo: "periodo", de, ate } : { tipo: "periodo", de: ate, ate: de };
  }
  return null;
}

/** O escopo guardado deste usuário, ou o padrão. */
export function lerEscopo(userId: number | string | undefined): EscopoDoDashboard {
  if (userId == null) return ESCOPO_PADRAO;
  try {
    const bruto = localStorage.getItem(chave(userId));
    if (!bruto) return ESCOPO_PADRAO;
    return escopoValido(JSON.parse(bruto)) ?? ESCOPO_PADRAO;
  } catch {
    // storage bloqueado, JSON corrompido: a tela abre no padrão, e não quebra
    return ESCOPO_PADRAO;
  }
}

/** Guarda a escolha. Escopo inválido não é gravado: melhor perder a preferência que a verdade. */
export function gravarEscopo(userId: number | string | undefined,
                             escopo: EscopoDoDashboard): void {
  if (userId == null) return;
  const limpo = escopoValido(escopo);
  if (!limpo) return;
  try {
    localStorage.setItem(chave(userId), JSON.stringify(limpo));
  } catch {
    /* storage cheio ou bloqueado: a escolha vale nesta sessão e só */
  }
}

/** O piso do seletor de data: o mesmo teto de meses que o servidor apara. */
export function pisoDaFaixa(hoje = new Date()): string {
  const d = new Date(hoje);
  d.setMonth(d.getMonth() - MESES_MAXIMOS_DO_ESCOPO);
  return d.toISOString().slice(0, 10);
}
