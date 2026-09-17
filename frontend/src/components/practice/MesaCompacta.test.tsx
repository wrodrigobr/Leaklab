// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import { MesaCompacta, historico, lerCartas } from "./MesaCompacta";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { DrillTableState } from "@/lib/api";

/**
 * A mesa do modo Prática.
 *
 * ── Por que ela existe, e o que este arquivo defende ──────────────────────────────────────────
 *
 * O dono, com quatro mesas na tela: "ja esta ficando pequeno enxergar as fichas...talvez fazer
 * como o gto wizard faz, com mesas simples, mas funcionais", e depois "mantenha as mesmas
 * proporcoes do gto wizard, tamanho de carta, tamanho das fontes, fichas".
 *
 * jsdom não faz layout, então nenhum teste aqui mede pixel. O que eles travam é o que É
 * informação na mesa e o que não pode voltar: as cartas dele, o stack de cada assento na unidade
 * certa, quem está fora, a ficha de quem apostou, e o histórico que resume a mão. Mais o
 * mecanismo que mantém a proporção (`cqw` medindo o card, e não a viewport).
 */
afterEach(cleanup);

const SEAT = (seat: number, pos: string, over: Partial<DrillTableState["seats"][0]> = {}) => ({
  seat, pos, name: pos, stack: 2000, bet: 0, folded: false, active: true, hero: false, ...over,
});

/** UTG a CO foldaram, o BTN abriu 2,2bb, o herói é o SB. bb = 100 fichas. */
const MESA: DrillTableState = {
  seats: [
    SEAT(1, "UTG", { folded: true, active: false }),
    SEAT(2, "UTG+1", { folded: true, active: false }),
    SEAT(3, "UTG+2", { folded: true, active: false }),
    SEAT(4, "LJ", { folded: true, active: false }),
    SEAT(5, "HJ", { folded: true, active: false }),
    SEAT(6, "CO", { folded: true, active: false }),
    SEAT(7, "BTN", { bet: 220, stack: 1780 }),
    SEAT(8, "SB", { bet: 50, stack: 1950, hero: true, name: "Hero" }),
    SEAT(9, "BB", { bet: 100, stack: 1900 }),
  ],
  button: 7, pot: 370, bb_chips: 100, street: "preflop", board: [],
  hero_cards: "Ks7h",
};

function monta(over: Partial<DrillTableState> = {}, unidade: "bb" | "fichas" = "bb") {
  return render(<MesaCompacta table={{ ...MESA, ...over }} hero="Hero" unidade={unidade}
                              spot="SB contra BTN, vs Open" />);
}

/** O fonte sem comentarios, para guarda estrutural nao acusar a prosa que explica o defeito. */
function semComentarios(fonte: string): string {
  return fonte
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((l) => !l.trim().startsWith("//"))
    .join("\n");
}

describe("a mesa do Pratica", () => {
  it("mostra AS CARTAS dele, uma por naipe", () => {
    monta();
    const cartas = screen.getByTestId("cartas-do-heroi");
    // Rank E SÍMBOLO. O dono, na versão só com cor: "as cartas agora estao ruins, pq ja nao sei
    // qual o naipe delas". A cor sozinha é o que o GTO Wizard faz, e funciona lá porque o
    // jogador deles decorou o código; aqui ela era um enigma -- e sem o naipe ele não sabe se a
    // mão é SUITED, que é metade da decisão preflop.
    expect(cartas.textContent).toBe("K♠7♥");

    // e a cor do quadrado segue sendo o naipe, para ler de longe
    const quadrados = Array.from(cartas.children);
    expect(quadrados.length).toBe(2);
    // jsdom normaliza hex para rgb(): comparar o hex falharia por formato, não por defeito
    expect(quadrados[0].getAttribute("style")).toContain("rgb(201, 209, 219)");   // Ks spades
    expect(quadrados[1].getAttribute("style")).toContain("rgb(217, 59, 66)");     // 7h hearts
  });

  it("a cor do naipe NUNCA e a cor de uma acao", () => {
    // O guarda de `actionColors` pegou a primeira versao desta mesa: ela usava o verde do call e
    // o azul do fold para clubs e diamonds. Nesta tela os dois vocabularios aparecem LADO A
    // LADO -- botao verde ao lado de carta verde ensinaria que a carta tem a ver com "call".
    //
    // Este guarda le os DOIS arquivos e compara, em vez de cravar a lista de hex proibidos: uma
    // cor nova na paleta de acao passa a ser barrada aqui sem ninguem lembrar de atualizar.
    const fonte = readFileSync(join(import.meta.dirname, "MesaCompacta.tsx"), "utf-8");
    const paleta = readFileSync(join(import.meta.dirname, "..", "..", "lib", "actionColors.ts"), "utf-8");
    const hexDasAcoes = [...paleta.matchAll(/#([0-9A-Fa-f]{6})/g)].map((m) => m[1].toUpperCase());
    const bloco = fonte.slice(fonte.indexOf("const NAIPE"), fonte.indexOf("export function lerCartas"));
    const hexDosNaipes = [...bloco.matchAll(/#([0-9A-Fa-f]{6})/g)].map((m) => m[1].toUpperCase());
    expect(hexDosNaipes.length).toBe(8);                       // 4 naipes x (fundo + texto)
    const colidem = hexDosNaipes.filter((h) => hexDasAcoes.includes(h));
    expect(colidem, `cor de acao usada como naipe: ${colidem.join(", ")}`).toEqual([]);
  });

  it("le a mao suited com os DOIS quadrados da mesma cor", () => {
    monta({ hero_cards: "Kc7c" });
    const cartas = screen.getByTestId("cartas-do-heroi");
    const quadrados = Array.from(cartas.children);
    expect(quadrados[0].getAttribute("style")).toContain("rgb(62, 155, 84)");
    expect(quadrados[1].getAttribute("style")).toContain("rgb(62, 155, 84)");
    // e o símbolo repetido também diz suited, para quem não lê a cor
    expect(cartas.textContent).toBe("K♣7♣");
  });

  it("cada assento mostra posicao e stack, INCLUSIVE quem foldou", () => {
    monta();
    // o abridor, com o stack já descontado da aposta
    expect(within(screen.getByTestId("assento-BTN")).getByText("17.8")).toBeTruthy();

    // ── Isto mudou em 17/09, e o caso dizia o contrário ────────────────────────────────────
    //
    // Antes o pod de quem saiu mostrava um traço, "porque número de quem não está na mão é ruído
    // com aparência de dado". O dono viu na tela e discordou: "quando os assentos nao estao na
    // mao, estamos ocultando muito o pod, e quase nao da pra ver...siga o mesmo padrao do gto
    // wizard nisto tambem".
    //
    // Ele tem razão, e o motivo não é estético: a posição que abriu antes de você e o stack que
    // ela tinha ainda informam. Era o traço que fazia o pod parecer vazio. Só o TOM muda.
    const utg = screen.getByTestId("assento-UTG");
    expect(utg.textContent, "quem saiu voltou a nao mostrar o stack").not.toContain("—");
    expect(utg.textContent).toMatch(/\d/);
  });

  it("a unidade vale para stack E aposta, com UM formatador", () => {
    // A cicatriz mais recorrente do projeto é "fichas vs BB". Dois formatadores é como a mesa
    // acaba mostrando a mesma grandeza de dois jeitos no mesmo desenho.
    monta({}, "fichas");
    expect(within(screen.getByTestId("assento-BTN")).getByText("1.780")).toBeTruthy();
    expect(screen.getByTestId("aposta-BTN").textContent).toContain("220");
  });

  it("a ficha aparece SO para quem pos dinheiro", () => {
    monta();
    expect(screen.getByTestId("aposta-BTN").textContent).toContain("2.2");
    expect(screen.getByTestId("aposta-BB").textContent).toContain("1");
    // quem foldou antes não tem ficha na mesa
    expect(screen.queryByTestId("aposta-UTG")).toBeNull();
  });

  it("o botao do dealer fica ENCOSTADO no pod do botao", () => {
    // Ele deixou de ser filho do assento: agora a geometria o posiciona, encostado na borda do pod
    // (o desenho do GTO Wizard). Como filho, ele herdava o `overflow` e o tamanho do pod.
    monta();
    const d = screen.getByTestId("botao-dealer");
    expect(d.textContent).toContain("D");

    // e ele está SOBRE o pod do BTN, não sobre outro: as duas caixas se tocam
    const pod = screen.getByTestId("assento-BTN").style;
    const dealer = d.style;
    const dist = Math.hypot(
      parseFloat(pod.left) - parseFloat(dealer.left),
      parseFloat(pod.top) - parseFloat(dealer.top),
    );
    const outro = screen.getByTestId("assento-SB").style;
    const distOutro = Math.hypot(
      parseFloat(outro.left) - parseFloat(dealer.left),
      parseFloat(outro.top) - parseFloat(dealer.top),
    );
    expect(dist, "o D esta mais perto de outro assento que do BTN").toBeLessThan(distOutro);
  });

  it("o spot escrito no CENTRO, e curto", () => {
    // O dono: "o texto no feltro tem que ser algo mais simples também, como por exemplo: LJ
    // Contra UTG1, vs Open". A frase longa da Academia ("Você abriu de LJ e BTN deu 3-bet.
    // 20.0bb efetivos.") virava três linhas de texto miúdo no meio da mesa.
    monta();
    expect(screen.getByText("SB contra BTN, vs Open")).toBeTruthy();
  });

  it("as medidas vem do TAMANHO MEDIDO, e nao de container query", () => {
    // A mesa mede o próprio tamanho e posiciona em px. Antes ela media em `cqw`/`cqh` com
    // `clamp()`, e as posições saíam em `%` com `calc()` -- o que obrigava cada regra do desenho a
    // existir duas vezes, uma para o navegador e uma para o medidor de colisão. Cinco desenhos num
    // dia depois, a duplicação saiu.
    monta();
    const raiz = screen.getByTestId("mesa-compacta");
    const arena = screen.getByTestId("arena-da-mesa");
    // posicionamento absoluto em px, vindo da geometria
    expect(arena.style.position).toBe("absolute");
    expect(arena.style.left).toMatch(/px$/);
    expect(arena.style.width).toMatch(/px$/);

    const fonte = semComentarios(readFileSync(join(import.meta.dirname, "MesaCompacta.tsx"), "utf-8"));
    expect(fonte, "o recorte do componente falhou").toContain("export function MesaCompacta");
    expect(fonte, "container query voltou: sao duas contas outra vez").not.toContain("cqw");
    expect(fonte, "clamp no componente e a segunda escrita da medida").not.toContain("clamp(");
    expect(fonte, "a mesa precisa MEDIR para saber o aspecto do espaco").toContain("ResizeObserver");
    expect(raiz.className).toContain("relative");
  });

  it("o historico e UMA linha por assento, com altura FIXA", () => {
    // O dono pediu duas vezes, e a segunda desfez a primeira. Primeiro: "a posicao em cima, a
    // acao embaixo....dentro de um box pra cada posicao". Depois, com a captura do GTO Wizard:
    // "as acoes tbm deve ficar neste modelo, pra economizar espaco superior".
    //
    // O box de duas linhas gastava o dobro de altura, e altura e exatamente o que falta na mesa --
    // foi a mesma escassez que achatou o trilho. Este caso trava o modelo NOVO, e existe para a
    // proxima mudanca de desenho ser uma decisao e nao um acidente.
    monta();
    const hist = screen.getByTestId("historico-da-mao");
    expect(hist.className, "sem isto um item a mais empurra a mesa").toContain("overflow-hidden");

    // a altura vem da GEOMETRIA (a mesma faixa que a arena desconta do topo), e não do conteúdo
    expect(hist.style.height, "a altura do historico precisa sair da geometria").toMatch(/px$/);
    expect(parseFloat(hist.style.height)).toBeGreaterThan(8);

    const itens = [...hist.children];
    expect(itens.length, "a varredura nao achou nenhum item do historico").toBeGreaterThan(1);
    for (const item of itens) {
      expect(item.className, "o chip e uma LINHA: posicao, stack e acao lado a lado")
        .not.toContain("flex-col");
      // posicao + stack + acao
      expect(item.children.length, "o chip precisa dos tres pedacos").toBe(3);
    }
    // e o stack aparece, como no modelo deles ("UTG 35 Fold")
    expect(hist.textContent).toMatch(/\d/);
  });

  it("o trilho e um ESTADIO, e a arena tem ASPECTO fixo", () => {
    // O pedido do dono, com a captura deles: "ideal e que as bordas superiores e inferiores da
    // mesa fiquem retas, e so curvemos as laterais...assim ganhamos espaco". Num retangulo 2:1, o
    // `rounded-full` E o estadio.
    //
    // E o aspecto fixo e o "limite minimo de achatamento" que ele pediu no recado seguinte: sem
    // ele a arena usava toda a altura do card e virava uma fita em tela baixa.
    monta();
    const arena = screen.getByTestId("arena-da-mesa");
    // a arena É o trilho: um elemento, uma borda. O `rounded-full` num retângulo é o estádio, e as
    // retas caem no eixo maior -- a mesma borda serve para a mesa horizontal e para a vertical.
    expect(arena.className, "o contorno voltou a ser elipse").toContain("rounded-full");
    expect(arena.className).toContain("border-2");

    const fonte = semComentarios(readFileSync(join(import.meta.dirname, "MesaCompacta.tsx"), "utf-8"));
    // CONTROLE: o corte de comentarios nao pode comer o codigo
    expect(fonte).toContain("export function MesaCompacta");
    expect(fonte, "o contorno tem de ser pill, e nao elipse").not.toContain("rounded-[50%]");
    expect(fonte, "a arena precisa vir da geometria").toContain("layoutDaMesa");
  });

  it("NENHUM tamanho da mesa fica cravado no componente", () => {
    // A varredura N+1 da regra 5. O botão do dealer era `size-3.5` + `text-[7px]` cravados, e
    // ficou de fora das duas primeiras calibragens justamente porque não estava na tabela de
    // medidas -- o dono teve de citá-lo por nome. A tabela mora em `geometriaDaMesa.ts`; aqui o
    // guarda é que o COMPONENTE não escreva tamanho nenhum por conta própria.
    const fonte = readFileSync(join(import.meta.dirname, "MesaCompacta.tsx"), "utf-8");
    const corpo = fonte.slice(fonte.indexOf("export function MesaCompacta"));

    // CONTROLE: sem isto, um recorte errado deixaria as buscas abaixo passarem verdes sobre uma
    // string vazia.
    expect(corpo.length, "o recorte do componente falhou").toBeGreaterThan(2000);

    expect(corpo, "tamanho de fonte cravado no JSX nao escala com o card").not.toMatch(/text-\[\d+px\]/);
    expect(corpo, "size-N do Tailwind e tamanho fixo").not.toMatch(/size-\d/);
    expect(corpo, "w-N/h-N do Tailwind sao tamanho fixo").not.toMatch(/[wh]-\d+(\.\d+)?/);
  });

  it("a mesa NAO depende mais de container query", () => {
    // O caso anterior aqui exigia `container-type: size` na `.container-mesa`, porque as medidas
    // eram `clamp()` com `cqh` e sem ele TODAS caiam no piso. A regra saiu do CSS e virou px
    // medido, e a classe foi removida junto -- deixa-la seria CSS morto com cara de dependencia.
    const css = readFileSync(join(import.meta.dirname, "..", "..", "index.css"), "utf-8");
    expect(css, "a classe voltou, e agora nao tem consumidor").not.toContain(".container-mesa");
    const fonte = semComentarios(readFileSync(join(import.meta.dirname, "MesaCompacta.tsx"), "utf-8"));
    expect(fonte).not.toContain("container-mesa");
  });

  /** O formatador que a mesa usa em BB, com o blind em 100 fichas. Ele fica aqui, e nao no
   *  componente, porque `historico` e exportada justamente para ter teste proprio -- e o caso que
   *  engana (o blind do BB) so aparece quando se controla o valor do blind. */
  const fmt = (chips: number) => {
    const v = Math.round((chips / 100) * 10) / 10;
    return Number.isInteger(v) ? String(v) : v.toFixed(1);
  };

  it("resume quem agiu, na ordem, terminando na vez dele", () => {
    const h = historico(MESA.seats, "Hero", fmt, 100);
    expect(h.map((x) => `${x.pos} ${x.texto}`)).toEqual([
      "UTG fold", "UTG+1 fold", "UTG+2 fold", "LJ fold", "HJ fold", "CO fold",
      "BTN 2.2", "SB sua vez",
    ]);
    expect(h[h.length - 1].vez).toBe(true);
  });

  it("o blind do BB NAO conta como aposta", () => {
    // O caso que engana: o `bet` de 1bb do BB é o blind POSTADO, não agressão. Contá-lo faria a
    // faixa dizer que o BB "apostou 1" em toda mão, e o jogador leria isso como uma ação.
    const h = historico(MESA.seats, "Hero", fmt, 100);
    expect(h.some((x) => x.pos === "BB")).toBe(false);
  });

  it("o BB ENTRA quando ele realmente aumenta", () => {
    // O controle do caso acima: sem ele, um filtro que simplesmente escondesse o BB passaria
    // verde, e um 3-bet do BB desapareceria do histórico.
    const seats = MESA.seats.map((s) => (s.pos === "BB" ? { ...s, bet: 800 } : s));
    const h = historico(seats, "Hero", fmt, 100);
    expect(h.find((x) => x.pos === "BB")?.texto).toBe("8");
  });
});

describe("lerCartas", () => {
  it("le o que o servidor manda, e ignora o resto", () => {
    expect(lerCartas("Ks7h")).toEqual([["K", "s"], ["7", "h"]]);
    expect(lerCartas("TdTc")).toEqual([["T", "d"], ["T", "c"]]);
    // a CLASSE da mão não é carta: `K7s` tem uma só, e era o bug que o dono viu (as cartas não
    // apareciam). Aqui isso fica visível em vez de silencioso.
    expect(lerCartas("K7s")).toEqual([["7", "s"]]);
    expect(lerCartas(null)).toEqual([]);
    expect(lerCartas("")).toEqual([]);
  });
});
