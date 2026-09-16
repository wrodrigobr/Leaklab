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

/**
 * Os QUATRO niveis do veredito.
 *
 * Eram cinco, com "melhor jogada" separada de "correta", e o dono fundiu as duas: "melhor jogada
 * e correta, pra mim sao a mesma coisa".
 *
 * A medicao explica por que a distincao rendia tao pouco: **83,7% dos spots preflop do acervo sao
 * PUROS** (uma acao em 100%), e so 5,7% tem uma segunda perna com 30% ou mais. Separar "acertou a
 * de maior frequencia" de "pegou uma perna da mistura" so dizia algo em 5,7% dos casos, e nos
 * outros 94% os dois niveis descreviam a mesma coisa com dois nomes.
 */
/**
 * O identificador de cada nível. O RÓTULO que o jogador lê vem do i18n (`nivel.*`).
 *
 * Os rótulos passaram por "boa" e voltaram para **correta** e **aceitável** (decisão do dono),
 * e a volta foi boa por um motivo além do gosto: eles agora batem com o `action_quality` que o
 * servidor já usa (`correct`, `acceptable`, `leak`, `major_leak`). Um vocabulário só entre a
 * tela e o motor é menos uma tradução para alguém errar depois.
 */
export type Nivel = "correta" | "imprecisao" | "errada" | "grave";

/** A ordem em que o placar mostra, do melhor para o pior. */
export const NIVEIS: Nivel[] = ["correta", "imprecisao", "errada", "grave"];

/**
 * O SÍMBOLO de cada nível, numa escala de quatro degraus.
 *
 * Pedido do dono: "acho que o gto wizard classifica como VV, V, X, XX" -- e é isso mesmo, a
 * captura deles mostra "✓✓ MELHOR ESCOLHA" e o painel usa a mesma escala.
 *
 * O símbolo faz o que a palavra não faz: ele ordena. "imprecisão" e "errada" são dois
 * substantivos que o jogador precisa saber qual é pior; `✓` e `✗` dizem de que lado cada uma
 * está, e o dobro diz a intensidade. A palavra fica ao lado, porque ela é que nomeia.
 *
 * Fonte única: o card do centro e o placar da sessão leem daqui, senão seriam duas escalas.
 */
export const SIMBOLO_DO_NIVEL: Record<Nivel, string> = {
  correta:    "✓✓",
  imprecisao: "✓",
  errada:     "✗",
  grave:      "✗✗",
};

/** A frequência mínima para o GTO estar MISTURANDO a ação de verdade, e não fazendo por exceção. */
export const FREQ_DA_MISTURA = 0.3;

/** Os cortes de CUSTO, em bb, que separam imprecisão de erro e de erro grave.
 *
 *  Calibrados nos números reais do acervo, medidos em 16/09 no BTN a 20bb: `raise` com 75o custa
 *  **0,15bb**, `fold` com KQs custa **1,70bb** e `fold` com AA custa **9,21bb**. Os três eram
 *  `major_leak` no vocabulário da carta -- sessenta vezes de diferença no mesmo rótulo. */
export const CUSTO_DA_IMPRECISAO = 0.5;
export const CUSTO_DO_ERRO_GRAVE = 3;

/**
 * Os quatro níveis: a FREQUÊNCIA decide o lado bom, o CUSTO decide a severidade.
 *
 * ── Por que os dois, e não um só ──────────────────────────────────────────────────────────────
 *
 * O dono, vendo o placar com tudo em "melhor jogada" ou "erro grave": "precisamos pensar em como
 * classificar as jogadas de acordo com os levels que definimos".
 *
 * **Frequência sozinha não separa o que importa.** `raise` com 75o e `fold` com AA têm ambos 0%
 * de frequência -- os dois são "totalmente fora" -- e custam 0,15bb e 9,21bb. Uma régua só de
 * frequência é obrigada a dar o mesmo nível aos dois, que foi exatamente o defeito.
 *
 * **Custo sozinho também não basta.** Num spot que o GTO mistura 50/50, escolher a perna menor
 * custa quase nada, mas é informação diferente de ter acertado a de maior frequência.
 *
 * Então cada um no seu papel, e é o que o GTO Wizard faz: a "pontuação GTOW" deles é frequência,
 * e o painel de stats mostra "total de erros EV" e "média de EV perdida", que é custo.
 *
 * ── A ordem de avaliação, que é o que faz a régua funcionar ───────────────────────────────────
 *
 * 1. O GTO faz essa ação com peso -- a de maior frequência, ou uma perna de >= 30%? CORRETA.
 * 2. Está fora: o CUSTO decide. Abaixo de 0,5bb é imprecisão, até 3bb é errada, acima é grave.
 *
 * Sem custo medido (spot sem carta), o passo 3 cai no `action_quality` da carta -- é menos
 * preciso, e a alternativa seria inventar severidade onde não houve medida.
 */
export function nivelDoGrade(g: PracticeGrade | null | undefined, acao: string): Nivel {
  const freq = g?.hand_freq || null;
  const entradas = freq
    ? Object.entries(freq).filter(([, v]) => typeof v === "number")
    : [];

  // ── 1: o lado bom, pela frequência ──────────────────────────────────────────────────────
  // Acertar a ação de maior frequência e pegar uma perna que o GTO mistura com peso real são o
  // MESMO nível, por decisão do dono. O que separa "correta" de "imprecisão" é o GTO fazer
  // aquilo com peso, e não qual das pernas ele faz mais.
  if (entradas.length) {
    const maior = entradas.reduce((a, b) => (b[1] > a[1] ? b : a));
    const daEscolhida = entradas.find(([a]) => normalizaAcao(a) === normalizaAcao(acao));
    const pct = daEscolhida ? daEscolhida[1] : 0;
    if (pct > 0 && (pct >= maior[1] || pct >= FREQ_DA_MISTURA)) return "correta";
  }

  // ── 3: está fora da mistura, e o CUSTO decide a severidade ──────────────────────────────
  const custo = typeof g?.ev_loss_bb === "number" ? Math.abs(g.ev_loss_bb) : null;
  if (custo != null) {
    if (custo < CUSTO_DA_IMPRECISAO) return "imprecisao";
    if (custo <= CUSTO_DO_ERRO_GRAVE) return "errada";
    return "grave";
  }

  // ── sem custo medido: o vocabulário da carta, que é o que há ─────────────────────────────
  const q = String(g?.action_quality || "").toLowerCase();
  if (q === "major_leak") return "grave";
  if (q === "leak") return "errada";
  if (q === "acceptable") return "imprecisao";
  if (q === "correct") return "correta";
  // Sem qualidade legível não há veredito. `is_correct` sozinho é o que o endpoint devolve
  // quando não houve carta, e a régua da casa manda calar em vez de afirmar.
  return g?.is_correct ? "correta" : "errada";
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
  porNivel: { correta: 0, imprecisao: 0, errada: 0, grave: 0 },
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
    acertos: s.acertos + (n === "correta" ? 1 : 0),
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
