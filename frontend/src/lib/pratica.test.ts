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

describe("o veredito vem do SERVIDOR", () => {
  /**
   * A regua dos quatro niveis MOROU aqui, com os cortes de frequencia e de custo, e os casos dela
   * eram estes. Em 16/09 ela foi para o servidor, porque o historico das maos praticadas passou a
   * GRAVAR o veredito: manter a conta nos dois lados criaria duas implementacoes da mesma regra,
   * e o relatorio discordaria da mesa.
   *
   * Os casos da regua vivem agora em `backend/tests/test_pratica_preflop.py` (frequencia zero,
   * piso de ruido, piso de frequencia, perna menor da mistura, sem dado nao acusa). Aqui ficam os
   * casos do que o FRONT faz: ler.
   */
  it("le o nivel que o servidor mandou", () => {
    expect(nivelDoGrade({ nivel: "errada" } as never, "call")).toBe("errada");
    expect(nivelDoGrade({ nivel: "correta" } as never, "allin")).toBe("correta");
    expect(nivelDoGrade({ nivel: "grave" } as never, "fold")).toBe("grave");
  });

  it("NAO calcula: com os insumos na mao e sem o nivel, cala", () => {
    // Este e o guarda que impede a regua de voltar para ca. Os tres campos abaixo bastariam para
    // recalcular tudo -- e e exatamente isso que nao pode acontecer.
    const comInsumos = {
      hand_freq: { fold: 0, allin: 1 },
      ev_loss_bb: 0.028,
      action_quality: "major_leak",
      is_correct: false,
    } as never;
    expect(nivelDoGrade(comInsumos, "call")).toBeNull();
  });

  it("nivel desconhecido do servidor nao vira veredito", () => {
    // Backend mais novo que o bundle, ou campo renomeado: um rotulo que a tela nao sabe pintar
    // nao pode virar "errada" por descuido de comparacao.
    expect(nivelDoGrade({ nivel: "catastrofica" } as never, "fold")).toBeNull();
    expect(nivelDoGrade({ nivel: "" } as never, "fold")).toBeNull();
    expect(nivelDoGrade({ nivel: null } as never, "fold")).toBeNull();
  });

  it("a tabela de simbolos cobre os quatro niveis, e so eles", () => {
    // O simbolo ORDENA (pedido do dono: "VV, V, X, XX") e a palavra NOMEIA.
    expect(Object.keys(SIMBOLO_DO_NIVEL).sort()).toEqual([...NIVEIS].sort());
    for (const n of NIVEIS) expect(SIMBOLO_DO_NIVEL[n]).toBeTruthy();
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
    // O `nivel` vem do servidor. O `is_correct` do endpoint chama `acceptable` de correto para
    // efeito de XP, e herdar isso no percentual da sessao faria o placar dizer que o jogador vai
    // melhor do que vai -- por isso o placar olha o NIVEL, e nao o `is_correct`.
    const s = acumula(STATS_ZERO,
                      { is_correct: true, action_quality: "acceptable", nivel: "imprecisao" } as never,
                      "call");
    expect(s.maos).toBe(1);
    expect(s.acertos).toBe(0);
    expect(s.porNivel.imprecisao).toBe(1);
  });

  it("soma o custo em bb, sempre positivo", () => {
    let s = acumula(STATS_ZERO,
                    { is_correct: false, nivel: "errada", ev_loss_bb: -1.21 } as never, "fold");
    s = acumula(s, { is_correct: false, nivel: "errada", ev_loss_bb: 0.4 } as never, "call");
    // o sinal do ev_loss varia por superfície no produto; o placar mostra quanto CUSTOU
    expect(s.bbPerdidos).toBe(1.61);
    expect(s.maos).toBe(2);
  });

  it("acerto sem custo não inventa bb perdido", () => {
    const s = acumula(STATS_ZERO, { is_correct: true, nivel: "correta" } as never, "fold");
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

  it("mao sem veredito nao entra no placar", () => {
    // Contar como erro seria a mesma invencao; contar como acerto, o oposto. Ela fica fora, e a
    // tela diz que ficou.
    const s = acumula(STATS_ZERO, null, "fold");
    expect(s.maos).toBe(0);
    expect(s.acertos).toBe(0);
    expect(Object.values(s.porNivel).reduce((a, b) => a + b, 0)).toBe(0);
  });

});
