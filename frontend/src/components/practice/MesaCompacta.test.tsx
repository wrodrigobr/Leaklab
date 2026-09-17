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

  it("cada assento mostra posicao e stack, e quem foldou aparece sem numero", () => {
    monta();
    // o abridor, com o stack já descontado da aposta
    expect(within(screen.getByTestId("assento-BTN")).getByText("17.8")).toBeTruthy();
    // quem saiu não mostra stack: número de quem não está na mão é ruído com aparência de dado
    expect(screen.getByTestId("assento-UTG").textContent).toContain("—");
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

  it("o botao do dealer fica no assento certo", () => {
    monta();
    const btn = screen.getByTestId("assento-BTN");
    expect(within(btn).getByTestId("botao-dealer")).toBeTruthy();
    expect(within(screen.getByTestId("assento-SB")).queryByTestId("botao-dealer")).toBeNull();
  });

  it("o spot escrito no CENTRO, e curto", () => {
    // O dono: "o texto no feltro tem que ser algo mais simples também, como por exemplo: LJ
    // Contra UTG1, vs Open". A frase longa da Academia ("Você abriu de LJ e BTN deu 3-bet.
    // 20.0bb efetivos.") virava três linhas de texto miúdo no meio da mesa.
    monta();
    expect(screen.getByText("SB contra BTN, vs Open")).toBeTruthy();
  });

  it("escala pelo CARD, e nao pela viewport", () => {
    // O mecanismo que mantém a proporção do GTO Wizard: as medidas medem o CONTAINER. Com `vw`,
    // uma mesa e quatro mesas dariam elementos do mesmo tamanho.
    monta();
    const raiz = screen.getByTestId("mesa-compacta");
    expect(raiz.className).toContain("container-mesa");
  });

  it("o trilho e a BORDA da arena, e nao um raio cravado em %", () => {
    // O raio em % do card nao resolve as duas celulas (estoura em 4 mesas, sobra em 2), e a sobra
    // era o vazio no meio do feltro que o dono reclamou. Este guarda impede a volta do numero
    // cravado: a elipse e a borda de um elemento que PREENCHE a arena.
    monta();
    const arena = screen.getByTestId("arena-da-mesa");
    const trilho = [...arena.children].find((el) =>
      el.className.includes("rounded-[50%]"),
    );
    expect(trilho, "o trilho precisa ser filho da arena").toBeTruthy();
    expect(trilho?.className).toContain("inset-0");

    // Sem os comentarios: esta e a SEXTA vez nesta casa que um guarda estrutural acusa a propria
    // prosa que explica o defeito (o comentario da arena cita `rx: 44` para dizer que ele saiu).
    const fonte = readFileSync(join(import.meta.dirname, "MesaCompacta.tsx"), "utf-8");
    const codigo = semComentarios(fonte);
    // CONTROLE: o corte de comentarios nao pode comer o codigo.
    expect(codigo, "o corte de comentarios apagou o componente").toContain("export function MesaCompacta");
    expect(codigo, "o corte de comentarios nao cortou nada").not.toContain("rx: 44");
    expect(codigo, "raio em % do card e o desenho que nao cabia").not.toMatch(/rx:\s*\d/);
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

  it("a `.container-mesa` expoe a ALTURA, senao toda medida cai no piso", () => {
    // Dependência entre arquivos, e o tipo de coisa que quebra calada: `container-type:
    // inline-size` expõe só `cqw`. Com ele, `min(Xcqw, Ycqh)` vira `min(X, 0)` = 0 e o `clamp`
    // devolve o PISO em toda a mesa -- que é exatamente o sintoma que este conserto atacou,
    // reintroduzido por uma linha em outro arquivo.
    const css = readFileSync(join(import.meta.dirname, "..", "..", "index.css"), "utf-8");
    const bloco = css.slice(css.indexOf(".container-mesa"));
    const fecha = bloco.indexOf("}");
    expect(bloco.slice(0, fecha)).toContain("container-type: size");
  });
});

describe("o historico da mao", () => {
  const fmt = (c: number) => {
    const v = Math.round((c / 100) * 10) / 10;
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
