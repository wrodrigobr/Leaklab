import { describe, it, expect } from "vitest";
import {
  CONFIG_PADRAO, MAX_MESAS, POSICOES_DISPONIVEIS,
  acaoDaTecla, acumula, configNaTela, devePausar, mudaOSorteio,
  tetoDeMesas,
  gradeDaTela,
  ALTURA_MINIMA_DO_CARD,
  CHROME_DO_CARD,
  MESA_MINIMA,
  LARGURA_PARA_VARIAS_MESAS,
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
    // a POSICAO escolhe o spot igual ao stack: deixa-la fora faria o filtro aplicar na hora e as
    // mesas abertas continuarem com o filtro velho, sem nada na tela explicando a diferenca
    expect(mudaOSorteio(cfg(), cfg({ posicoes: ["BTN"] }))).toBe(true);
    expect(mudaOSorteio(cfg({ posicoes: ["BTN", "CO"] }),
                        cfg({ posicoes: ["BTN", "CO"] }))).toBe(false);
    // a pausa só decide quando a tela espera: aplica na hora
    expect(mudaOSorteio(cfg({ pausa: "erro" }), cfg({ pausa: "nunca" }))).toBe(false);
  });

  it("o padrão abre na faixa curta, que é onde vive o MTT", () => {
    expect(CONFIG_PADRAO.mesas).toBe(MAX_MESAS);
    expect(Math.max(...CONFIG_PADRAO.stacks)).toBeLessThanOrEqual(20);
    // e com TODAS as posicoes: o filtro comeca sem filtrar, e "todas" e a lista com as nove e
    // nunca o vazio -- duas representacoes do mesmo estado fariam `mudaOSorteio` mentir
    expect(CONFIG_PADRAO.posicoes).toEqual([...POSICOES_DISPONIVEIS]);
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

describe("quantas mesas caberm na tela", () => {
  it("abaixo de 1024px, UMA mesa", () => {
    // O pedido do dono depois de abrir no celular: "No celular vamos ficar apenas 1 mesa".
    expect(tetoDeMesas(390)).toBe(1);     // iPhone em retrato
    expect(tetoDeMesas(844)).toBe(1);     // o mesmo iPhone em paisagem
    expect(tetoDeMesas(1023)).toBe(1);    // a janela do desktop pela metade
    expect(tetoDeMesas(1024)).toBe(MAX_MESAS);
    expect(tetoDeMesas(1920)).toBe(MAX_MESAS);
  });

  it("a escolha dele e APARADA, e nao reescrita", () => {
    // Quem configurou quatro mesas no desktop e abre no celular nao perde a preferencia: ela
    // volta a valer quando a tela crescer.
    const quatro = { ...CONFIG_PADRAO, mesas: 4 };
    expect(configNaTela(quatro, 390).mesas).toBe(1);
    expect(configNaTela(quatro, 1440).mesas).toBe(4);
    // e o resto da configuracao passa intacto
    const cheia = { ...CONFIG_PADRAO, mesas: 4, cenario: "rfi", unidade: "fichas" as const };
    const apar = configNaTela(cheia, 390);
    expect(apar.cenario).toBe("rfi");
    expect(apar.unidade).toBe("fichas");
  });

  it("quem ja escolheu 1 mesa nao e tocado", () => {
    // Sem isto, `configNaTela` devolveria um objeto NOVO a cada render e o efeito que monta as
    // mesas dispararia em loop.
    const uma = { ...CONFIG_PADRAO, mesas: 1 };
    expect(configNaTela(uma, 390)).toBe(uma);
    expect(configNaTela(uma, 1440)).toBe(uma);
  });

  it("a ALTURA tambem manda: janela baixa abre menos mesas", () => {
    // O dono reduziu a altura da janela com quatro mesas abertas e mandou a captura: as mesas
    // viraram fitas. O aspecto com faixa impede a deformacao, mas nao cria espaco.
    //
    // Medido com o medidor de colisao da geometria: card de 300px de altura passa com ZERO
    // sobreposicoes, 250px da 648 e 200px da 4.824. Entao o teto olha a altura.
    // A medicao: a MESA precisa de 300px de altura para nao colidir, em qualquer largura. O que
    // sobra para ela e a celula do grid menos o cabecalho e os botoes do card (78px, medidos).
    expect(tetoDeMesas(1680, 900), "tela cheia cabe quatro").toBe(MAX_MESAS);
    expect(tetoDeMesas(1366, 768), "1366x768 deixaria a mesa com 274px: abre duas").toBe(2);
    expect(tetoDeMesas(1680, 600), "janela baixa nao cabe quatro, mas cabe duas").toBe(2);
    expect(tetoDeMesas(1680, 420), "janela muito baixa cabe uma").toBe(1);
    // e a largura continua mandando: no celular e uma, por alta que a tela seja
    expect(tetoDeMesas(390, 1200)).toBe(1);
  });

  it("o PAINEL come largura, e a celula ainda fica acima do minimo", () => {
    // `tetoDeMesas` compara MESA_MINIMA.largura com metade da JANELA, e a celula real e menor: o
    // painel de configuracao e uma coluna de `clamp(180px, 14vw, 224px)` no desktop, mais o `p-3`
    // da faixa e o `gap-3` entre as celulas.
    //
    // Medido no pior caso -- a janela mais estreita em que duas mesas sao permitidas (1024px, o
    // corte `lg`) e com o painel ABERTO: a celula fica com 404px, contra 360 de minimo. Passa com
    // folga, mas por coincidencia de dois numeros escolhidos separadamente. Este caso e o que
    // acusa se alguem alargar o painel ou baixar o corte de 1024.
    const JANELA = LARGURA_PARA_VARIAS_MESAS;          // 1024, o corte
    const painel = Math.min(224, Math.max(180, JANELA * 0.14));
    const faixa = JANELA - painel - 2 * 12;            // p-3 nos dois lados
    const celula = (faixa - 12) / 2;                   // gap-3 entre as duas colunas
    expect(tetoDeMesas(JANELA, 1000), "duas mesas a 1024px").toBeGreaterThanOrEqual(2);
    expect(celula, `a celula real ficou com ${Math.round(celula)}px, abaixo do minimo`)
      .toBeGreaterThanOrEqual(MESA_MINIMA.largura);
  });

  it("a grade TIRA mesa, depois TIRA coluna, e so no fim deixa rolar", () => {
    // 17/09, a captura do dono com a janela do browser reduzida: quatro mesas na tela, cada uma
    // um borrao. "isto nao pode acontecer...temos que ter os cuidados responsivos...se nao cabe
    // com as condicoes minimas, deixamos apenas 1 coluna, ou algo do tipo...mas nao podemos
    // reduzir a mesa desta forma".
    //
    // A ordem importa, e e o que este caso fixa: primeiro cai o numero de mesas, depois o numero
    // de colunas, e rolar e o ultimo recurso -- porque rolar contraria um pedido anterior dele.
    expect(gradeDaTela(4, 1680, 900)).toEqual(
      { mesas: 4, colunas: 2, linhas: 2, rola: false });

    // a janela da captura: quatro pedidas, duas desenhadas, lado a lado e sem rolagem
    const dele = gradeDaTela(4, 1353, 500);
    expect(dele.mesas, "quatro mesas numa janela de 500px de altura").toBe(2);
    expect(dele.colunas).toBe(2);
    expect(dele.linhas).toBe(1);
    expect(dele.rola, "havia espaco para duas, nao precisava rolar").toBe(false);

    // largura de celular: uma coluna, por mais mesas que ele peca
    expect(gradeDaTela(4, 390, 1200)).toEqual(
      { mesas: 1, colunas: 1, linhas: 1, rola: false });

    // e o ULTIMO recurso: numa janela em que nem UMA mesa alcanca o minimo, a faixa rola em vez
    // de a mesa achatar
    const minuscula = gradeDaTela(4, 1353, 340);
    expect(minuscula.mesas).toBe(1);
    expect(minuscula.rola, "preferiu achatar a mesa a rolar a faixa").toBe(true);

    // nunca zero mesa: sem isto uma janela absurda deixaria a tela vazia
    expect(gradeDaTela(0, 1353, 500).mesas).toBe(1);
  });

  it("o piso do card e o minimo da mesa MAIS o que o card gasta em volta", () => {
    // O numero que a grade usa como piso de linha nao pode ser escolhido a olho: ele e o minimo
    // medido da mesa (300px, do medidor de colisao) mais o cabecalho e os botoes (78px, medidos
    // no layout). Se um dos dois mudar, o piso muda com ele.
    expect(ALTURA_MINIMA_DO_CARD).toBe(MESA_MINIMA.altura + CHROME_DO_CARD);
  });
});
