// @vitest-environment jsdom
import fs from "node:fs";
import path from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BoletimDaSessao } from "./BoletimDaSessao";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, v?: Record<string, unknown>) =>
      v && "n" in v ? `${k}:${v.n}` : k,
  }),
}));

afterEach(cleanup);

/**
 * O fim do treino grátis: boletim, e não parede.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * Ao abrir o treino de fundamentos no Free, eu desliguei o teto diário sem ninguém pedir. O dono
 * corrigiu mostrando o concorrente, que limita treino (20/dia) e tipo.
 *
 * O que o print dele ensina não é o limite — é a EMBALAGEM. Onde nós mandávamos o jogador para uma
 * fase chamada `paywall` (uma frase de limite e um card de upsell), eles fecham o dia com um
 * relatório e dizem quando ele volta.
 *
 * ── A honestidade que estes guardas protegem ──────────────────────────────────────────────
 *
 * No print do concorrente, "EV DEIXADO NA MESA (BB)" aparece como **0.0** — zerado, porque os
 * spots deles são sintéticos e não há custo medido. Eu propus preencher esse número como nosso
 * diferencial, e ao checar descobri que **o nosso corretor de treino também não devolve bb**: os
 * spots de treino são sintéticos aqui também. O número honesto é ausência, não zero.
 *
 * O mesmo vale para dias seguidos e precisão sem amostra. É a regra que atravessa o produto: a
 * célula sem amostra fica cinza, nunca vira zero.
 */

const CATS = [
  { label: "Vs open", hits: 8, misses: 0 },
  { label: "RFI", hits: 3, misses: 3 },
];

function montar(props: Partial<React.ComponentProps<typeof BoletimDaSessao>> = {}) {
  return render(
    <MemoryRouter>
      <BoletimDaSessao
        totalFeito={20} totalCerto={17} melhorSequencia={5}
        categorias={CATS} cap={20} {...props}
      />
    </MemoryRouter>,
  );
}

describe("boletim da sessão", () => {
  it("mostra precisão, melhor sequência e acerto por cenário", () => {
    montar();
    expect(screen.getByText("85%")).toBeTruthy();          // 17 de 20
    expect(screen.getByText("5")).toBeTruthy();            // melhor sequência
    expect(screen.getByText("Vs open")).toBeTruthy();
    expect(screen.getByText("100%")).toBeTruthy();         // 8 de 8
    expect(screen.getByText("50%")).toBeTruthy();          // 3 de 6
  });

  it("OMITE o EV na mesa quando não foi medido", () => {
    // O defeito que o concorrente comete e eu quase repeti: mostrar 0.0 afirma que o jogador não
    // perdeu nada, quando a verdade é que não medimos aqui.
    montar({ bbNaMesa: null });
    expect(screen.queryByText("boletim.bbNaMesa")).toBeNull();
    expect(screen.queryByText("0.0")).toBeNull();
  });

  it("MOSTRA o EV quando existe", () => {
    // CONTRAPROVA: um boletim que nunca mostra o número passaria no teste acima e mataria o dado
    // no dia em que ele existir.
    montar({ bbNaMesa: 4.2 });
    expect(screen.getByText("4.2")).toBeTruthy();
    expect(screen.getByText("boletim.bbNaMesa")).toBeTruthy();
  });

  it("omite precisão quando não houve amostra", () => {
    montar({ totalFeito: 0, totalCerto: 0 });
    expect(screen.queryByText("0%"), "0% afirma desempenho ruim onde não houve desempenho").toBeNull();
  });

  it("omite dias seguidos quando não há streak", () => {
    montar({ diasSeguidos: null });
    expect(screen.queryByText(/diasSeguidos/)).toBeNull();
    cleanup();
    montar({ diasSeguidos: 1 });   // 1 dia não é sequência
    expect(screen.queryByText(/diasSeguidos/)).toBeNull();
    cleanup();
    montar({ diasSeguidos: 4 });
    expect(screen.getByText("boletim.diasSeguidos:4")).toBeTruthy();
  });

  it("diz QUANDO o jogador volta, com o número do teto", () => {
    // Metade do valor do limite diário é o gancho de retorno. Sem isto, o teto é só porta.
    montar({ cap: 20 });
    expect(screen.getByText("boletim.volteAmanha:20")).toBeTruthy();
  });

  it("lista os travados só quando há travados", () => {
    montar({ travados: [] });
    expect(screen.queryByText("boletim.noPro")).toBeNull();
    cleanup();
    montar({ travados: ["Ghost Table", "Spots pós-flop"] });
    expect(screen.getByText("Ghost Table")).toBeTruthy();
    expect(screen.getByText("boletim.noPro")).toBeTruthy();
  });

  it("a lista de travados NÃO é escrita no componente", () => {
    // Ela chega por prop, derivada do gate do backend. Uma lista aqui seria a segunda fonte de
    // verdade sobre o plano -- o padrão que custou o dia inteiro quando o preço apareceu escrito
    // à mão em seis lugares.
    const fonte = fs.readFileSync(path.join(__dirname, "BoletimDaSessao.tsx"), "utf-8")
      .split("\n").filter((l) => !l.trim().startsWith("*") && !l.trim().startsWith("//")).join("\n");
    expect(/Ghost Table|leak_targeted|=== *["']pro["']/.test(fonte),
           "o boletim decidiu sozinho o que é Pro").toBe(false);
  });
});
