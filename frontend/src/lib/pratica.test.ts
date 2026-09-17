import { describe, it, expect } from "vitest";
import {
  CONFIG_PADRAO, MAX_MESAS, acaoDaTecla, acumula, devePausar, mudaOSorteio,
  nivelDoGrade, normalizaAcao, proximoFoco, NIVEIS, SIMBOLO_DO_NIVEL, STATS_ZERO,
  type ConfigPratica,
} from "./pratica";

/**
 * As regras do modo Prática. Cada bloco guarda uma decisão que, invertida, estraga o treino de um
 * jeito que a tela não denuncia: o placar dizendo que o jogador vai melhor do que vai, a tecla
 * mandando uma ação que o spot não tem, a configuração descartando respostas já dadas.
 */

const cfg = (over: Partial<ConfigPratica> = {}): ConfigPratica => ({ ...CONFIG_PADRAO, ...over });
const opcoes = (...acts: string[]) => acts.map((a) => ({ action: a, label: a }));

describe("configuração", () => {
  it("mexer no SORTEIO espera a próxima rodada; mexer na pausa não", () => {
    // O conserto do que o GTO Wizard faz: lá, trocar o número de mesas reinicia a sessão e
    // descarta o que o jogador já respondeu.
    expect(mudaOSorteio(cfg(), cfg({ mesas: 2 }))).toBe(true);
    expect(mudaOSorteio(cfg(), cfg({ cenario: "rfi" }))).toBe(true);
    expect(mudaOSorteio(cfg(), cfg({ stacks: [10, 14] }))).toBe(true);
    // mesma lista, outra ordem de digitação do usuário, mesmo sorteio
    expect(mudaOSorteio(cfg({ stacks: [10, 14] }), cfg({ stacks: [10, 14] }))).toBe(false);
    // a pausa só decide quando a tela espera: aplica na hora
    expect(mudaOSorteio(cfg({ pausa: "erro" }), cfg({ pausa: "nunca" }))).toBe(false);
  });

  it("o padrão abre na faixa curta, que é onde vive o MTT", () => {
    expect(CONFIG_PADRAO.mesas).toBe(MAX_MESAS);
    expect(Math.max(...CONFIG_PADRAO.stacks)).toBeLessThanOrEqual(20);
  });
});

describe("teclado", () => {
  it("a tecla vira ação DENTRO do que a mesa oferece", () => {
    expect(acaoDaTecla("f", opcoes("fold", "call", "allin"))).toBe("fold");
    expect(acaoDaTecla("C", opcoes("fold", "call"))).toBe("call");
    expect(acaoDaTecla("a", opcoes("fold", "call", "allin"))).toBe("allin");
    // `c` também serve o check, porque o menu do spot pode ter check e não call
    expect(acaoDaTecla("c", opcoes("fold", "check"))).toBe("check");
    expect(acaoDaTecla("r", opcoes("fold", "raise"))).toBe("raise");
  });

  it("tecla sem ação NAQUELE spot não faz nada", () => {
    // O defeito que isto impede: a 100bb não há all-in no menu, e uma tabela fixa mandaria
    // `allin` para o servidor, que recusaria sem o jogador entender por quê.
    expect(acaoDaTecla("a", opcoes("fold", "call", "raise"))).toBeNull();
    expect(acaoDaTecla("z", opcoes("fold", "call"))).toBeNull();
    expect(acaoDaTecla("", opcoes("fold"))).toBeNull();
  });
});

describe("foco", () => {
  it("gira a partir da atual, e não volta sempre para a primeira", () => {
    // 4 mesas, a 0 e a 2 já respondidas, foco na 0: o Tab tem de ir para a 1
    expect(proximoFoco(0, 4, new Set([0, 2]))).toBe(1);
    // foco na 1 (pendente), respondidas 0 e 2: a próxima pendente girando é a 3
    expect(proximoFoco(1, 4, new Set([0, 2]))).toBe(3);
    // da 3 ele dá a volta e acha a 1
    expect(proximoFoco(3, 4, new Set([0, 2]))).toBe(1);
  });

  it("todas respondidas devolve -1, que é o fim da rodada", () => {
    expect(proximoFoco(2, 4, new Set([0, 1, 2, 3]))).toBe(-1);
    expect(proximoFoco(0, 1, new Set([0]))).toBe(-1);
  });
});

describe("os cinco níveis", () => {
  /** Os TRÊS casos reais que motivaram a régua, medidos no acervo em 16/09 (BTN, 20bb, RFI).
   *  Os três eram `major_leak` no vocabulário da carta, com custo variando sessenta vezes. */
  const FORA = { freq: { fold: 1, raise: 0, call: 0, allin: 0 }, acao: "raise" };
  const raise75o = { is_correct: false, action_quality: "major_leak",
                     hand_freq: FORA.freq, ev_loss_bb: 0.148 };
  const foldKQs  = { is_correct: false, action_quality: "major_leak",
                     hand_freq: { fold: 0, raise: 1, call: 0, allin: 0 }, ev_loss_bb: 1.696 };
  const foldAA   = { is_correct: false, action_quality: "major_leak",
                     hand_freq: { fold: 0, raise: 1, call: 0, allin: 0 }, ev_loss_bb: 9.208 };

  it("o CUSTO separa o que o action_quality achatava", () => {
    // O defeito que o dono viu: os tres abaixo recebiam o MESMO "erro grave", e a diferenca de
    // custo entre o primeiro e o ultimo e de sessenta vezes. A frequencia nao podia separa-los
    // (todos tem 0%), e por isso a severidade passou a vir do custo.
    // ATUALIZADO em 16/09, quando a frequencia passou a decidir o LADO: os tres tem 0% de
    // frequencia, entao os tres estao no lado ruim, e o custo separa errada de grave. O primeiro
    // saiu de "aceitavel" para "errada" -- e e isto que o dono pediu ao ver "0%" com selo de
    // endosso.
    //
    // O pedido antigo dele ("o custo separa") nao foi perdido: os tres continuam distinguiveis na
    // tela, que mostra -0,15bb, -1,70bb e -9,21bb ao lado do rotulo. O rotulo da o lado e a ordem
    // de grandeza; o numero da o detalhe fino, e com quatro niveis nao cabem tres faixas de custo
    // dentro do lado ruim (o dono cortou o quinto nivel de proposito).
    expect(nivelDoGrade(raise75o, "raise")).toBe("errada");       // 0,15bb
    expect(nivelDoGrade(foldKQs, "fold")).toBe("errada");         // 1,70bb
    expect(nivelDoGrade(foldAA, "fold")).toBe("grave");           // 9,21bb
  });

  it("os cortes de custo, nos limites exatos", () => {
    // Com estrategia no nó, o corte de 0,5 NAO separa nada: a frequencia zero ja pos a jogada no
    // lado ruim, e dentro dele so existe a fronteira de 3bb (errada/grave) e o piso de ruido.
    // O corte de 0,5 continua valendo onde nao ha estrategia nenhuma, no caso abaixo.
    const fora = { is_correct: false, hand_freq: { fold: 1, raise: 0 } };
    expect(nivelDoGrade({ ...fora, ev_loss_bb: 0.49 }, "raise")).toBe("errada");
    expect(nivelDoGrade({ ...fora, ev_loss_bb: 0.5 }, "raise")).toBe("errada");
    expect(nivelDoGrade({ ...fora, ev_loss_bb: 3 }, "raise")).toBe("errada");
    expect(nivelDoGrade({ ...fora, ev_loss_bb: 3.01 }, "raise")).toBe("grave");
    // o sinal do ev_loss varia por superficie no produto: o que decide e o TAMANHO
    expect(nivelDoGrade({ ...fora, ev_loss_bb: -9 }, "raise")).toBe("grave");
  });

  it("SEM custo medido, cai no vocabulário da carta", () => {
    // Menos preciso, e declarado: a alternativa seria inventar severidade onde nao houve medida.
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct" }, "fold")).toBe("correta");
    expect(nivelDoGrade({ is_correct: true, action_quality: "acceptable" }, "call")).toBe("imprecisao");
    expect(nivelDoGrade({ is_correct: false, action_quality: "leak" }, "call")).toBe("errada");
    expect(nivelDoGrade({ is_correct: false, action_quality: "major_leak" }, "call")).toBe("grave");
  });

  it("acertar o que o GTO faz com peso e UM nivel, e nao dois", () => {
    // O dono fundiu "melhor jogada" e "correta": "pra mim sao a mesma coisa". A medicao explica
    // por que a distincao rendia pouco -- 83,7% dos spots preflop do acervo sao PUROS, e a
    // separacao so dizia algo em 5,7% deles.
    const freq = { F: 0.72, R2: 0.28 };
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: freq }, "fold"))
      .toBe("correta");
    // Escolheu a perna menor (28%, logo abaixo do corte de 30%): o GTO FAZ, mas pouco, e isso e
    // "aceitavel". Antes de 16/09 esta linha esperava "correta", porque sem custo o veredito caia
    // no `action_quality` da carta (que diz `correct` para o NÓ, nao para a perna escolhida) --
    // um fallback ganhando de um dado que existia.
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: freq }, "raise"))
      .toBe("imprecisao");
    // COM o custo medido, a mesma jogada e classificada pelo que ela custou
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: freq,
                          ev_loss_bb: 0.2 }, "raise")).toBe("imprecisao");
    // Frequencia de 28% COM custo de 4,5bb nao existe no acervo: medido em 1.642 combinacoes com
    // frequencia positiva e custo medido, o maior custo e 2,552bb -- e esse caso tem 0,4% de
    // frequencia, ou seja cai no piso e nem conta como "o GTO faz". Num dado assim, contraditorio
    // consigo mesmo, manda a frequencia (decisao do dono: ela decide o LADO) e o custo aparece na
    // tela ao lado do rotulo.
    expect(nivelDoGrade({ is_correct: false, action_quality: "leak", hand_freq: freq,
                          ev_loss_bb: 4.5 }, "raise")).toBe("imprecisao");
  });

  it("num 50/50 as DUAS pernas contam como boa", () => {
    // Empate na maior frequencia: penalizar uma delas seria inventar uma preferencia que o
    // solver nao tem.
    const meioAMeio = { F: 0.5, R2: 0.5 };
    expect(nivelDoGrade({ hand_freq: meioAMeio, is_correct: true }, "fold")).toBe("correta");
    expect(nivelDoGrade({ hand_freq: meioAMeio, is_correct: true }, "raise")).toBe("correta");
  });

  it("a mistura com peso real conta como CORRETA", () => {
    const freq = { F: 0.6, R2: 0.4 };
    expect(nivelDoGrade({ hand_freq: freq, is_correct: true }, "raise")).toBe("correta");
    // e logo abaixo do corte deixa de ser: 29% e excecao, nao mistura
    expect(nivelDoGrade({ hand_freq: { F: 0.71, R2: 0.29 }, is_correct: true, ev_loss_bb: 0.2 },
                        "raise")).toBe("imprecisao");
  });

  it("sem hand_freq nao ha o que comparar, e o quality manda", () => {
    // Promover por otimismo infla o placar com o que nao se mediu.
    // Promover por otimismo infla o placar com o que não se mediu, que é a versão do
    // "zero tranquilizador" para o lado bom do número.
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct" }, "fold")).toBe("correta");
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: {} }, "fold"))
      .toBe("correta");
  });

  it("sem veredito nenhum, CALA: `is_correct` sozinho nao julga", () => {
    // Este caso existia ao contrario, exigindo "correta"/"errada" a partir do `is_correct` cru --
    // e foi ele que manteve de pe o defeito que o dono viu piscar na tela. `is_correct` sozinho e
    // o que o endpoint devolve quando NAO houve carta nenhuma: julgar por ele e afirmar sem base.
    //
    // A regra 2 da casa em acao: teste que congela comportamento errado conta como cobertura sem
    // dar cobertura.
    expect(nivelDoGrade({ is_correct: true }, "fold")).toBeNull();
    expect(nivelDoGrade({ is_correct: false }, "fold")).toBeNull();
    expect(nivelDoGrade(null, "fold")).toBeNull();
  });

  it("o codigo do nó e o nome da ação falam o mesmo idioma", () => {
    // `hand_freq` vem com o código do nó do solver (`F`, `R2.5`, `RAI`) e as opções vêm com o
    // nome da ação. Comparar cru daria "melhor jogada" nunca.
    expect(normalizaAcao("F")).toBe("fold");
    expect(normalizaAcao("R2.5")).toBe("raise");
    expect(normalizaAcao("RAI")).toBe("allin");
    expect(normalizaAcao("jam")).toBe("allin");
    expect(normalizaAcao("shove")).toBe("allin");
    expect(normalizaAcao("C")).toBe("call");
    expect(normalizaAcao("X")).toBe("check");
  });
});

describe("a escala de simbolos", () => {
  it("ordena os quatro niveis, e o dobro diz a intensidade", () => {
    // Pedido do dono ("VV, V, X, XX"): o simbolo faz o que a palavra nao faz, que e ORDENAR.
    // "imprecisao" e "errada" sao dois substantivos e o jogador precisa saber qual e pior.
    expect(NIVEIS.map((n) => SIMBOLO_DO_NIVEL[n])).toEqual(["✓✓", "✓", "✗", "✗✗"]);
  });

  it("todo nivel TEM simbolo, e nenhum sobra", () => {
    // Nivel novo sem simbolo apareceria sem marca na tela; simbolo de nivel que nao existe e
    // codigo morto que engana quem le.
    expect(Object.keys(SIMBOLO_DO_NIVEL).sort()).toEqual([...NIVEIS].sort());
  });
});

describe("placar da sessão", () => {
  it("imprecisão NÃO conta como acerto", () => {
    // O endpoint chama `acceptable` de correto para efeito de XP. Herdar isso no percentual da
    // sessão faria o placar dizer que o jogador vai melhor do que vai.
    const s = acumula(STATS_ZERO, { is_correct: true, action_quality: "acceptable" }, "call");
    expect(s.maos).toBe(1);
    expect(s.acertos).toBe(0);
    expect(s.porNivel.imprecisao).toBe(1);
  });

  it("soma o custo em bb, sempre positivo", () => {
    let s = acumula(STATS_ZERO, { is_correct: false, action_quality: "leak", ev_loss_bb: -1.21 }, "fold");
    s = acumula(s, { is_correct: false, action_quality: "leak", ev_loss_bb: 0.4 }, "call");
    // o sinal do ev_loss varia por superfície no produto; o placar mostra quanto CUSTOU
    expect(s.bbPerdidos).toBe(1.61);
    expect(s.maos).toBe(2);
  });

  it("acerto sem custo não inventa bb perdido", () => {
    const s = acumula(STATS_ZERO, { is_correct: true, action_quality: "correct" }, "fold");
    expect(s.bbPerdidos).toBe(0);
    expect(s.acertos).toBe(1);
  });
});

describe("pausar depois de", () => {
  it("nunca segue direto, ação sempre espera, erro só no erro", () => {
    expect(devePausar("nunca", "grave")).toBe(false);
    expect(devePausar("acao", "correta")).toBe(true);
    expect(devePausar("erro", "errada")).toBe(true);
    expect(devePausar("erro", "grave")).toBe(true);
    // imprecisão não segura o grind: ela é uma das ações que o GTO mistura
    expect(devePausar("erro", "imprecisao")).toBe(false);
    expect(devePausar("erro", "correta")).toBe(false);
  });

  it("SEM grade nao ha veredito: nao se acusa por falta de resposta", () => {
    // O dono, vendo a tela: "ao clicar em uma acao...antes do veredito final, esta aparecendo
    // rapidamente o veredito 'errada', e na sequencia aparece o veredito real".
    //
    // A causa nao era animacao: enquanto a resposta do servidor nao chegava, a mesa julgava com
    // `grade` nulo, e a ultima linha de `nivelDoGrade` respondia `is_correct ? correta : errada`
    // -- ou seja ERRADA, sempre. O flash era o sintoma; o defeito de verdade e que uma falha do
    // `/grade` deixava a acusacao inventada PARADA na tela, sem nenhum dado por baixo.
    //
    // O comentario daquela linha ja dizia o certo ("a regua da casa manda calar em vez de
    // afirmar") e o codigo fazia o contrario. Agora nao ha veredito sem base: `null`.
    expect(nivelDoGrade(null, "fold")).toBeNull();
    expect(nivelDoGrade(undefined, "raise")).toBeNull();
    expect(nivelDoGrade({} as never, "fold")).toBeNull();
    // e nem com `is_correct` sozinho, que e o que o endpoint devolve quando NAO houve carta
    expect(nivelDoGrade({ is_correct: false } as never, "fold")).toBeNull();
    expect(nivelDoGrade({ is_correct: true } as never, "fold")).toBeNull();
  });

  it("mao sem veredito nao entra no placar", () => {
    // Contar como erro seria a mesma invencao; contar como acerto, o oposto. Ela fica fora, e a
    // tela diz que ficou.
    const s = acumula(STATS_ZERO, null, "fold");
    expect(s.maos).toBe(0);
    expect(s.acertos).toBe(0);
    expect(Object.values(s.porNivel).reduce((a, b) => a + b, 0)).toBe(0);
  });

  it("frequencia ZERO nunca e 'aceitavel', mesmo com custo baixo", () => {
    // O caso da captura do dono: SB 96s a 10bb, ele limpou, o GTO faz allin 100%, custo 0,028bb.
    // A tela dizia "0% SUA JOGADA" e "✓ aceitavel" ao mesmo tempo, com "o GTO joga: allin 100%"
    // logo abaixo -- o selo endossava o que a linha de baixo desmentia.
    const puro = { hand_freq: { fold: 0, call: 0, raise: 0, allin: 1 }, ev_loss_bb: 0.028,
                   action_quality: "major_leak" } as never;
    expect(nivelDoGrade(puro, "call")).toBe("errada");
    expect(nivelDoGrade(puro, "allin")).toBe("correta");

    // e o CUSTO segue decidindo a severidade DENTRO do lado ruim
    expect(nivelDoGrade({ ...(puro as object), ev_loss_bb: 3 } as never, "call")).toBe("errada");
    expect(nivelDoGrade({ ...(puro as object), ev_loss_bb: 3.01 } as never, "call")).toBe("grave");
  });

  it("custo indistinguivel de zero nao vira erro (o piso de ruido)", () => {
    // Medido: `HJ Q5s 50bb` abrindo custa 0,001bb pela carta de EV. O GTO nao faz, mas chamar
    // 0,001bb de erro e preciosismo -- e o numero nem sobrevive ao arredondamento de duas casas
    // que a propria tela faz.
    const ruido = { hand_freq: { fold: 1, raise: 0 }, ev_loss_bb: 0.001 } as never;
    expect(nivelDoGrade(ruido, "raise")).toBe("imprecisao");
    // no limite do piso, ja e erro
    // no limite: a tela mostra duas casas, entao 0,004 aparece como "-0,00bb" e 0,005 como
    // "-0,01bb". O veredito acompanha o que o jogador LE.
    expect(nivelDoGrade({ ...(ruido as object), ev_loss_bb: 0.004 } as never, "raise")).toBe("imprecisao");
    expect(nivelDoGrade({ ...(ruido as object), ev_loss_bb: 0.005 } as never, "raise")).toBe("errada");
  });

  it("o GTO FAZ, mas pouco: continua 'aceitavel' e nao depende do custo", () => {
    // A perna menor da mistura e o outro caminho para "aceitavel", e este e o que o dono pediu
    // quando falou de "um % mais baixo". Aqui o custo nem entra na conta.
    const mistura = { hand_freq: { fold: 0.85, raise: 0.15 }, ev_loss_bb: 2.5 } as never;
    expect(nivelDoGrade(mistura, "raise")).toBe("imprecisao");
  });

  it("perna de 0,4% nao e 'o GTO faz': ela cai no lado ruim", () => {
    // Achado medindo: o acervo tem pernas de frequencia minuscula com custo alto. A maior delas
    // custa 2,552bb com 0,4% de frequencia (UTG+2 QJo 14bb, allin). Sem piso, a regra "faz pouco
    // -> aceitavel" absolveria isso.
    //
    // 1% e o mesmo numero que o card usa para LISTAR as pernas: o que nao aparece na tela nao
    // pode justificar o veredito nela.
    const minuscula = { hand_freq: { fold: 0.996, allin: 0.004 }, ev_loss_bb: 2.552 } as never;
    expect(nivelDoGrade(minuscula, "allin")).toBe("errada");
    const existe = { hand_freq: { fold: 0.99, allin: 0.01 }, ev_loss_bb: 2.552 } as never;
    expect(nivelDoGrade(existe, "allin")).toBe("imprecisao");
  });
});
