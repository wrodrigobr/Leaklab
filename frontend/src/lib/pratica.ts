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

/**
 * Quantas mesas a tela AGUENTA, pela largura dela em px.
 *
 * ── O pedido (17/09) ──────────────────────────────────────────────────────────────────────────
 *
 * O dono, depois de abrir o Pratica no celular: "No celular vamos ficar apenas 1 mesa, e garantir
 * que o menu de configuracao apareca, hoje isto nao esta acontecendo. Nao permitir aumentar o
 * numero de mesas em telas pequenas".
 *
 * ── Por que a regra e por LARGURA, e nao por "e celular?" ─────────────────────────────────────
 *
 * Nenhum teste de user-agent: o que decide e o espaco, e o espaco muda com o celular girando, com
 * a janela do desktop pela metade e com o tablet em qualquer orientacao. Detectar aparelho erra
 * nos tres casos, e erra calado.
 *
 * O corte e 1024px porque e o MESMO `lg` do Tailwind que o painel de configuracao usa para virar
 * coluna: abaixo dele o painel e uma gaveta sobre as mesas, e duas mesas mais uma gaveta nao
 * cabem. Um degrau intermediario (duas mesas no tablet) fica para quando alguem pedir -- inventar
 * agora seria mais uma faixa para testar sem ninguem tendo reclamado dela.
 */
export const LARGURA_PARA_VARIAS_MESAS = 1024;

/**
 * O card mínimo em que a mesa CABE, medido com o medidor de colisão da geometria.
 *
 * ── Por que a ALTURA entra na conta (17/09) ───────────────────────────────────────────────────
 *
 * O dono reduziu a altura da janela com quatro mesas abertas e mandou a captura: as mesas viraram
 * fitas horizontais. O aspecto com faixa impede a deformação, mas não cria espaço -- com 200px de
 * altura por card, a mesa fica com 86x36 e nada cabe nela.
 *
 * Medido, varrendo as 81 mãos: card de 300px de altura passa com ZERO sobreposições, 250px dá 648
 * e 200px dá 4.824. Então o teto passou a olhar a altura: se não cabem quatro mesas, o Prática
 * abre duas; se não cabem duas, abre uma. É o que o GTO Wizard faz -- a captura dele numa janela
 * estreita mostra UMA mesa, vertical.
 */
export const MESA_MINIMA = { largura: 360, altura: 300 };

/**
 * A altura que sobra para a MESA de cada card, dada a janela e o número de linhas.
 *
 * Os descontos são o layout real, medido na tela e não estimado: 48px da barra do topo, 8px do
 * espaçamento da grade, e 78px que o card gasta acima e abaixo da mesa (o cabeçalho com a mão e o
 * stack, mais a linha de botões, que agora tem 44px de altura mínima).
 */
function alturaDaMesa(alturaDaTela: number, linhas: number): number {
  return (alturaDaTela - 48) / linhas - 8 - 78;
}

export function tetoDeMesas(larguraDaTela: number, alturaDaTela = 900): number {
  if (larguraDaTela < LARGURA_PARA_VARIAS_MESAS) return 1;
  const caberiaNaLargura = larguraDaTela / 2 >= MESA_MINIMA.largura;
  if (caberiaNaLargura && alturaDaMesa(alturaDaTela, 2) >= MESA_MINIMA.altura) return MAX_MESAS;
  if (caberiaNaLargura && alturaDaMesa(alturaDaTela, 1) >= MESA_MINIMA.altura) return 2;
  return 1;
}

/** A configuracao que VALE nesta tela: o que ele escolheu, aparado pelo que cabe.
 *
 *  Aparar em vez de reescrever a escolha dele e deliberado: quem configurou quatro mesas no
 *  desktop e abriu no celular nao perde a preferencia -- ela volta a valer quando a tela crescer.
 */
export function configNaTela(c: ConfigPratica, larguraDaTela: number,
                             alturaDaTela = 900): ConfigPratica {
  const teto = tetoDeMesas(larguraDaTela, alturaDaTela);
  return c.mesas <= teto ? c : { ...c, mesas: teto };
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
/**
 * O corte de "custa pouco", em bb. Vale SO quando o nó não tem estratégia nenhuma (`hand_freq`
 * vazio): com estratégia, quem decide o lado é a frequência, e o custo só separa errada de grave.
 */
export const CUSTO_DA_IMPRECISAO = 0.5;
/**
 * Abaixo deste custo, em bb, uma jogada que o GTO NAO faz ainda nao e erro.
 *
 * ── Por que um piso existe, e por que ele e 0,005 ─────────────────────────────────────────────
 *
 * A regua diz que frequencia zero e o lado ruim ("totalmente fora", na descricao do dono). Sem
 * piso, ela chamaria de errada uma jogada que custa 0,001bb -- medido: `HJ Q5s 50bb` abrindo
 * custa exatamente isso pela carta de EV. Chamar 0,001bb de erro e preciosismo, e ensina o
 * jogador a desconfiar do veredito quando ele mais precisa confiar.
 *
 * O numero nao e gosto: a tela mostra o custo com DUAS casas, entao tudo abaixo de 0,005 aparece
 * como "-0,00bb". Chamar de erro um numero que a propria tela exibe como zero e contradicao na
 * mesma linha. Acima disso o numero existe na tela, e o veredito pode falar dele.
 *
 * A primeira tentativa foi 0,05, e o proprio teste do caso do dono a derrubou: o limp dele custa
 * 0,028bb, ou seja o piso engoliria justamente o lance que originou a queixa.
 */
export const PISO_DE_RUIDO_BB = 0.005;

/**
 * Abaixo desta frequencia, "o GTO faz" nao e verdade: e ruido da carta.
 *
 * ── Como este furo apareceu ───────────────────────────────────────────────────────────────────
 *
 * Medindo o acervo para saber se existia dado contraditorio (frequencia positiva com custo alto),
 * o medidor imprimiu um caso com custo de 2,552bb e frequencia `0.0` -- dentro de um filtro que
 * exigia `> 0`. Nao era bug do medidor: a frequencia era 0,4%, que arredonda para zero na
 * impressao. Sem piso, a regra "o GTO faz, mas pouco -> aceitavel" absolveria uma perna que o
 * solver joga 0,4% do tempo e que custa 2,5bb.
 *
 * 1% e o MESMO numero que o card ja usa para listar as outras pernas da mistura: uma perna que
 * nao aparece na tela nao pode ser a justificativa de um veredito na mesma tela.
 */
export const FREQ_MINIMA_PARA_EXISTIR = 0.01;

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
/**
 * O nivel de uma resposta, ou `null` quando nao ha base para julgar.
 *
 * ── Por que `null` existe ─────────────────────────────────────────────────────────────────────
 *
 * O dono viu o veredito "errada" piscar antes do veredito real. A causa: enquanto a resposta do
 * servidor nao chega, a mesa chamava esta funcao com `grade` nulo, e a ultima linha chutava
 * `is_correct ? correta : errada` -- ou seja ERRADA, sempre. O flash era o sintoma barato; o caro
 * e que uma falha do `/grade` deixava a acusacao inventada PARADA na tela.
 *
 * Nao ha veredito sem dado. Quem chama decide o que dizer no lugar ("avaliando", "sem
 * avaliacao"), e nenhuma das duas e uma acusacao.
 */
/**
 * O nivel que o SERVIDOR deu a esta resposta, ou `null` quando ele nao julgou.
 *
 * ── Por que aqui nao ha regua nenhuma ─────────────────────────────────────────────────────────
 *
 * Ela existia neste arquivo, com os cortes de frequencia e de custo, e funcionou enquanto o
 * Pratica so PINTAVA o veredito. O historico das maos praticadas mudou o problema: o servidor
 * passou a GRAVAR o veredito, e manter a conta aqui tambem criaria duas implementacoes da mesma
 * regra -- a regra 5 da casa, e o defeito que este modo acabou de pagar em outra dimensao (o
 * motor chamando `major_leak` o que o Pratica chamava de "aceitavel", em 36,5% das combinacoes).
 *
 * A regua mora em `backend/leaklab/pratica_preflop.nivel_do_veredito`, com os casos dela em
 * `backend/tests/test_pratica_preflop.py`. Aqui so se LE.
 *
 * `null` acontece em dois casos, e nenhum deles e acusacao: o servidor nao teve base para julgar,
 * ou a resposta ainda nao voltou. A mesa diz "sem avaliacao" e "avaliando", respectivamente.
 */
export function nivelDoGrade(g: PracticeGrade | null | undefined, _acao?: string): Nivel | null {
  const n = g?.nivel;
  return n && NIVEIS.includes(n as Nivel) ? (n as Nivel) : null;
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
  // Sem veredito ela nao entra: contar como erro seria a invencao que este conserto tirou da
  // tela, e contar como acerto seria o oposto. A mao fica fora, e a mesa diz que ficou.
  if (n == null) return s;
  const perdeu = typeof g?.ev_loss_bb === "number" ? Math.abs(g.ev_loss_bb) : 0;
  return {
    maos: s.maos + 1,
    acertos: s.acertos + (n === "correta" ? 1 : 0),
    bbPerdidos: Math.round((s.bbPerdidos + perdeu) * 100) / 100,
    porNivel: { ...s.porNivel, [n]: s.porNivel[n] + 1 },
  };
}

/** Se a tela deve ESPERAR o jogador depois desta resposta, conforme o "pausar depois de". */
export function devePausar(pausa: Pausa, nivel: Nivel | null): boolean {
  if (pausa === "acao") return true;
  if (pausa === "erro") return nivel === "errada" || nivel === "grave";
  return false;
}
