// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
  }),
}));

import { FiltroDeEscopo, fraseDoEscopo } from "./FiltroDeEscopo";
import { TETO_DE_MAOS_DO_ESCOPO, type EscopoDoDashboard } from "@/lib/api";
import { ESCOPO_PADRAO } from "@/lib/escopoGuardado";

/**
 * O filtro de escopo do dashboard: o ícone, o popup, e a frase que a faixa verde mostra.
 *
 * ── O pedido (17/09) ──────────────────────────────────────────────────────────────────────────
 *
 * "criar um icone de filtro, e abrir um popup para o jogador escolher como quer filtrar 'ultimos
 * torneios, ultimas x mãos (com limite de 30 mil mãos), por data de inicio e fim'...e ao
 * selecionar, aí ficaria exposto neste bloco verde a opção do filtro do usuario".
 */

const t = (k: string, o?: Record<string, unknown>) =>
  (o ? `${k}:${Object.values(o).join(",")}` : k);

function abrir(escopo: EscopoDoDashboard = ESCOPO_PADRAO) {
  const onEscopo = vi.fn();
  render(<FiltroDeEscopo escopo={escopo} onEscopo={onEscopo} />);
  fireEvent.click(screen.getByTestId("abrir-filtro-escopo"));
  return onEscopo;
}

describe("a frase que a faixa verde mostra", () => {
  it("diz a dimensão escolhida, e não só um número", () => {
    // O conserto de 05/09 que não pode regredir: "este filtro esta muito escondido, temos que
    // pensar uma forma de ficar mais evidente para o jogador ver que os dados sao com base neste
    // filtro". A frase É o filtro visível; o ícone é só o ajuste dela.
    expect(fraseDoEscopo({ tipo: "torneios", n: 50 }, t)).toContain("scopeLastN:50");
    // o separador de milhar sai do LOCALE do ambiente, entao a expectativa usa a mesma conta em
    // vez de cravar "5,000" -- cravar faria o teste falhar numa maquina com outro locale, que e
    // falha de teste e nao de produto
    expect(fraseDoEscopo({ tipo: "maos", n: 5000 }, t))
      .toContain(`scopeMaos:${(5000).toLocaleString()}`);
    expect(fraseDoEscopo({ tipo: "periodo", de: "2026-06-01", ate: "2026-06-30" }, t))
      .toContain("scopePeriodo:2026-06-01,2026-06-30");
  });

  it("no histórico ela declara o TAMANHO do acervo", () => {
    // Sem o total, "histórico" não diz sobre quantos torneios ele está olhando -- e era essa
    // ausência (a amostra) que o dono apontou na mesma auditoria.
    expect(fraseDoEscopo({ tipo: "torneios", n: 0 }, t, 106)).toContain("scopeAll:106");
  });
});

describe("o popup", () => {
  afterEach(cleanup);

  it("abre pelo ícone e fecha pelo X", () => {
    abrir();
    expect(screen.getByTestId("filtro-escopo")).toBeTruthy();
    fireEvent.click(screen.getByTestId("fechar-filtro-escopo"));
    expect(screen.queryByTestId("filtro-escopo")).toBeNull();
  });

  it("as três dimensões estão lá, e são exclusivas", () => {
    abrir();
    // abre na aba do escopo que VALE, e não numa fixa
    expect(screen.getByTestId("opcoes-torneios")).toBeTruthy();
    expect(screen.queryByTestId("opcoes-maos")).toBeNull();

    fireEvent.click(screen.getByTestId("aba-maos"));
    expect(screen.getByTestId("opcoes-maos")).toBeTruthy();
    expect(screen.queryByTestId("opcoes-torneios"), "duas dimensões ativas ao mesmo tempo").toBeNull();

    fireEvent.click(screen.getByTestId("aba-periodo"));
    expect(screen.getByTestId("opcoes-periodo")).toBeTruthy();
  });

  it("escolher torneios devolve o escopo e fecha", () => {
    const onEscopo = abrir();
    fireEvent.click(screen.getByTestId("escopo-torneios-50"));
    expect(onEscopo).toHaveBeenCalledWith({ tipo: "torneios", n: 50 });
    expect(screen.queryByTestId("filtro-escopo"), "o popup ficou aberto depois da escolha").toBeNull();
  });

  it("o histórico é `0`, e não a ausência de escopo", () => {
    // `0` é o sentinela de acervo inteiro, o mesmo do servidor. Mandar `null` cairia no fallback
    // de 90 dias e "Histórico" voltaria a mentir, que é a cicatriz de 03/09.
    const onEscopo = abrir({ tipo: "torneios", n: 50 });
    fireEvent.click(screen.getByTestId("escopo-torneios-0"));
    expect(onEscopo).toHaveBeenCalledWith({ tipo: "torneios", n: 0 });
  });

  it("a maior opção de mãos é o TETO do servidor", () => {
    // Oferecer mais do que o servidor aceita seria a tela prometendo o que o backend apara sem
    // avisar. O número sai da constante compartilhada, e não de um literal aqui.
    abrir();
    fireEvent.click(screen.getByTestId("aba-maos"));
    expect(screen.getByTestId(`escopo-maos-${TETO_DE_MAOS_DO_ESCOPO}`)).toBeTruthy();
  });

  it("os limites das DUAS pontas são diferentes: o começo pelo fim, o fim por hoje", () => {
    // 18/09, o dono: "as datas do filtro 'de' e 'até' estão invertidas....o 'de' tem que permitir
    // selecionar o passado....o até, no máximo o dia de hoje".
    //
    // A causa era um atalho meu: eu gerava os dois campos num `map`, e o laço os fazia IDÊNTICOS
    // (piso e hoje nos dois). As duas pontas de uma faixa não são simétricas, e com limites
    // iguais dava para escolher `de` DEPOIS do `ate` -- a faixa invertida só era corrigida
    // depois, no validador, calada.
    //
    // O caso anterior só exigia que os limites EXISTISSEM, e passava verde com os dois iguais.
    abrir();
    fireEvent.click(screen.getByTestId("aba-periodo"));
    const de = screen.getByTestId("escopo-data-de") as HTMLInputElement;
    const ate = screen.getByTestId("escopo-data-ate") as HTMLInputElement;
    const hoje = new Date().toISOString().slice(0, 10);

    // o FIM não passa de hoje, e o COMEÇO não passa do fim
    expect(ate.max, "o `até` deixou de parar em hoje").toBe(hoje);
    // o teto do `de` SEGUE o `ate`. Com o `ate` no padrao (hoje) os dois coincidem, entao
    // exigir que sejam DIFERENTES seria falso -- o que prova o acoplamento e mexer numa ponta e
    // ver a outra mover, no fim deste caso.
    expect(de.max, "o `de` não está limitado pelo `até`").toBe(ate.value);

    // e o COMEÇO alcança o passado, até o piso de meses
    expect(de.min < hoje, "o `de` não permite escolher o passado").toBe(true);
    expect(ate.min, "o `até` não está limitado pelo `de`").toBe(de.value);

    // mexer numa ponta move o limite da outra
    fireEvent.change(ate, { target: { value: "2026-06-30" } });
    expect((screen.getByTestId("escopo-data-de") as HTMLInputElement).max,
           "mudar o `até` não moveu o teto do `de`").toBe("2026-06-30");
  });

  it("a faixa de data só aplica quando ele confirma, e respeita o piso", () => {
    const onEscopo = abrir();
    fireEvent.click(screen.getByTestId("aba-periodo"));
    const de = screen.getByTestId("escopo-data-de") as HTMLInputElement;
    // o piso está no PRÓPRIO campo: o seletor não oferece o que o servidor apara
    expect(de.min, "o campo de data ficou sem piso").toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(de.max, "o campo de data ficou sem teto").toMatch(/^\d{4}-\d{2}-\d{2}$/);

    fireEvent.change(de, { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByTestId("escopo-data-ate"), { target: { value: "2026-06-30" } });
    expect(onEscopo, "aplicou sem ele confirmar").not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("escopo-aplicar-periodo"));
    expect(onEscopo).toHaveBeenCalledWith({ tipo: "periodo", de: "2026-06-01", ate: "2026-06-30" });
  });

  it("o campo de data NÃO perde o foco a cada tecla", () => {
    // A lição de hoje, aplicada antes de virar defeito: uma função de componente declarada no
    // corpo de outro tem identidade nova a cada render, e o React remonta a árvore em vez de
    // atualizar. Foi o que o dono relatou no formulário de resultado manual ("a cada digitação,
    // ele perde o foco"), e este popup também tem campo.
    abrir();
    fireEvent.click(screen.getByTestId("aba-periodo"));
    const alvo = screen.getByTestId("escopo-data-de") as HTMLInputElement;
    alvo.focus();
    for (const v of ["2026-06-01", "2026-06-02", "2026-06-03"]) {
      fireEvent.change(screen.getByTestId("escopo-data-de"), { target: { value: v } });
      expect(alvo.isConnected, `o campo foi remontado ao digitar ${v}`).toBe(true);
      expect(document.activeElement, `o foco saiu ao digitar ${v}`).toBe(alvo);
    }
  });

  it("reabrir mostra o que está VALENDO, e não o rascunho abandonado", () => {
    // Sem isto o popup "lembra" uma escolha que a tela não está usando, e o jogador acha que o
    // filtro está aplicado.
    const onEscopo = vi.fn();
    const { rerender } = render(
      <FiltroDeEscopo escopo={{ tipo: "torneios", n: 20 }} onEscopo={onEscopo} />);
    fireEvent.click(screen.getByTestId("abrir-filtro-escopo"));
    fireEvent.click(screen.getByTestId("aba-maos"));
    fireEvent.click(screen.getByTestId("fechar-filtro-escopo"));

    rerender(<FiltroDeEscopo escopo={{ tipo: "torneios", n: 20 }} onEscopo={onEscopo} />);
    fireEvent.click(screen.getByTestId("abrir-filtro-escopo"));
    expect(screen.getByTestId("opcoes-torneios"), "reabriu na aba que ele abandonou").toBeTruthy();
  });
});
