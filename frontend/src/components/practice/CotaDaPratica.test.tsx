// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

vi.mock("react-router-dom", () => ({
  Link: ({ children, to, ...p }: { children: React.ReactNode; to: string }) =>
    <a href={to} {...p}>{children}</a>,
}));

import { ContadorDaCota, CotaEsgotada } from "./CotaDaPratica";
import { PainelDePratica } from "./PainelDePratica";
import { CONFIG_PADRAO, STATS_ZERO, type ConfigPratica } from "@/lib/pratica";
import type { CotaDaPratica } from "@/lib/api";

const FREE: CotaDaPratica = {
  plano: "free", mesas: 2, spots_limite: 30, spots_usados: 12,
  spots_restantes: 18, esgotado: false, renova_em: "2026-10-01",
};

/**
 * A cota do Prática na tela.
 *
 * O pedido do dono (18/09) tem duas metades, e a segunda é a que este arquivo cobra: "no maximo 30
 * spots por mes... **e isto precisa ficar explicito pra eles na tela**". Limite que só aparece
 * quando o jogador bate nele é indistinguível de defeito.
 */
describe("o contador da cota", () => {
  afterEach(cleanup);

  it("mostra usados e limite", () => {
    render(<ContadorDaCota cota={FREE} />);
    expect(screen.getByTestId("pratica-cota").textContent).toContain("cota.spots:12,30");
  });

  it("NAO aparece em plano sem teto: barra cheia mentiria para quem nao tem limite", () => {
    render(<ContadorDaCota cota={{ ...FREE, plano: "pro", spots_limite: null,
                                   spots_restantes: null, mesas: 4 }} />);
    expect(screen.queryByTestId("pratica-cota")).toBeNull();
  });

  it("nao aparece antes da primeira resposta do servidor", () => {
    render(<ContadorDaCota cota={null} />);
    expect(screen.queryByTestId("pratica-cota")).toBeNull();
  });
});

describe("o fim da cota", () => {
  afterEach(cleanup);

  const esgotada: CotaDaPratica = { ...FREE, spots_usados: 30, spots_restantes: 0, esgotado: true };

  it("fecha com o relatorio e com a saida do Pro, e nao com uma parede", () => {
    render(<CotaEsgotada cota={esgotada} onRelatorio={() => {}} />);
    expect(screen.getByTestId("pratica-cota-relatorio")).toBeTruthy();
    expect(screen.getByTestId("pratica-cota-pro").getAttribute("href")).toBe("/subscription");
  });

  it("diz o limite que foi atingido, e nao um numero cravado", () => {
    render(<CotaEsgotada cota={esgotada} onRelatorio={() => {}} />);
    expect(screen.getByTestId("pratica-cota-esgotada").textContent)
      .toContain("cota.esgotada.titulo:30");
  });

  /**
   * A data de renovação NÃO pode andar um dia para trás.
   *
   * `new Date("2026-10-01")` é interpretado como UTC pelo navegador, e em fuso negativo (o nosso)
   * `toLocaleDateString` devolve 30/09. A tela prometeria a cota para o dia anterior ao que o
   * servidor usa como corte, e o jogador voltaria e encontraria a parede de novo. Por isso o
   * componente monta a data com `T00:00:00` explícito, e é isto que este caso trava.
   */
  /**
   * A variante compacta nasceu de um dano que eu mesmo causei: o bloco de tela cheia entrava
   * quando a cota zerava e APAGAVA as mesas com os vereditos que o jogador estava lendo.
   */
  it("compacta: faixa com a saida do Pro, e SEM o bloco de tela cheia", () => {
    render(<CotaEsgotada cota={esgotada} compacto onRelatorio={() => {}} />);
    expect(screen.getByTestId("pratica-cota-faixa")).toBeTruthy();
    expect(screen.queryByTestId("pratica-cota-esgotada")).toBeNull();
    expect(screen.getByTestId("pratica-cota-pro-faixa").getAttribute("href")).toBe("/subscription");
  });

  it("a faixa tambem diz quando a cota volta", () => {
    render(<CotaEsgotada cota={esgotada} compacto onRelatorio={() => {}} />);
    expect(screen.getByTestId("pratica-cota-faixa").textContent).toContain("cota.esgotada.volta");
  });

  it("promete o dia 1, e nao o ultimo dia do mes anterior", () => {
    render(<CotaEsgotada cota={esgotada} onRelatorio={() => {}} />);
    const txt = screen.getByTestId("pratica-cota-esgotada").textContent || "";
    expect(txt).toMatch(/01/);
    expect(txt).not.toMatch(/30\/09|30 de set|Sep 30|30 sept/i);
  });
});

/**
 * O seletor de mesas tem DOIS limites com motivos diferentes, e a frase tem de dizer o certo.
 *
 * Trocar uma frase pela outra faz o jogador consertar a coisa errada: girar o celular quando o
 * barrado é o plano, ou assinar o Pro quando o barrado é a janela.
 */
describe("o teto de mesas do plano no painel", () => {
  afterEach(cleanup);

  function monta(tetoDeMesas: number, tetoDoPlano: number, config: ConfigPratica = CONFIG_PADRAO) {
    render(<PainelDePratica aberto config={config} pendente={null} stats={STATS_ZERO}
                            tetoDeMesas={tetoDeMesas} tetoDoPlano={tetoDoPlano}
                            onConfig={vi.fn()} onAlternar={() => {}} onAplicar={() => {}} />);
  }

  it("free em tela grande: 3 e 4 travadas, e o motivo dito e o PLANO", () => {
    monta(4, 2);
    expect(screen.getByTestId("pratica-mesas-2").hasAttribute("disabled")).toBe(false);
    expect(screen.getByTestId("pratica-mesas-3").hasAttribute("disabled")).toBe(true);
    expect(screen.getByTestId("pratica-mesas-4").hasAttribute("disabled")).toBe(true);
    expect(screen.getByTestId("pratica-teto-do-plano")).toBeTruthy();
    expect(screen.queryByTestId("pratica-so-uma-mesa")).toBeNull();
  });

  it("celular: o motivo volta a ser a TELA, mesmo sendo free", () => {
    monta(1, 2);
    expect(screen.getByTestId("pratica-mesas-2").hasAttribute("disabled")).toBe(true);
    expect(screen.getByTestId("pratica-so-uma-mesa")).toBeTruthy();
    expect(screen.queryByTestId("pratica-teto-do-plano")).toBeNull();
  });

  it("pro em tela grande: nenhuma travada e nenhuma frase", () => {
    monta(4, 4);
    for (const n of [1, 2, 3, 4]) {
      expect(screen.getByTestId(`pratica-mesas-${n}`).hasAttribute("disabled")).toBe(false);
    }
    expect(screen.queryByTestId("pratica-teto-do-plano")).toBeNull();
    expect(screen.queryByTestId("pratica-so-uma-mesa")).toBeNull();
  });

  /**
   * Chegar por `?mesas=4` sendo free não pode deixar NENHUM botão aceso: isso parece defeito.
   * A escolha dele fica guardada (não reescrevemos a config) e o seletor desenha o valor aparado.
   */
  it("com ?mesas=4 no free, o seletor acende o 2 em vez de nada", () => {
    monta(4, 2, { ...CONFIG_PADRAO, mesas: 4 });
    expect(screen.getByTestId("pratica-mesas-2").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("pratica-mesas-4").getAttribute("aria-pressed")).toBe("false");
  });
});
