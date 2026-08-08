// @vitest-environment jsdom
// As tres mudancas do card de veredito (08/08), cada uma nascida de um print do usuario.
//
//   1. o CUSTO aparece — e a ausencia dele tambem, em vez de sumir calada
//   2. o PORQUE sai de tras do toggle: o backend gerava a explicacao e a tela nao mostrava
//   3. "sem veredito" diz o MOTIVO, porque "nao sei" sem explicacao le como produto quebrado
//
// Cada teste tem CONTROLE: o estado oposto continua como era. Um teste que so verificasse a
// presenca passaria com o texto aparecendo sempre.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DecisionCard } from "./DecisionCard";

const veredito = (label: string, cls = "text-red-400") => ({
  icon: "✗", label, cls, borderCls: "border-red-500/30", hdrCls: "bg-red-500/8",
});

// `screen` busca no DOCUMENTO inteiro. Sem isto o render de um teste sobrevive no proximo, e o
// controle "nao deve aparecer" falha por causa do card ANTERIOR — foi o que aconteceu aqui.
afterEach(cleanup);

function montar(props: Record<string, unknown> = {}) {
  return render(
    <DecisionCard
      verdict={veredito("Erro") as never}
      source={{ label: "Solver", tooltip: "", variant: "solver" as never }}
      playedAction="CALL"
      idealAction="FOLD"
      idealLabel="GTO recomenda"
      isActionOk={false}
      fmtAction={(a: string) => a.toUpperCase()}
      showDetails={false}
      onToggleDetails={() => {}}
      {...props}
    />,
  );
}

describe("card de veredito — as tres mudancas", () => {
  it("1. mostra o custo em bb quando ele existe", () => {
    montar({ evLossBb: 1.4 });
    expect(screen.getByText(/1[.,]4 bb/)).toBeTruthy();
  });

  it("1b. a AUSENCIA de custo e explicada, nao silenciosa", () => {
    // Sem isto o jogador nao sabe se nao perdeu nada ou se o produto nao sabe.
    montar({ evLossBb: null });
    expect(screen.getByText("EV ?")).toBeTruthy();
  });

  it("1c. CONTROLE: em acao correta, EV ausente nao vira pergunta", () => {
    // EV perto de zero numa jogada certa nao precisa de explicacao — seria ruido em todo card.
    montar({ evLossBb: null, isActionOk: true, verdict: veredito("Correto", "text-emerald-400") });
    expect(screen.queryByText("EV ?")).toBeNull();
  });

  it("2. o porque aparece SEM precisar abrir o toggle", () => {
    // Era `showDetails && why`: a explicacao existia no payload e ficava escondida.
    montar({ why: "O preco fecha, mas o veredito vem da range.", showDetails: false });
    expect(screen.getByText(/o veredito vem da range/i)).toBeTruthy();
  });

  it("2b. CONTROLE: as pro_notes seguem atras do toggle", () => {
    const notas = <p>nota tecnica de profissional</p>;
    montar({ why: "porque sim", proNotes: notas, showDetails: false });
    expect(screen.queryByText(/nota tecnica/i)).toBeNull();
    screen.getByText(/porque sim/i);   // o why, esse, aparece
  });

  it("2c. sem why, nada de bloco vazio", () => {
    const { container } = montar({ why: undefined });
    expect(container.textContent).not.toContain("undefined");
  });

  it("4. o olho TEM trabalho: os indicadores abrem e fecham com ele", () => {
    // Ao tirar o `why` do toggle, o olho ficou inerte — so restava `proNotes`, que quase nunca
    // existe. Controle que nao faz nada e pior que controle nenhum. Agora ele revela os DADOS.
    const ind = <p>equity 53.8% · pot odds 43.8%</p>;
    montar({ indicators: ind, showDetails: false });
    expect(screen.queryByText(/pot odds/i)).toBeNull();
    cleanup();
    montar({ indicators: ind, showDetails: true });
    expect(screen.getByText(/pot odds/i)).toBeTruthy();
  });

  it("4b. CONTROLE: a LEITURA nao depende do olho", () => {
    // O que o card se propoe a responder fica sempre visivel; so a auditoria abre.
    montar({ why: "a jogada aqui e all-in", evLossBb: 1.4, indicators: <p>dado</p>,
             showDetails: false });
    screen.getByText(/a jogada aqui e all-in/i);
    screen.getByText(/1[.,]4 bb/);
  });

  it("3. o veredito neutro de 'sem cobertura' e renderizavel", () => {
    // O banner neutro ja existia; o que faltava era o card poder exibi-lo sem parecer erro.
    montar({
      verdict: veredito("Sem veredito", "text-muted-foreground") as never,
      isActionOk: true,
      idealAction: undefined,
      why: "Spot de heads-up sem carta na nossa base para esta profundidade.",
    });
    expect(screen.getByText(/sem veredito/i)).toBeTruthy();
    expect(screen.getByText(/sem carta na nossa base/i)).toBeTruthy();
  });
});
