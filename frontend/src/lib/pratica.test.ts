import { describe, it, expect } from "vitest";
import {
  CONFIG_PADRAO, MAX_MESAS, acaoDaTecla, acumula, devePausar, mudaOSorteio,
  nivelDoGrade, normalizaAcao, proximoFoco, STATS_ZERO, type ConfigPratica,
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
  it("vêm do action_quality, e não do is_correct", () => {
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct" }, "fold")).toBe("correta");
    expect(nivelDoGrade({ is_correct: true, action_quality: "acceptable" }, "call")).toBe("imprecisao");
    expect(nivelDoGrade({ is_correct: false, action_quality: "leak" }, "call")).toBe("errada");
    expect(nivelDoGrade({ is_correct: false, action_quality: "major_leak" }, "call")).toBe("grave");
  });

  it('"melhor jogada" exige ser a ação de MAIOR frequência', () => {
    const freq = { F: 0.72, R2: 0.28 };
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: freq }, "fold"))
      .toBe("melhor");
    // mesma qualidade, mas escolheu a perna menor da mistura: correta, não melhor
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: freq }, "raise"))
      .toBe("correta");
  });

  it("sem hand_freq NUNCA promove a melhor jogada", () => {
    // Promover por otimismo infla o placar com o que não se mediu, que é a versão do
    // "zero tranquilizador" para o lado bom do número.
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct" }, "fold")).toBe("correta");
    expect(nivelDoGrade({ is_correct: true, action_quality: "correct", hand_freq: {} }, "fold"))
      .toBe("correta");
  });

  it("sem veredito nenhum, cai no que o endpoint diz e nada mais", () => {
    expect(nivelDoGrade({ is_correct: true }, "fold")).toBe("correta");
    expect(nivelDoGrade({ is_correct: false }, "fold")).toBe("errada");
    expect(nivelDoGrade(null, "fold")).toBe("errada");
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
    expect(devePausar("acao", "melhor")).toBe(true);
    expect(devePausar("erro", "errada")).toBe(true);
    expect(devePausar("erro", "grave")).toBe(true);
    // imprecisão não segura o grind: ela é uma das ações que o GTO mistura
    expect(devePausar("erro", "imprecisao")).toBe(false);
    expect(devePausar("erro", "melhor")).toBe(false);
  });
});
