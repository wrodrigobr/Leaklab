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

import {
  BookOpen, BookText, Bot, Blocks, Crosshair, Dumbbell, GitCompareArrows, Ghost,
  Grid3x3, GraduationCap, LayoutDashboard, Medal, MessagesSquare, Spade, TrendingUp, Trophy, Users,
} from "lucide-react";

/** Chave de capacidade em `QuotaStatus.limits`. `undefined` = livre para todos. */
export type Capacidade = "ghost" | "leak_targeted" | "ai_coach_chat" | "advanced_insights";

/** Cor de INTENÇÃO do item — a mesma linguagem dos ícones do catálogo de treino (30/08):
 *  teal=fazer, amber=resultado, blue=consultar/defender, red=seus erros, purple=memória. */
export type CorDeItem = "teal" | "amber" | "blue" | "red" | "purple";

export interface ItemDeMenu {
  to: string;
  /** chave i18n do rótulo, em `common:nav.*` */
  chave: string;
  /** chave i18n da descrição de uma linha (`common:nav.desc.*`) — o mega-menu mostra sempre */
  desc: string;
  /** ícone do item (o painel estilo mega-menu dá um tile por item) */
  icone: typeof LayoutDashboard;
  /** cor de intenção do tile; sem ela, teal */
  cor?: CorDeItem;
  /** capacidade exigida; sem ela o item aparece com cadeado e o motivo */
  exige?: Capacidade;
}

/** Coluna TITULADA do mega-menu (v2, 30/08): a arquitetura do grupo aparece antes dos itens —
 *  a diferença nº 1 medida contra o benchmark. */
export interface SecaoDeMenu {
  /** chave i18n do título da seção (`common:nav.secoes.*`) */
  chave: string;
  itens: ItemDeMenu[];
}

export interface GrupoDeMenu {
  /** chave i18n do título do grupo */
  chave: string;
  /** para onde o próprio título leva (o grupo continua clicável, não só passável) */
  to: string;
  /** as colunas do painel. `itens` (abaixo) é DERIVADO delas — fonte única é a seção. */
  secoes: SecaoDeMenu[];
  itens: ItemDeMenu[];
  /** prefixos que acendem o grupo; ver a lógica de "acende por PREFIXO" no HudHeader */
  acende: string[];
  /** ícone do grupo. A barra inferior do mobile é de ícones e deriva DESTA mesma lista: o menu
   *  com painel não cabe em cinco botões, mas ter duas declarações do que existe seria pior. */
  icone: typeof LayoutDashboard;
}

const SECOES_MEU_JOGO: SecaoDeMenu[] = [
  { chave: "nav.secoes.resultados", itens: [
    { to: "/dashboard", chave: "nav.dashboard", desc: "nav.desc.dashboard", icone: LayoutDashboard, cor: "teal" },
    { to: "/tournaments", chave: "nav.tournaments", desc: "nav.desc.tournaments", icone: Trophy, cor: "amber" },
    { to: "/tournaments/compare", chave: "nav.comparar", desc: "nav.desc.comparar", icone: GitCompareArrows, cor: "blue" },
  ]},
  { chave: "nav.secoes.progresso", itens: [
    { to: "/evolucao", chave: "nav.evolucao", desc: "nav.desc.evolucao", icone: TrendingUp, cor: "teal" },
    { to: "/rating", chave: "nav.rating", desc: "nav.desc.rating", icone: Medal, cor: "amber" },
  ]},
];

const SECOES_TREINAR: SecaoDeMenu[] = [
  { chave: "nav.secoes.praticar", itens: [
    { to: "/training", chave: "nav.treinos", desc: "nav.desc.treinos", icone: Dumbbell, cor: "teal" },
    // O acervo é COMPARTILHADO e anonimizado: livre de propósito, e é o que faz o import valer.
    { to: "/grind", chave: "nav.maoCompleta", desc: "nav.desc.maoCompleta", icone: Spade, cor: "teal" },
  ]},
  // A coluna que explica o preço: é onde mora o PRO, e o título diz o porquê.
  { chave: "nav.secoes.errosMedidos", itens: [
    { to: "/leak-trainer", chave: "nav.meusLeaks", desc: "nav.desc.meusLeaks", icone: Crosshair, cor: "red", exige: "leak_targeted" },
    { to: "/ghost", chave: "nav.ghost", desc: "nav.desc.ghost", icone: Ghost, cor: "purple", exige: "ghost" },
  ]},
  { chave: "nav.secoes.consulta", itens: [
    { to: "/ranges", chave: "nav.ranges", desc: "nav.desc.ranges", icone: Grid3x3, cor: "blue" },
  ]},
];

const SECOES_ESTUDAR: SecaoDeMenu[] = [
  { chave: "nav.secoes.aprender", itens: [
    { to: "/study", chave: "nav.study", desc: "nav.desc.study", icone: BookOpen, cor: "teal", exige: "advanced_insights" },
    { to: "/academy", chave: "nav.academia", desc: "nav.desc.academia", icone: GraduationCap, cor: "purple" },
  ]},
  { chave: "nav.secoes.ferramentas", itens: [
    { to: "/docs", chave: "nav.docs", desc: "nav.desc.docs", icone: BookText, cor: "amber" },
  ]},
];

const SECOES_COMUNIDADE: SecaoDeMenu[] = [
  { chave: "nav.grupos.comunidade", itens: [
    { to: "/maos", chave: "nav.maosCompartilhadas", desc: "nav.desc.maosCompartilhadas", icone: MessagesSquare, cor: "teal" },
    { to: "/leaderboard", chave: "nav.leaderboard", desc: "nav.desc.leaderboard", icone: Medal, cor: "amber" },
    { to: "/coaches", chave: "nav.coaches", desc: "nav.desc.coaches", icone: Users, cor: "teal" },
  ]},
];

const _itens = (secoes: SecaoDeMenu[]) => secoes.flatMap((sec) => sec.itens);

export const GRUPOS: GrupoDeMenu[] = [
  {
    chave: "nav.grupos.meuJogo", icone: LayoutDashboard, to: "/dashboard",
    acende: ["/dashboard", "/tournaments", "/evolucao", "/replayer", "/rating"],
    secoes: SECOES_MEU_JOGO, itens: _itens(SECOES_MEU_JOGO),
  },
  {
    chave: "nav.grupos.treinar", icone: Dumbbell, to: "/training",
    acende: ["/training", "/leak-trainer", "/ghost", "/grind", "/ranges"],
    secoes: SECOES_TREINAR, itens: _itens(SECOES_TREINAR),
  },
  {
    chave: "nav.grupos.estudar", icone: GraduationCap, to: "/study",
    acende: ["/study", "/academy", "/docs"],
    secoes: SECOES_ESTUDAR, itens: _itens(SECOES_ESTUDAR),
  },
  {
    chave: "nav.grupos.comunidade", icone: Medal, to: "/leaderboard",
    acende: ["/leaderboard", "/coaches", "/maos"],
    secoes: SECOES_COMUNIDADE, itens: _itens(SECOES_COMUNIDADE),
  },
];

/** O AI Coach fica fora dos grupos: é uma conversa, não uma seção. (A barra mobile ainda usa.) */
export const ITEM_COACH: ItemDeMenu = {
  to: "/coach", chave: "nav.coach", desc: "nav.desc.coach", icone: Bot, exige: "ai_coach_chat",
};

/** O AI Coach como GRUPO (30/08, pedido do dono): a conversa + os RELATÓRIOS que a IA gera do
 *  jogador. Os relatórios são cards do dashboard — o link é âncora (#twin etc.), e o Index
 *  rola até o card quando ele existir. */
export const GRUPO_COACH: GrupoDeMenu = {
  chave: "nav.coach", icone: Bot, to: "/coach",
  acende: ["/coach"],
  secoes: [
    { chave: "nav.secoes.conversa", itens: [ITEM_COACH] },
    { chave: "nav.secoes.relatorios", itens: [
      { to: "/dashboard#twin", chave: "nav.relTwin", desc: "nav.desc.relTwin",
        icone: TrendingUp, cor: "teal", exige: "advanced_insights" },
      { to: "/dashboard#cognitive", chave: "nav.relCognitivo", desc: "nav.desc.relCognitivo",
        icone: Crosshair, cor: "red", exige: "advanced_insights" },
      { to: "/dashboard#causal_map", chave: "nav.relCausal", desc: "nav.desc.relCausal",
        icone: Grid3x3, cor: "purple", exige: "advanced_insights" },
      { to: "/dashboard#career", chave: "nav.relCarreira", desc: "nav.desc.relCarreira",
        icone: Medal, cor: "amber", exige: "advanced_insights" },
    ]},
  ],
  itens: [],
};
GRUPO_COACH.itens = GRUPO_COACH.secoes.flatMap((sec) => sec.itens);
