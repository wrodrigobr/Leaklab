import type { PracticeGrade, PracticeOption } from "@/lib/api";

/**
 * As regras do modo Prática que não são desenho de tela.
 *
 * Elas moram aqui porque a página tem quatro mesas, rede em toda rodada e teclado global, e é o
 * tipo de componente que ninguém consegue montar num teste. O que decide o resultado do treino
 * (o que a tecla faz, quando a configuração entra, como o placar soma) fica fora dela e coberto.
 */

/** As faixas que o acervo cobre: 3 a 100bb em 14 baldes, e estas são as que o treino oferece. */
export const STACKS_DISPONIVEIS = [10, 14, 17, 20, 30, 40, 50, 75, 100] as const;

export const MAX_MESAS = 4;

export type Pausa = "nunca" | "erro" | "acao";

/** Em que unidade a mesa mostra stack e apostas. */
export type Unidade = "bb" | "fichas";

export interface ConfigPratica {
  mesas: number;
  stacks: number[];
  /** "mixed" | "rfi" | "vs_rfi" | "vs_3bet" — o mesmo vocabulário do servidor */
  cenario: string;
  pausa: Pausa;
  /** BB ou fichas na mesa. A casa tem a cicatriz mais recorrente do projeto justamente aqui
   *  ("Fichas vs BB"), e a régua do produto é BB: o solver, os leaks, o EV e o ELO todos falam
   *  em BB, e uma mesa em fichas obrigaria o jogador a converter de cabeça para ligar o que vê
   *  na mesa ao que lê no veredito. Fichas fica disponível para quem quer o visual da sala. */
  unidade: Unidade;
}

export const CONFIG_PADRAO: ConfigPratica = {
  mesas: 4,
  // O MTT curto é o ponto do treino, e é a faixa que a Academia não cobre de propósito.
  stacks: [10, 14, 17, 20],
  cenario: "mixed",
  // "nunca" e o padrao (decisao do dono, 16/09): ele viu o botao "continuar" aparecer depois de
  // algumas rodadas e pediu fluxo continuo -- "a cada nova acao escolhida, cada uma das mesas
  // puxe um novo spot". Com "erro", a mesa que ele errava ficava esperando um clique, e o grind
  // parava justamente onde o jogador estava engajado.
  //
  // As outras duas seguem no painel para quem QUER parar: "erro" e o modo de estudo (segura no
  // erro para ler o veredito com calma) e "acao" e o passo a passo.
  pausa: "nunca",
  unidade: "bb",
};

/**
 * Se a configuração nova muda o SORTEIO. `pausa` e `unidade` não mudam: uma decide quando a tela
 * espera o jogador e a outra só como o número é escrito, então aplicam na hora. Mesas, stacks e
 * cenário mudam o que é sorteado, e por isso valem do próximo spot em diante.
 *
 * Essa distinção é o conserto do que o GTO Wizard faz: lá, trocar o número de mesas reinicia a
 * sessão e descarta as respostas que o jogador já deu.
 */
export function mudaOSorteio(a: ConfigPratica, b: ConfigPratica): boolean {
  return a.mesas !== b.mesas
    || a.cenario !== b.cenario
    || a.stacks.length !== b.stacks.length
    || a.stacks.some((s, i) => s !== b.stacks[i]);
}

/**
 * A tecla vira ação, dentro das opções QUE AQUELA MESA OFERECE.
 *
 * Nunca de uma tabela fixa: o menu de ações vem do StrategyProvider e varia por spot (a 12bb há
 * all-in, a 100bb não; no RFI do SB existe o limp). Uma tabela fixa aqui faria `A` mandar all-in
 * numa mesa que não tem all-in, e o servidor recusaria a resposta sem o jogador entender.
 */
export function acaoDaTecla(tecla: string, opcoes: PracticeOption[]): string | null {
  const k = (tecla || "").toLowerCase();
  const alvo: Record<string, string[]> = {
    f: ["fold"],
    c: ["call", "check"],
    r: ["raise", "bet"],
    a: ["allin", "jam", "shove"],
  };
  const querem = alvo[k];
  if (!querem) return null;
  const achada = opcoes.find((o) => querem.includes((o.action || "").toLowerCase()));
  return achada ? achada.action : null;
}

/**
 * A próxima mesa a receber o foco: a de menor índice ainda SEM resposta, girando a partir da
 * atual. Devolve `-1` quando todas já responderam, que é o sinal de fim de rodada.
 *
 * Girar a partir da atual, e não varrer do zero, é o que faz o `Tab` avançar em vez de voltar
 * sempre para a primeira pendente.
 */
export function proximoFoco(atual: number, total: number, respondidas: Set<number>): number {
  for (let passo = 1; passo <= total; passo++) {
    const i = (atual + passo) % total;
    if (!respondidas.has(i)) return i;
  }
  return -1;
}

export type Nivel = "melhor" | "correta" | "imprecisao" | "errada" | "grave";

/** A ordem em que o placar mostra, do melhor para o pior. */
export const NIVEIS: Nivel[] = ["melhor", "correta", "imprecisao", "errada", "grave"];

/**
 * Os cinco níveis, derivados do veredito do servidor.
 *
 * Quatro deles vêm direto do `action_quality` da carta. O quinto, "melhor jogada", precisa de
 * comparação: é o `correct` cuja ação escolhida É a de maior frequência no spot. Sem `hand_freq`
 * não há como distinguir, e aí `correct` fica em "correta" -- nunca promovido a "melhor" por
 * otimismo, que seria inflar o placar do jogador com o que não se mediu.
 */
export function nivelDoGrade(g: PracticeGrade | null | undefined, acao: string): Nivel {
  const q = String(g?.action_quality || "").toLowerCase();
  if (q === "major_leak") return "grave";
  if (q === "leak") return "errada";
  if (q === "acceptable") return "imprecisao";
  if (q !== "correct") {
    // Sem qualidade legível não há veredito. `is_correct` sozinho é o que o endpoint devolve
    // quando não houve carta, e a régua da casa manda calar em vez de afirmar.
    return g?.is_correct ? "correta" : "errada";
  }
  const freq = g?.hand_freq || null;
  if (!freq) return "correta";
  const entradas = Object.entries(freq).filter(([, v]) => typeof v === "number");
  if (!entradas.length) return "correta";
  const maior = entradas.reduce((a, b) => (b[1] > a[1] ? b : a));
  return normalizaAcao(maior[0]) === normalizaAcao(acao) ? "melhor" : "correta";
}

/** `F`, `R2.5`, `allin`, `jam` viram um vocabulário só, porque o `hand_freq` usa o código do nó
 *  do solver e as opções usam o nome da ação. Comparar cru daria "melhor jogada" nunca. */
export function normalizaAcao(a: string): string {
  const s = String(a || "").trim().toLowerCase();
  if (!s) return "";
  if (s === "f" || s.startsWith("fold")) return "fold";
  if (s === "c" || s.startsWith("call")) return "call";
  if (s === "x" || s.startsWith("check")) return "check";
  if (s === "rai" || s === "allin" || s === "jam" || s === "shove") return "allin";
  if (s.startsWith("r") || s.startsWith("bet") || s.startsWith("raise")) return "raise";
  return s;
}

export interface StatsPratica {
  maos: number;
  acertos: number;
  bbPerdidos: number;
  porNivel: Record<Nivel, number>;
}

export const STATS_ZERO: StatsPratica = {
  maos: 0, acertos: 0, bbPerdidos: 0,
  porNivel: { melhor: 0, correta: 0, imprecisao: 0, errada: 0, grave: 0 },
};

/**
 * Soma uma resposta ao placar da sessão.
 *
 * "Acerto" é `melhor` ou `correta`, e não `is_correct`: o endpoint chama `acceptable` de correto
 * para efeito de XP, e contar imprecisão como acerto faria o percentual da sessão dizer que o
 * jogador vai melhor do que vai.
 */
export function acumula(s: StatsPratica, g: PracticeGrade | null | undefined, acao: string): StatsPratica {
  const n = nivelDoGrade(g, acao);
  const perdeu = typeof g?.ev_loss_bb === "number" ? Math.abs(g.ev_loss_bb) : 0;
  return {
    maos: s.maos + 1,
    acertos: s.acertos + (n === "melhor" || n === "correta" ? 1 : 0),
    bbPerdidos: Math.round((s.bbPerdidos + perdeu) * 100) / 100,
    porNivel: { ...s.porNivel, [n]: s.porNivel[n] + 1 },
  };
}

/** Se a tela deve ESPERAR o jogador depois desta resposta, conforme o "pausar depois de". */
export function devePausar(pausa: Pausa, nivel: Nivel): boolean {
  if (pausa === "acao") return true;
  if (pausa === "erro") return nivel === "errada" || nivel === "grave";
  return false;
}
