/**
 * O que existe no produto, por grupo — a declaração que o menu renderiza.
 *
 * ── Por que existe (28/08) ─────────────────────────────────────────────────────────────────
 *
 * Medido: o produto tem **47 rotas de jogador** e a barra de navegação oferecia **11**. Ficavam
 * invisíveis `/ranges` (construída na véspera justamente porque a matriz de ranges só abria presa
 * a um passo), `/evolucao`, `/ghost`, `/grind`, `/leak-trainer`, `/hand-builder`, `/rating`,
 * `/docs` e **23 aulas da Academia**.
 *
 * É a mesma doença da matriz de ranges, um nível acima e quatro vezes maior: construímos e
 * escondemos.
 *
 * ── A regra do cadeado ─────────────────────────────────────────────────────────────────────
 *
 * O item declara a CAPACIDADE de que depende (`ghost`, `leak_targeted`, `ai_coach_chat`), e o
 * menu pergunta ao backend (`/subscription/status` → `limits`) se o usuário a tem. **Nenhuma
 * lista de "isto é Pro" mora no front** — se morasse, seria a segunda fonte de verdade sobre o
 * plano, e este projeto passou o dia consertando exatamente esse padrão (o preço estava escrito
 * em seis lugares).
 *
 * Cadeado que só diz "Pro" irrita; cadeado que diz o que se ganha vende. Por isso cada item
 * travado carrega um motivo, e não só um ícone.
 *
 * ── O que NÃO está aqui, de propósito ──────────────────────────────────────────────────────
 *
 * `/training/trilha` (a beta oculta por decisão do dono em 28/08), `/training-v2` e
 * `/training/classic` (redirects), `/demo` (é da landing) e `/subscription`/`/profile` (moram no
 * menu da conta, não no de produto).
 */

import { Dumbbell, GraduationCap, LayoutDashboard, Medal } from "lucide-react";

/** Chave de capacidade em `QuotaStatus.limits`. `undefined` = livre para todos. */
export type Capacidade = "ghost" | "leak_targeted" | "ai_coach_chat" | "advanced_insights";

export interface ItemDeMenu {
  to: string;
  /** chave i18n do rótulo, em `dashboard:nav.*` */
  chave: string;
  /** capacidade exigida; sem ela o item aparece com cadeado e o motivo */
  exige?: Capacidade;
}

export interface GrupoDeMenu {
  /** chave i18n do título do grupo */
  chave: string;
  /** para onde o próprio título leva (o grupo continua clicável, não só passável) */
  to: string;
  itens: ItemDeMenu[];
  /** prefixos que acendem o grupo; ver a lógica de "acende por PREFIXO" no HudHeader */
  acende: string[];
  /** ícone do grupo. A barra inferior do mobile é de ícones e deriva DESTA mesma lista: o menu
   *  com painel não cabe em cinco botões, mas ter duas declarações do que existe seria pior. */
  icone: typeof LayoutDashboard;
}

export const GRUPOS: GrupoDeMenu[] = [
  {
    chave: "nav.grupos.meuJogo", icone: LayoutDashboard, to: "/dashboard",
    acende: ["/dashboard", "/tournaments", "/evolucao", "/replayer", "/rating"],
    itens: [
      { to: "/dashboard", chave: "nav.dashboard" },
      { to: "/tournaments", chave: "nav.tournaments" },
      { to: "/tournaments/compare", chave: "nav.comparar" },
      { to: "/evolucao", chave: "nav.evolucao" },
      { to: "/rating", chave: "nav.rating" },
    ],
  },
  {
    chave: "nav.grupos.treinar", icone: Dumbbell, to: "/training",
    acende: ["/training", "/leak-trainer", "/ghost", "/grind", "/ranges"],
    itens: [
      { to: "/training", chave: "nav.treinos" },
      // O acervo é COMPARTILHADO e anonimizado: livre de propósito, e é o que faz o import valer.
      { to: "/grind", chave: "nav.maoCompleta" },
      { to: "/ranges", chave: "nav.ranges" },
      // Estes dois trabalham sobre as SUAS mãos medidas — é a tese do produto, e o que se paga.
      { to: "/leak-trainer", chave: "nav.meusLeaks", exige: "leak_targeted" },
      { to: "/ghost", chave: "nav.ghost", exige: "ghost" },
    ],
  },
  {
    chave: "nav.grupos.estudar", icone: GraduationCap, to: "/study",
    acende: ["/study", "/academy", "/docs", "/hand-builder"],
    itens: [
      { to: "/study", chave: "nav.study" },
      { to: "/academy", chave: "nav.academia" },
      { to: "/hand-builder", chave: "nav.handBuilder" },
      { to: "/docs", chave: "nav.docs" },
    ],
  },
  {
    chave: "nav.grupos.comunidade", icone: Medal, to: "/leaderboard",
    acende: ["/leaderboard", "/coaches"],
    itens: [
      { to: "/leaderboard", chave: "nav.leaderboard" },
      { to: "/coaches", chave: "nav.coaches" },
    ],
  },
];

/** O AI Coach fica fora dos grupos: é uma conversa, não uma seção. */
export const ITEM_COACH: ItemDeMenu = {
  to: "/coach", chave: "nav.coach", exige: "ai_coach_chat",
};
