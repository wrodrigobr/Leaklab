import { describe, it, expect } from "vitest";
import ptBR from "@/i18n/locales/pt-BR/evolution.json";
import { buildEvolutionHtml, evolutionFileName } from "./evolutionExport";
import type { EvolutionReport, TrainingProofItem } from "@/lib/api";

/**
 * O arquivo baixado é a superfície com MENOS supervisão do produto: sai do site, é guardado, e
 * pode ser aberto meses depois, possivelmente na frente de um coach. Se ele afirmar algo que a
 * tela não afirma, ninguém vai estar por perto para corrigir.
 *
 * Por isso estes testes protegem, acima de tudo, as CORREÇÕES que a auditoria da tela produziu.
 * Reescrever o layout é a oportunidade natural de reintroduzi-las sem perceber.
 */

/** `t` de verdade, lendo o PT-BR do app: chave que não existir vaza como texto cru e o teste vê. */
const t = (chave: string, opts: Record<string, unknown> = {}): string => {
  const bruto = chave.split(".").reduce<unknown>(
    (o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), ptBR);
  if (typeof bruto !== "string") return (opts.defaultValue as string) ?? `!!${chave}!!`;
  return bruto.replace(/\{\{(\w+)\}\}/g, (_, k) => String(opts[k] ?? ""));
};

const spotLabel = (k: string) => `spot(${k})`;

const relatorio = (over: Partial<EvolutionReport> = {}): EvolutionReport => ({
  resumo: { n_torneios: 8, bb_por_torneio: 12.4, anterior: 18.9, delta: -6.5 },
  timeline: [],
  top_spots: [{
    ext: "T-900", hand_id: "H1", street: "preflop", position: "BTN", vs_position: "SB",
    stack_bb: 42.5, action: "fold", best_action: "raise", gto_label: "never", ev_loss_bb: 3.42,
  }],
  matriz: [
    { position: "BTN", bucket: "35-60bb", n: 40, bb_100: 5.2 },
    { position: "BB",  bucket: "35-60bb", n: 0,  bb_100: null },  // sem amostra
  ],
  ...over,
});

const prova = (over: Partial<TrainingProofItem> = {}): TrainingProofItem => ({
  category_key: "rfi:UTG+1:_:50", familia: "rfi:UTG+1:_",
  baseline_pct: 8.1, baseline_n: 60, after_pct: 0, after_n: 128, delta: -8.1,
  snapshot: null, confident: true,
  validacao: {
    veredito: "melhorou", label: "melhorou", n_antes: 60, n_depois: 128,
    taxa_antes: 8.1, taxa_depois: 0.0, taxa_global: 11.2,
    taxa_antes_ajustada: 6.4, ic_diferenca: [1.2, 11.5],
  },
  acoes: [{ acao: "fold", n: 128, erros: 0 }, { acao: "raise", n: 12, erros: 3 }],
  pureza: { puro: { n: 96, erros: 14 }, misto: { n: 34, erros: 3 } },
  ...over,
});

const montar = (over: { data?: EvolutionReport; proof?: TrainingProofItem[] } = {}) =>
  buildEvolutionHtml({
    data: over.data ?? relatorio(),
    proof: over.proof ?? [prova()],
    t, spotLabel,
    origin: "https://grindlabpoker.com",
    geradoEm: new Date("2026-07-28T14:30:00Z"),
    locale: "pt-BR",
  });

describe("relatório de evolução em HTML", () => {
  it("é um documento completo e autossuficiente, sem buscar nada de fora", () => {
    const html = montar();
    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(html).toContain("</html>");
    // Nada de CDN, fonte remota ou imagem externa: o arquivo tem que abrir offline.
    expect(html).not.toMatch(/<link[^>]+href=["']http/i);
    expect(html).not.toMatch(/<script/i);
    expect(html).not.toMatch(/@import|url\(https?:/i);
    expect(html).not.toMatch(/<img/i);
  });

  it("leva o logotipo do GrindLab embutido como SVG, não como link", () => {
    const html = montar();
    expect(html).toContain("<svg");
    expect(html).toContain("GrindLab");
    expect(html).toContain("#2DD4BF");   // o teal da marca, vindo do próprio arquivo de marca
  });

  // A marca é desenhada para fundo escuro. O documento pode abrir em tema claro e SEMPRE vai para
  // papel branco se impresso — e ali o cinza da palavra "Grind" praticamente some. A troca é por
  // contexto (CSS vence atributo de apresentação), nunca recolorindo o arquivo de marca, que
  // continua correto onde o fundo é escuro.
  it("o logotipo troca de tinta conforme o fundo, sem recolorir o asset", () => {
    const html = montar();
    expect(html).toContain('fill="#E3E8EC"');                     // o asset chega intacto
    expect(html).toContain('.marca svg [fill="#E3E8EC"] { fill: var(--logo-ink); }');
    // tinta escura declarada nos dois contextos de fundo claro: tema claro e impressão
    const claro = html.slice(html.indexOf("prefers-color-scheme: light"));
    expect(claro).toContain("--logo-ink:#0F1724");
    const impressao = html.slice(html.indexOf("@media print"));
    expect(impressao).toContain("--logo-ink:#0F1724");
  });

  it("nenhuma chave de tradução vaza sem valor", () => {
    const html = montar();
    expect(html).not.toContain("!!");
  });

  // ── as correções da auditoria, que reescrever o layout convida a desfazer ──────────────

  it("NÃO apresenta o spot misto como taxa — só o puro vira porcentagem", () => {
    const html = montar();
    // puro: 14/96 = 15%
    expect(html).toContain("15%");
    expect(html).toContain("14/96");
    // misto: 3/34 = 9% — este número NÃO pode aparecer como taxa em lugar nenhum.
    expect(html).not.toContain("9%");
    // e a ressalva do porquê tem que viajar junto
    expect(html).toContain("Não compare esse número com o de cima");
  });

  it("célula sem amostra fica vazia, nunca zero", () => {
    const html = montar();
    const celulas = html.match(/<td[^>]*>(.*?)<\/td>/gs) ?? [];
    const vazias = celulas.filter((c) => c.includes("vaz"));
    expect(vazias).toHaveLength(1);
    expect(vazias[0]).not.toMatch(/>0(\.0)?</);
    expect(vazias[0]).toContain("—");
  });

  // Cada quadrante traz dois números. Sem chave, "1.1" e "12" são dois números sem unidade, e o
  // leitor inventa a própria interpretação — num arquivo salvo não há ninguém para corrigir.
  it("explica os dois números do quadrante ANTES da grade, não no rodapé", () => {
    const html = montar();
    const posChave = html.indexOf("chave-cel");
    const posGrade = html.indexOf("<table");
    expect(posChave).toBeGreaterThan(-1);
    expect(posChave).toBeLessThan(posGrade);
    expect(html).toContain("bb perdidos a cada 100 decisões");
    expect(html).toContain("quantas decisões foram medidas ali");
    expect(html).toContain("Não quer dizer que você acertou");   // o vazio explicado junto
  });

  it("declara o recorte: sem gabarito, EV não confiável e zona de ICM ficam de fora", () => {
    const html = montar();
    expect(html).toContain("o solver sabe avaliar");
    expect(html).toContain("estimativas confiáveis");
    expect(html).toContain("ICM");
    // "piso" é a palavra que impede ler o custo como total exato
    expect(html).toContain("piso");
  });

  it("avisa que os números são congelados, para não serem lidos como leitura de hoje", () => {
    expect(montar()).toContain("não se atualizam");

    const congelado = buildEvolutionHtml({
      data: relatorio(), proof: [prova()], t, spotLabel,
      origin: "https://grindlabpoker.com", geradoEm: new Date("2026-07-28T14:30:00Z"),
      congeladoEm: "12 de junho de 2026", locale: "pt-BR",
    });
    expect(congelado).toContain("Retrato congelado de 12 de junho de 2026");
    expect(congelado).not.toContain("Gerado em");
  });

  // ── as duas armadilhas de um documento que sai do site ────────────────────────────────

  // Posição, ação e id de mão nascem do arquivo de hand history que o PRÓPRIO usuário subiu, e
  // acabam num HTML que ele vai abrir no navegador. São dois caminhos com defesas diferentes: o
  // que vira TEXTO passa por `escapar`, o que vira URL passa por `encodeURIComponent`. O teste
  // cobre os dois, porque acertar um e esquecer o outro é o modo natural de errar aqui.
  it("neutraliza dado hostil vindo do hand history, no texto e na URL", () => {
    const html = montar({
      data: relatorio({
        top_spots: [{
          ext: '"><script>alert(1)</script>', hand_id: "H<2>", street: "flop",
          position: "B&B", vs_position: '<img onerror=x>', stack_bb: 10,
          action: '</b><script>alert(2)</script>', best_action: "raise",
          gto_label: null, ev_loss_bb: 1,
        }],
      }),
      proof: [],
    });
    // nenhum script sobrevive, venha ele pela URL ou pelo texto
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img onerror");
    // texto → entidades
    expect(html).toContain("B&amp;B");
    expect(html).toContain("&lt;script&gt;alert(2)&lt;/script&gt;");
    // URL → percent-encoding
    expect(html).toContain("%3Cscript%3E");
  });

  it("usa link absoluto, porque no arquivo salvo o relativo aponta para file://", () => {
    const html = montar();
    expect(html).toContain("https://grindlabpoker.com/replayer?t=T-900&amp;h=H1");
    expect(html).not.toMatch(/href="\/replayer/);
    expect(html).not.toMatch(/href="\/evolucao/);
  });

  // ── o conteúdo em si ───────────────────────────────────────────────────────────────────

  // O banco guarda "allin"; o produto diz "Shove" em toda superfície visível. Um arquivo salvo em
  // disco é a pior superfície para falar outra língua, porque ninguém está por perto para explicar.
  it("usa o vocabulário do produto, nunca o valor cru do banco", () => {
    const html = montar({
      data: relatorio({
        top_spots: [{
          ext: "T-1", hand_id: "H1", street: "preflop", position: "SB", vs_position: null,
          stack_bb: 12, action: "call", best_action: "allin", gto_label: null, ev_loss_bb: 2,
        }],
      }),
    });
    expect(html).toContain("Shove");
    expect(html).not.toContain("allin");
    expect(html).not.toContain("jam");
  });

  // Quem lê este relatório está EVOLUINDO, não auditando. A versão anterior abria com "De 14.6%
  // (ajustado para 14.3%) para 16% em 75 decisões. O intervalo de 95% é [-13 · 8.8] e cruza o
  // zero": quatro números e dois termos de estatística antes de qualquer significado. O veredito
  // tem que vir em primeiro, em português comum; a conta desce para quem quiser conferir.
  it("abre com o veredito em linguagem comum, com a estatística separada", () => {
    const html = montar();
    const paragrafos = [...html.matchAll(/<p>([^<]+)<\/p>/g)].map((m) => m[1].trim());
    const veredito = paragrafos.find((p) => p.includes("Melhorou"));
    expect(veredito).toBeDefined();
    expect(veredito!.startsWith("Melhorou de verdade")).toBe(true);
    // o jargão sai do texto principal
    expect(veredito).not.toContain("intervalo");
    expect(veredito).not.toContain("[");
    // mas não se perde: fica no rodapé técnico, marcado como tal
    const tecnico = html.match(/<p class="tecnico">([^<]+)<\/p>/)?.[1] ?? "";
    expect(tecnico).toContain("intervalo de confiança de 95%");
    expect(tecnico).toContain("1.2");
    expect(tecnico).toContain("11.5");
  });

  // Regra do projeto: travessão em copy soa a texto de máquina.
  it("não usa travessão em nenhum texto visível", () => {
    const visivel = montar().replace(/<style>[\s\S]*?<\/style>/g, "").replace(/<svg[\s\S]*?<\/svg>/g, "");
    // O alvo é o travessão de PROSA (" texto — texto "), que é o que soa a texto de máquina.
    // O travessão sozinho continua valendo como símbolo: é o marcador de célula sem amostra.
    expect(visivel).not.toMatch(/\S\s—\s\S/);
    expect(visivel).not.toContain("&mdash;");
  });

  it("traz os mesmos números que a tela mostra", () => {
    const html = montar();
    expect(html).toContain("-12.4");          // hero
    expect(html).toContain("6.5bb");          // delta vs metade anterior
    expect(html).toContain("-3.4bb");         // spot mais caro
    expect(html).toContain("8.1%");           // antes
    expect(html).toContain("0%");             // depois
    expect(html).toContain("5.2");            // célula da matriz
    expect(html).toContain("spot(rfi:UTG+1:_)");  // rótulo pela família, sem stack
  });

  it("omite o bloco de validação quando não há veredito", () => {
    const html = montar({ proof: [prova({ validacao: null })] });
    expect(html).not.toContain("Antes e depois");
  });

  it("aguenta relatório vazio sem quebrar", () => {
    const html = montar({
      data: { resumo: { n_torneios: 0 }, timeline: [], top_spots: [], matriz: [] },
      proof: [],
    });
    expect(html).toContain("Importe suas mãos");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("undefined");
  });

  it("nomeia o arquivo com a data, porque o valor dele é ser um retrato", () => {
    expect(evolutionFileName(new Date(2026, 6, 5))).toBe("grindlab-evolucao-2026-07-05.html");
  });
});
