// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { RangePanel } from "./RangePanel";

/* A tabela de ranges tem que responder a PERGUNTA que foi feita.
 *
 * Reportado com print: a pergunta do treino era "qual destas BTN joga de DOIS jeitos a 17bb?" e o
 * botão "tabela de ranges" abria a matriz do SB — a posição do SPOT (o jogador estava defendendo o
 * SB contra o BTN). Ele conferiu a mão citada, viu que ali ela nunca folda, e concluiu que o
 * produto tinha errado.
 *
 * Conferido no dado do backend: BTN a 17bb tem 86s na fronteira entrando 32%; SB a 17bb tem 86s no
 * núcleo entrando 100%. A pergunta estava CERTA — a referência que o próprio produto abriu é que
 * não respondia a pergunta feita.
 *
 * Estes testes olham a CHAMADA À API, e não o desenho da grade: é `position=` e `stack_bb=` que
 * determinam qual range o jogador vê. Um teste que só conferisse o rótulo passaria com a matriz
 * errada desde que o texto do cabeçalho estivesse certo. */

// O painel busca `/preflop-ranges?position=..&stack_bb=..` com um `authFetch` LOCAL, que chama o
// `fetch` global — então é o global que se intercepta. (A primeira versão deste teste mockava
// `@/lib/api` e não interceptava nada: cinco testes falharam com zero URLs, o que ao menos falhou
// ALTO em vez de passar medindo o vazio.)
const urls: string[] = [];

beforeEach(() => {
  urls.length = 0;
  vi.stubGlobal("fetch", (url: string) => {
    urls.push(String(url));
    // Shape COMPLETO da resposta. A primeira versão devolvia só `position`/`stack_bucket`, e o
    // painel estourava em `Object.keys(apiData.vs_rfi)` — o teste falhava por dublê incompleto,
    // não por defeito do componente. Dublê que não honra o contrato acusa a coisa errada.
    return Promise.resolve({
      json: () => Promise.resolve({
        position: "BTN", stack_bb: 17, stack_bucket: "20bb",
        rfi: { hands: ["AA", "KK"], pct: 12 },
        vs_rfi: {}, vs_3bet: null, squeeze: null,
      }),
    } as unknown as Response);
  });
});

/** Mesa mínima com o herói no SB — a posição do SPOT no relato. */
const STEP: any = {
  seats: { 1: { player: "Hero", pos: "SB", stack: 1700 }, 2: { player: "V", pos: "BTN", stack: 1700 } },
  bets: {},
  bb: 100,
  hero_stack_bb: 17,
  preflop_gto: { scenario: "vs_rfi", vs_position: "BTN" },
};

const params = (u: string) => {
  const q = new URLSearchParams(u.split("?")[1] ?? "");
  return { pos: q.get("position"), stack: q.get("stack_bb") };
};
const ultima = () => params(urls[urls.length - 1]);

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("RangePanel — condições da pergunta", () => {
  it("sem condições pedidas, abre na posição da MÃO (comportamento de sempre)", async () => {
    render(<RangePanel step={STEP} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(ultima().pos).toBe("SB");
  });

  it("o caso do relato: com a pergunta em cena, abre na posição DELA — já na PRIMEIRA busca", async () => {
    render(<RangePanel step={STEP} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}}
      posicaoInicial="BTN" stackInicial={17} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    // `urls[0]`, não a última: se o painel abrisse no SB e só depois corrigisse para BTN, o
    // jogador veria a matriz errada piscar e uma busca seria desperdiçada.
    expect(params(urls[0])).toEqual({ pos: "BTN", stack: "17" });
  });

  it("ao revelar as cartas do herói, a matriz TROCA para a da mão", async () => {
    /* Pedido explícito do usuário: "ao exibir as cartas do hero, aí a matriz teria que mudar".
     *
     * A prop muda por um PAI que re-renderiza, com o painel seguindo montado — que é como o
     * LeakTrainer faz quando a fase sai de `probe`. A primeira versão deste teste usava o
     * `rerender` da testing-library e era INCAPAZ DE FALHAR: medido com um contador de montagem,
     * o `rerender` REMONTAVA o componente, o `useState` reinicializava sozinho e o teste passava
     * mesmo com o efeito de sincronia deletado. */
    function Pai() {
      const [naPergunta, setNaPergunta] = useState(true);
      return (
        <>
          <button onClick={() => setNaPergunta(false)}>revelar</button>
          <RangePanel step={STEP} hero="Hero" heroCards={naPergunta ? [] : ["Ah", "Kh"]}
            onClose={() => {}}
            posicaoInicial={naPergunta ? "BTN" : null}
            stackInicial={naPergunta ? 17 : null} />
        </>
      );
    }
    render(<Pai />);
    await waitFor(() => expect(ultima().pos).toBe("BTN"));
    fireEvent.click(screen.getByText("revelar"));
    await waitFor(() => expect(ultima().pos).toBe("SB"));
    expect(ultima().stack).toBe("17");
  });

  it("pergunta sem posição única (ex.: 'quem abre mais?') não desvia a matriz", async () => {
    // O backend omite `posicao` quando a pergunta compara duas posições: abrir uma delas seria
    // apontar para metade das alternativas. A tela precisa tratar a ausência como "mantém o que
    // já usava", nunca como um valor vazio que vira posição.
    render(<RangePanel step={STEP} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}}
      posicaoInicial={null} stackInicial={30} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(ultima().pos).toBe("SB");
    expect(ultima().stack).toBe("30");
  });

  it("stack da pergunta manda sobre o da mesa", async () => {
    render(<RangePanel step={STEP} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}}
      posicaoInicial="LJ" stackInicial={50} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(ultima()).toEqual({ pos: "LJ", stack: "50" });
  });
});

/* MESA CURTA (20/08). A varredura de contradição (scripts/varredura_contradicao_grade.py,
 * com prova de detecção por forja) mediu no acervo real: das 3.149 combinações
 * (posição, stack, mão), 235 divergem entre o VEREDITO gravado e a GRADE — e a ablação por
 * tamanho de mesa explica quase tudo:
 *
 *     mesa 2 (HU) .... 51,5% de divergência
 *     mesa 3-4 ....... ~15%
 *     mesa 6-9 ....... 4-6%
 *
 * Não é erro de lookup: as ranges são de 9-max e numa mesa de 3 o "UTG" é outra posição
 * efetiva. O veredito conhece a mesa real; a grade, não. Então a grade DECLARA a premissa —
 * fonte que não sabe, diz que não sabe — em vez de contradizer o card ao lado. */
describe("RangePanel — mesa curta declara a premissa", () => {
  const mesaCom = (n: number): any => ({
    seats: Object.fromEntries(Array.from({ length: n }, (_, i) => [
      i + 1, { player: i === 0 ? "Hero" : `V${i}`, pos: ["BTN", "BB", "SB", "CO", "HJ", "LJ", "UTG", "UTG+1", "UTG+2"][i], stack: 2000 },
    ])),
    bets: {}, folded: [], bb: 100, hero_stack_bb: 20,
    // Shape COMPLETO do banner: dublê incompleto acusa a coisa errada (o cabeçalho deste
    // arquivo registra a primeira vez que isso custou uma investigação).
    preflop_gto: {
      scenario: "rfi", vs_position: null, position: "BTN", available: true,
      in_range: true, range_pct: 0.4, recommended_actions: ["raise"],
      action_quality: "correct", hand_freq: null, pro_notes: [], reasoning: "",
    },
  });

  it("heads-up avisa que a grade é de mesa cheia", async () => {
    render(<RangePanel step={mesaCom(2)} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}} />);
    expect(await screen.findByText("Mão heads-up.")).toBeTruthy();
    expect(screen.getByText(/mesa cheia \(9-max\)/i)).toBeTruthy();
  });

  it("mesa de 4 avisa com o número de jogadores", async () => {
    render(<RangePanel step={mesaCom(4)} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}} />);
    expect(await screen.findByText(/Mesa com 4 jogadores/i)).toBeTruthy();
  });

  it("mesa cheia NÃO avisa (senão o aviso vira ruído em 100% das mãos)", async () => {
    render(<RangePanel step={mesaCom(9)} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(screen.queryByText(/mesa cheia \(9-max\)/i)).toBeNull();
  });

  it("jogadores que já FOLDARAM não contam como mesa cheia", async () => {
    // 8 assentos, 5 já foldaram → 3 vivos: o aviso tem que aparecer.
    const step = mesaCom(8);
    step.folded = ["V1", "V2", "V3", "V4", "V5"];
    render(<RangePanel step={step} hero="Hero" heroCards={["Ah", "Kh"]} onClose={() => {}} />);
    expect(await screen.findByText(/Mesa com 3 jogadores/i)).toBeTruthy();
  });
});

/* O caso do K6s (print de 19/08): RFI de UTG+2 a 24bb. O veredito — calculado pelo backend na
 * posição UTG+2, bucket 20bb — dizia "fora do range, Fold 100%, top 20%". A grade na MESMA tela
 * renderizava LJ 20bb, onde K6s é raise. Duas causas, dois guardas:
 *
 * 1. `normalizePosition` achatava UTG+2 → LJ (e UTG+1 → UTG). Era uma SEGUNDA cópia da regra de
 *    normalização de posição — a primeira vive em `_norm_pos` no backend, que mantém UTG+2 como
 *    chave própria do GW 9-max e, com n_players, mapeia por jogadores atrás. Duas cópias
 *    discordando é a regra 5 do projeto. A fonte única é `preflop_gto.position`: a posição em que
 *    o veredito FOI calculado, já normalizada por quem o calculou.
 *
 * 2. Conferir `pos === "UTG+2"` via URLSearchParams também prova o ENCODING: sem
 *    encodeURIComponent, o `+` literal na query decodifica como ESPAÇO e o backend recebe
 *    "UTG 2" — posição inexistente, grade vazia. */
describe("RangePanel — a grade responde a pergunta do VEREDITO", () => {
  const STEP_UTG2: any = {
    seats: { 1: { player: "Hero", pos: "UTG+2", stack: 2400 }, 2: { player: "V", pos: "BB", stack: 2400 } },
    bets: {},
    bb: 100,
    hero_stack_bb: 24,
    // Shape completo do banner (o cabeçalho deste arquivo explica: dublê incompleto acusa a
    // coisa errada) — os valores são os do print: fora do range, Fold 100%, top 20%.
    preflop_gto: {
      scenario: "rfi", vs_position: null, position: "UTG+2", available: true,
      in_range: false, range_pct: 0.2, recommended_actions: ["fold"],
      action_quality: "correct", hand_freq: null, pro_notes: [], reasoning: "",
    },
  };

  it("o caso do K6s: veredito em UTG+2 busca a grade de UTG+2, não a de LJ — já na 1ª busca", async () => {
    render(<RangePanel step={STEP_UTG2} hero="Hero" heroCards={["Kh", "6h"]} onClose={() => {}} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(params(urls[0])).toEqual({ pos: "UTG+2", stack: "24" });
    // A régua de posições não tem aba fixa de UTG+2 — ela entra DINAMICAMENTE quando é a posição
    // do veredito. Sem a aba, a busca certa renderizaria uma seleção invisível.
    expect(screen.getByRole("button", { name: "UTG+2" })).toBeTruthy();
  });

  it("quando o assento e o veredito discordam (mesa curta), a posição do VEREDITO manda", async () => {
    // Mesa de 7: o assento se chama "UTG+1" no dialeto do replay, mas o backend gradeia por
    // jogadores atrás e o veredito sai em LJ. A grade tem que seguir o veredito — reproduzir o
    // mapa por jogadores atrás no frontend seria a terceira cópia da regra.
    const step: any = {
      ...STEP_UTG2,
      seats: { 1: { player: "Hero", pos: "UTG+1", stack: 2400 }, 2: { player: "V", pos: "BB", stack: 2400 } },
      preflop_gto: { ...STEP_UTG2.preflop_gto, position: "LJ" },
    };
    render(<RangePanel step={step} hero="Hero" heroCards={["Kh", "6h"]} onClose={() => {}} />);
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(params(urls[0]).pos).toBe("LJ");
  });

  it("o header rotula o arredondamento: stack real 24bb, tabela do bucket 20bb", async () => {
    // O chip mostrava só "20bb" enquanto o veredito falava de 24bb — na mesma tela, parecia
    // contradição. O rótulo liga os dois números em vez de esconder um deles.
    render(<RangePanel step={STEP_UTG2} hero="Hero" heroCards={["Kh", "6h"]} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("24bb (bucket 20bb)")).toBeTruthy());
  });
});
