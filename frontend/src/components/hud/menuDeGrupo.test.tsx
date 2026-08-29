// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GRUPOS } from "./navGrupos";
import { MenuDeGrupo } from "./MenuDeGrupo";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

/**
 * O menu mostra o produto inteiro, e o cadeado vem do BACKEND.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * Medido: **47 rotas de jogador, 11 na barra de navegação**. Ficavam invisíveis `/ranges`
 * (construída na véspera justamente porque a matriz só abria presa a um passo), `/evolucao`,
 * `/ghost`, `/grind`, `/hand-builder`, `/rating` e 23 aulas da Academia. Construímos e
 * escondemos — a mesma doença da matriz de ranges, um nível acima.
 *
 * E o cadeado resolve o outro lado: hoje de manhã a landing vendia Ghost Table e treino mirado
 * embaixo de um CTA "Começar grátis", e o jogador só descobria o paywall depois de criar conta.
 * Cadeado no menu aparece ANTES de ele investir tempo.
 */

function abrir(grupo = GRUPOS[1], caps?: Record<string, boolean>) {
  const r = render(
    <MemoryRouter>
      <MenuDeGrupo grupo={grupo} capacidades={caps} />
    </MemoryRouter>,
  );
  // O painel abre no clique do chevron (touch) — hover não existe em tela sensível ao toque.
  // `fireEvent`, e não `.click()` cru: o DOM nativo não dispara o handler sintético do React, e a
  // 1ª versão deste teste falhou por isso acusando o componente de não abrir o painel.
  const botao = r.container.querySelector("button[aria-expanded]") as HTMLButtonElement;
  fireEvent.click(botao);
  return r;
}

afterEach(cleanup);   // sem isto os painéis de um teste vazam para a contagem do seguinte

describe("o menu mostra o produto e o cadeado vem do backend", () => {
  it("o painel lista TODOS os itens do grupo", () => {
    const grupo = GRUPOS[1];                       // Treinar
    abrir(grupo, { ghost: true, leak_targeted: true });
    for (const item of grupo.itens) {
      expect(screen.getByText(item.chave), `sumiu do painel: ${item.to}`).toBeTruthy();
    }
    expect(grupo.itens.length).toBeGreaterThanOrEqual(4);
  });

  it("cadeia o item quando o backend diz que a capacidade é FALSE", () => {
    abrir(GRUPOS[1], { ghost: false, leak_targeted: false });
    // Dois itens de Treinar exigem capacidade; ambos devem mostrar o selo.
    expect(screen.getAllByText("Pro").length).toBe(2);
    // E o MOTIVO viaja junto: "Pro" sozinho irrita, "Pro — treina os seus erros medidos" vende.
    expect(screen.getByText("nav.motivo.ghost")).toBeTruthy();
    expect(screen.getByText("nav.motivo.leak_targeted")).toBeTruthy();
  });

  it("NÃO cadeia quando a capacidade é true", () => {
    // CONTRAPROVA: um menu que cadeia sempre passaria no teste acima e mentiria para quem paga.
    abrir(GRUPOS[1], { ghost: true, leak_targeted: true });
    expect(screen.queryByText("Pro")).toBeNull();
  });

  it("NÃO cadeia enquanto o backend não respondeu", () => {
    // Cadeado que pisca no carregamento acusa o assinante de não ter o que ele tem.
    abrir(GRUPOS[1], undefined);
    expect(screen.queryByText("Pro")).toBeNull();
  });

  it("o item travado continua CLICÁVEL", () => {
    // Item morto manda o jogador embora; item que abre a tela com o convite converte. Esconder
    // seria pior ainda: ele descobriria o paywall depois de investir tempo.
    const { container } = abrir(GRUPOS[1], { ghost: false, leak_targeted: false });
    const hrefs = [...container.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/ghost");
    expect(hrefs).toContain("/leak-trainer");
  });

  it("o CELULAR nao perde acesso: barra com destinos diretos + folha com tudo", () => {
    // ── O erro que este guarda existe para impedir (28/08) ────────────────────────────────
    //
    // Ao trocar a barra do desktop pelo menu com paineis, eu derivei a barra do CELULAR dos
    // mesmos grupos: quatro botoes apontando para as raizes. Medido, isso TIROU acesso --
    // Torneios perdeu o toque direto, o AI Coach sumiu -- e nao devolveu nada, porque os
    // subitens so existiam no painel do desktop.
    //
    // O dono perguntou se no celular nao era melhor manter como estava. Estava certo. Reverter
    // tambem nao resolveria (as 47 rotas seguem invisiveis la), entao: barra com os destinos
    // diarios MAIS uma folha com o produto inteiro.
    const header = fs.readFileSync(path.join(__dirname, "HudHeader.tsx"), "utf-8");
    const barra = header.slice(header.indexOf("const playerNavItems"),
                               header.indexOf("const mostraGrupos"));
    for (const rota of ["/dashboard", "/tournaments", "/training", "/coach"]) {
      expect(barra.includes(`"${rota}"`), `a barra do celular perdeu ${rota}`).toBe(true);
    }
    // Ancora na ATRIBUICAO, e nao na presenca das rotas no trecho: a 1a versao deste guarda
    // passou verde com uma mutacao que derivava `playerNavItems` dos grupos e deixava o array
    // antigo ao lado como variavel morta -- as rotas continuavam no texto e o teste ficava feliz.
    // Presenca nao e cobertura; a condicao e o que a barra RECEBE.
    const atribuicao = header.slice(header.indexOf("const playerNavItems"),
                                    header.indexOf("];", header.indexOf("const playerNavItems")));
    expect(
      /GRUPOS\s*\.\s*map/.test(atribuicao),
      "a barra do celular voltou a derivar dos GRUPOS: isso mostra as raizes e tira o toque " +
        "direto de Torneios e do AI Coach, que foi a regressao de 28/08",
    ).toBe(false);
    // E a folha precisa existir e ser alcancavel: barra sem folha e o estado que causou a perda.
    expect(header.includes("FolhaDeMenu"), "a folha nao esta fiada no cabecalho").toBe(true);
    expect(header.includes("setFolhaAberta(true)"), "nao ha botao que ABRE a folha").toBe(true);
  });

  it("a folha do celular mostra os MESMOS itens e cadeados do desktop", () => {
    // Duas listas divergiriam no primeiro item novo. As duas leem de `GRUPOS`.
    const folha = fs.readFileSync(path.join(__dirname, "FolhaDeMenu.tsx"), "utf-8");
    expect(folha.includes("GRUPOS"), "a folha tem lista propria em vez de ler os grupos").toBe(true);
    expect(folha.includes("nav.motivo."), "a folha mostra cadeado sem o motivo").toBe(true);
  });

  it("nenhuma lista de 'isto é Pro' mora no front", () => {
    // O DEFEITO que este guarda existe para impedir. Se o front decidir sozinho o que é Pro,
    // vira a segunda fonte de verdade sobre o plano — o padrão que custou o dia inteiro quando o
    // preço apareceu escrito à mão em seis lugares. A verdade é do backend.
    const raiz = path.resolve(__dirname, "..", "..");
    const alvos = [
      path.join(__dirname, "navGrupos.ts"),
      path.join(__dirname, "MenuDeGrupo.tsx"),
    ];
    const violacoes: string[] = [];
    for (const arq of alvos) {
      const corpo = fs.readFileSync(arq, "utf-8")
        .split("\n")
        .filter((l) => !l.trim().startsWith("*") && !l.trim().startsWith("//") && !l.trim().startsWith("/*"))
        .join("\n");
      // Comparar o PLANO no front é a assinatura do defeito: `plan === "pro"`, `user.plan`.
      if (/plan\s*===|user\?\.plan|=== *["']pro["']/.test(corpo)) {
        violacoes.push(path.basename(arq));
      }
    }
    expect(
      violacoes,
      "o menu está decidindo sozinho o que é Pro. A capacidade vem de /subscription/status; " +
        "recriar a regra aqui cria uma segunda fonte de verdade sobre o plano.",
    ).toEqual([]);
    expect(raiz).toBeTruthy();
  });

  it("todo item do menu aponta para uma rota que EXISTE", () => {
    // Item que leva a 404 é pior que item ausente: quebra a confiança na navegação inteira.
    const app = fs.readFileSync(path.resolve(__dirname, "..", "..", "App.tsx"), "utf-8");
    const rotas = new Set([...app.matchAll(/path="([^"]+)"/g)].map((m) => m[1]));
    const faltando = GRUPOS.flatMap((g) => [g.to, ...g.itens.map((i) => i.to)])
      .filter((r) => !rotas.has(r));
    expect(faltando, `rotas no menu que não existem no App.tsx: ${faltando}`).toEqual([]);
  });
});
