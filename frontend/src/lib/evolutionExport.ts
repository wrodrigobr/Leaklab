import logoSvg from "@/assets/brand/grindlab_final_horizontal.svg?raw";
import type { EvolutionReport, TrainingProofItem } from "@/lib/api";
import { formatAction } from "@/lib/utils";

/**
 * Relatório de evolução em HTML, para baixar e guardar.
 *
 * ── POR QUE O ARQUIVO É MONTADO NO NAVEGADOR, E NÃO NO BACKEND ─────────────────────────────
 *
 * A pergunta parece de arquitetura e é de exatidão. O medo declarado do produto é o arquivo
 * afirmar um número que a tela não afirma, então a única pergunta que importa é: qual das duas
 * opções torna a divergência IMPOSSÍVEL, em vez de improvável?
 *
 * Aqui o exportador recebe `data` e `proof` — os MESMOS objetos que o JSX acabou de renderizar,
 * já em memória. Um número no arquivo veio literalmente da mesma variável que o número na tela.
 * Não há como divergir, nem por drift de código nem por diferença de instante.
 *
 * Um renderizador em Python leria as mesmas funções, mas numa SEGUNDA chamada: entre carregar a
 * página e clicar em baixar, um torneio novo pode ter entrado, e o arquivo sairia diferente do
 * que a pessoa está vendo — sem nada errado em lugar nenhum. Além disso duplicaria o layout, e
 * layout duplicado é exatamente o vetor de regressão que este projeto já pagou várias vezes.
 *
 * E o argumento que fecha: o JWT viaja no header `Authorization`, então um `<a download>` apontado
 * para o backend não autenticaria. Seria preciso buscar com header e montar um Blob no cliente de
 * qualquer forma. Ou seja, a opção do servidor custaria TODA a plumbing daqui MAIS um renderizador
 * inteiro em Python.
 *
 * ── O QUE ESTE ARQUIVO PRECISA PRESERVAR (e é fácil perder ao reescrever o layout) ──────────
 *
 * A tela passou por uma auditoria que corrigiu leituras enganosas. O exportador NÃO é uma segunda
 * chance de reintroduzi-las:
 *
 *   1. Spot MISTO não vira taxa. "Erro" é `played_freq < 0.25`; num spot misto o GTO aceita mais
 *      de uma ação, então errar exige escolher uma terceira. É estruturalmente mais difícil errar.
 *      Mostrar 8,8% (misto) ao lado de 14,6% (puro) convida "sou melhor no difícil", que é ler a
 *      régua como se fosse o resultado. Puro é taxa; misto é contagem, com a ressalva junto.
 *   2. Célula sem amostra fica VAZIA, nunca zero. Ausência de dado e jogo perfeito são coisas
 *      diferentes, e confundi-las é a mentira mais fácil de contar num mapa de calor.
 *   3. O rodapé declara o que ficou de FORA (zona de ICM, EV não confiável, decisão sem gabarito).
 *      Num arquivo que vai ser guardado, aberto meses depois e possivelmente mostrado a um coach,
 *      o recorte precisa viajar junto — a tela tem contexto ao redor, o arquivo solto não tem.
 *
 * ── AS DUAS ARMADILHAS DE UM DOCUMENTO QUE SAI DO SITE ──────────────────────────────────────
 *
 *   · `escapar()` em TUDO que vem de dado. Posição, ação e `hand_id` nascem de arquivo de hand
 *     history que o próprio usuário subiu — é entrada não confiável indo parar num HTML que ele
 *     vai abrir no navegador.
 *   · Links ABSOLUTOS. Num arquivo salvo, `/replayer?...` resolve contra `file://` e não abre nada.
 */

type TFn = (key: string, opts?: Record<string, unknown>) => string;
type SpotLabelFn = (input: string, opts?: { stack?: boolean; fallback?: string }) => string;

export interface EvolutionExportInput {
  data: EvolutionReport;
  proof: TrainingProofItem[];
  t: TFn;
  spotLabel: SpotLabelFn;
  /** Origem do app (`window.location.origin`) — os links do arquivo precisam ser absolutos. */
  origin: string;
  geradoEm: Date;
  /** Preenchido só no retrato congelado, para o arquivo não se passar por leitura de hoje. */
  congeladoEm?: string | null;
  locale?: string;
}

const escapar = (v: unknown): string =>
  String(v ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const ORDEM_POSICOES = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

/**
 * Preenchimento da célula, a partir da posição na rampa (0 a 1).
 *
 * O DESTINO da rampa muda com o tema, e isso não é estética. O teal da marca (#2DD4BF) é uma cor
 * CLARA: no tema escuro, a célula clareia conforme o spot encarece, e a tinta clara em cima dela
 * colapsa — medi 2,27:1 no número grande e 1,77:1 no pequeno na célula mais cara, ou seja, o dado
 * sumia exatamente onde ele mais importa. Não é problema da cor do texto, é da rampa: nenhuma
 * tinta funciona numa faixa que atravessa o meio da escala de luminância.
 *
 * Então o tema escuro escurece em direção a um teal PROFUNDO, e o claro segue clareando em direção
 * ao teal da marca. Nos dois casos a célula anda para longe da tinta, nunca na direção dela.
 */
const preenchimento = (p: number) =>
  `color-mix(in oklab, var(--cel-alvo) ${(8 + p * 84).toFixed(1)}%, transparent)`;

const pct = (x: { n: number; erros: number }): number | null =>
  x.n ? Math.round((x.erros / x.n) * 100) : null;

const fmtData = (d: Date, locale: string): string => {
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: "long", timeStyle: "short" }).format(d);
  } catch {
    return d.toISOString().slice(0, 16).replace("T", " ");
  }
};

/** `grindlab-evolucao-2026-07-28.html` — data no nome porque o valor do arquivo é ser um retrato. */
export function evolutionFileName(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `grindlab-evolucao-${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}.html`;
}

export function buildEvolutionHtml(input: EvolutionExportInput): string {
  const { data, proof, t, spotLabel, origin, geradoEm, congeladoEm } = input;
  const locale = input.locale || "pt-BR";
  const base = origin.replace(/\/+$/, "");

  const resumo = data?.resumo;
  const bb = resumo?.bb_por_torneio;
  const delta = resumo?.delta;

  // ── 1 · o número que resume o período ──────────────────────────────────────────────────
  const heroBloco = bb == null
    ? `<p class="vazio">${escapar(t("empty"))}</p>`
    : `<div class="hero">
         <div>
           <div class="hero-num">-${bb.toFixed(1)}<span class="hero-un">${escapar(t("perTournament"))}</span></div>
           ${delta == null ? "" : `<span class="pill ${delta < 0 ? "bom" : delta > 0 ? "ruim" : ""}">${
             delta < 0 ? "&#9660;" : delta > 0 ? "&#9650;" : "&#8212;"
           } ${Math.abs(delta).toFixed(1)}bb ${escapar(t("vsPrevious"))}</span>`}
         </div>
         <p class="hero-hint">${escapar(t("heroHint", { n: resumo?.n_torneios ?? 0 }))}</p>
       </div>`;

  // ── 2 · os spots que mais custaram ─────────────────────────────────────────────────────
  const spots = data?.top_spots ?? [];
  const spotsBloco = !spots.length ? "" : `
    <section class="card">
      <h2>${escapar(t("costly.title"))}</h2>
      <p class="sub">${escapar(t("costly.subtitle"))}</p>
      <ol class="spots">
        ${spots.map((s, i) => `
          <li>
            <span class="idx">${i + 1}</span>
            <span class="spot-main">
              <a href="${base}/replayer?t=${encodeURIComponent(s.ext)}&amp;h=${encodeURIComponent(s.hand_id)}">
                ${/* `formatAction` e não o valor cru: o banco guarda "allin", e o vocabulário
                      visível do produto é "Shove". Um arquivo que o jogador guarda no disco não
                      pode ser a única superfície que fala outra língua. */""}
                ${escapar(t("costly.played", {
                  action: formatAction(s.action),
                  best: s.best_action ? formatAction(s.best_action) : "—",
                }))}
              </a>
              <span class="spot-meta">${escapar(s.street)} &middot; ${escapar(s.position ?? "")}${
                s.vs_position ? ` vs ${escapar(s.vs_position)}` : ""} &middot; ${escapar(s.stack_bb)}bb</span>
            </span>
            <span class="spot-ev">-${s.ev_loss_bb.toFixed(1)}bb</span>
          </li>`).join("")}
      </ol>
    </section>`;

  // ── 3 · matriz posição × profundidade ──────────────────────────────────────────────────
  const matriz = data?.matriz ?? [];
  let matrizBloco = "";
  if (matriz.length) {
    const buckets = [...new Set(matriz.map((c) => c.bucket))]
      .sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
    const grade = new Map(matriz.map((c) => [`${c.position}|${c.bucket}`, c]));
    const posicoes = ORDEM_POSICOES.filter((p) => matriz.some((c) => c.position === p));
    const max = Math.max(...matriz.map((c) => c.bb_100 ?? 0), 1);

    const linhas = posicoes.map((p) => `
      <tr>
        <th scope="row">${escapar(p)}</th>
        ${buckets.map((b) => {
          const c = grade.get(`${p}|${b}`);
          // Célula sem dado NUNCA vira 0 — a regra que o mapa de calor mais convida a quebrar.
          if (!c || c.bb_100 == null) return `<td class="vaz">${escapar(t("matrix.empty"))}</td>`;
          return `<td style="background:${preenchimento(Math.min(c.bb_100 / max, 1))}">
                    <b>${c.bb_100.toFixed(1)}</b><i>${c.n}</i>
                  </td>`;
        }).join("")}
      </tr>`).join("");

    // CHAVE DE LEITURA acima da grade — cada quadrante tem DOIS números e nada dizia o que é cada
    // um. A legenda de rodapé chegava tarde: num mapa de calor a pessoa interpreta os números antes
    // de rolar até o fim. E aqui isso pesa mais que na tela, porque quem abre o arquivo meses
    // depois não tem ninguém para perguntar.
    const chave = `
      <div class="chave">
        <div class="chave-item">
          <div class="chave-cel" style="background:${preenchimento(0.55)}"><b>5.2</b><i>66</i></div>
          <div class="chave-txt">
            <div><b>5.2</b> &middot; ${escapar(t("matrix.keyTop"))}</div>
            <div><b>66</b> &middot; ${escapar(t("matrix.keyBottom"))}</div>
          </div>
        </div>
        <div class="chave-item">
          <div class="chave-cel vaz">${escapar(t("matrix.empty"))}</div>
          <div class="chave-txt">${escapar(t("matrix.keyEmpty"))}</div>
        </div>
      </div>`;

    matrizBloco = `
      <section class="card">
        <h2>${escapar(t("matrix.title"))}</h2>
        <p class="sub">${escapar(t("matrix.subtitle"))}</p>
        ${chave}
        <div class="rolagem">
          <table class="matriz">
            <thead><tr><td></td>${buckets.map((b) => `<th scope="col">${escapar(b)}</th>`).join("")}</tr></thead>
            <tbody>${linhas}</tbody>
          </table>
        </div>
        <p class="legenda">${escapar(t("matrix.legend"))}</p>
      </section>`;
  }

  // ── 4 · antes e depois ─────────────────────────────────────────────────────────────────
  const provas = (proof ?? []).filter((p) => p.validacao && p.validacao.veredito !== "sem_amostra");
  const provaBloco = !provas.length ? "" : `
    <section class="card">
      <h2>${escapar(t("proof.title"))}</h2>
      <p class="sub">${escapar(t("proof.subtitle"))}</p>
      ${provas.map((p) => {
        const v = p.validacao!;
        const ic = v.ic_diferenca;
        const acoes = (p.acoes ?? []).filter((a) => a.n > 0);
        const somar = (f: (a: { acao: string }) => boolean) =>
          acoes.filter(f).reduce((s, a) => ({ n: s.n + a.n, erros: s.erros + a.erros }),
                                 { n: 0, erros: 0 });
        const agindo = somar((a) => a.acao !== "fold");
        const passando = somar((a) => a.acao === "fold");
        const puro = p.pureza?.puro ?? { n: 0, erros: 0 };
        const misto = p.pureza?.misto ?? { n: 0, erros: 0 };
        const cls = v.veredito === "melhorou" ? "bom" : v.veredito === "piorou" ? "ruim" : "";

        return `
        <article class="prova">
          <header>
            <b>${escapar(spotLabel(p.familia ?? p.category_key, { stack: false, fallback: p.category_key }))}</b>
            <span class="taxas">
              <span class="antes">${v.taxa_antes}%</span> &rarr;
              <span class="depois ${cls}">${v.taxa_depois}%</span>
              <span class="n">(${v.n_depois})</span>
            </span>
          </header>
          ${/* Veredito em linguagem comum primeiro; o intervalo de confiança desce para o rodapé
                técnico. Quem lê este relatório está evoluindo, não auditando: precisa saber antes
                de tudo se melhorou, e só depois com que evidência. */""}
          <p>${escapar(t(`proof.explain.${v.veredito}`, {
            antes: v.taxa_antes, ajustado: v.taxa_antes_ajustada ?? v.taxa_antes,
            depois: v.taxa_depois, n: v.n_depois,
          }))}</p>
          ${ic ? `<p class="tecnico">${escapar(t("proof.technical", {
            lo: ic[0], hi: ic[1], n: v.n_depois,
            ajustado: v.taxa_antes_ajustada ?? v.taxa_antes,
          }))}</p>` : ""}

          ${/* PURO como taxa. MISTO nunca como taxa — ver o cabeçalho deste arquivo. */ ""}
          ${puro.n > 0 ? `
            <div class="puro">
              <span class="puro-num ${puro.erros === 0 ? "neutro" : "ruim"}">${pct(puro)}%</span>
              <span class="puro-frac">${puro.erros}/${puro.n}</span>
              <span class="puro-txt">${escapar(t("proof.purity.pure"))}</span>
            </div>` : ""}
          <p class="nota">${escapar(t(puro.erros > 0 ? "proof.purityHintErrs" : "proof.purityHint"))}</p>
          ${misto.n > 0 ? `<p class="nota">${escapar(t("proof.mixedNote", { erros: misto.erros, n: misto.n }))}</p>` : ""}

          ${(agindo.n > 0 || passando.n > 0) ? `<p class="mono nota">${escapar(t("proof.commission", {
            agindo: pct(agindo) ?? "—", nAgindo: agindo.n,
            passando: pct(passando) ?? "—", nPassando: passando.n,
          }))}</p>` : ""}

          ${acoes.length ? `
            <p class="rotulo">${escapar(t("proof.byAction"))}</p>
            <ul class="acoes">
              ${acoes.map((a) => {
                const q = a.n ? Math.round((a.erros / a.n) * 100) : 0;
                return `<li><span>${escapar(t(`proof.action.${a.acao}`, { defaultValue: a.acao }))}</span>
                        <span class="${a.erros === 0 ? "neutro" : q >= 50 ? "ruim" : "alerta"}">${a.erros}/${a.n}${
                          a.erros > 0 ? ` &middot; ${q}%` : ""}</span></li>`;
              }).join("")}
            </ul>` : ""}
        </article>`;
      }).join("")}
      <p class="legenda">${escapar(t("proof.disclaimer"))}</p>
    </section>`;

  const titulo = t("export.docTitle");
  const carimbo = congeladoEm
    ? t("export.snapshotOf", { date: congeladoEm })
    : t("export.generatedAt", { date: fmtData(geradoEm, locale) });

  return `<!doctype html>
<html lang="${escapar(locale)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapar(titulo)}</title>
<style>
  :root {
    --bg:#0A0E1A; --surface:#111726; --line:#222C42; --ink:#E3E8EC; --ink-2:#9AA8BC;
    --ink-3:#6B7A91; --accent:#2DD4BF; --bom:#2DD4BF; --alerta:#F5A524; --ruim:#F0616D;
    --logo-ink:#E3E8EC; --logo-sub:#2A4652; --cel-alvo:#0B6B61;
    --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    --mono:ui-monospace,"SF Mono","Cascadia Mono",Consolas,monospace;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#F4F7F9; --surface:#FFF; --line:#D6DEE7; --ink:#0F1724; --ink-2:#4A5A70;
            --ink-3:#75859B; --accent:#0E9384; --bom:#0E9384; --alerta:#B06A00; --ruim:#C6394A;
            --logo-ink:#0F1724; --logo-sub:#4A5A70; --cel-alvo:#2DD4BF; }
  }

  /* O LOGOTIPO SEGUE O FUNDO, e o asset da marca continua intocado.
     O SVG da marca é desenhado para fundo ESCURO: a palavra "Grind" é #E3E8EC, a cor de tinta
     clara. Num documento que o navegador pode abrir em tema claro — ou que vai para o papel, que
     é sempre branco — esse cinza fica quase invisível. Recolorir o arquivo de marca resolveria
     aqui e quebraria em todo lugar onde o fundo É escuro, então a troca é por CONTEXTO: o seletor
     casa o valor original do atributo fill e a variável decide qual tinta usar. Regra de CSS
     sempre vence atributo de apresentação, então basta isto — nada de segunda versão do logo.
     (Sem crase neste comentário: ele mora dentro de um template literal.) */
  .marca svg [fill="#E3E8EC"] { fill: var(--logo-ink); }
  .marca svg [fill="#2A4652"] { fill: var(--logo-sub); }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
         line-height:1.55; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:940px; margin:0 auto; padding:36px 20px 64px;
          display:flex; flex-direction:column; gap:22px; }
  .marca { display:flex; align-items:center; justify-content:space-between; gap:16px;
           flex-wrap:wrap; padding-bottom:18px; border-bottom:1px solid var(--line); }
  .marca svg { height:38px; width:auto; display:block; }
  .carimbo { font-family:var(--mono); font-size:12px; color:var(--ink-3); text-align:right; }
  h1 { font-size:clamp(22px,3.4vw,30px); line-height:1.15; margin:8px 0 4px;
       letter-spacing:-.02em; font-weight:800; }
  h2 { font-size:16px; font-weight:700; margin:0 0 3px; letter-spacing:-.01em; }
  .sub, .nota, .legenda { color:var(--ink-2); font-size:12.5px; margin:0; }
  .legenda { color:var(--ink-3); font-size:11px; margin-top:10px; }
  .card { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:18px; }
  .vazio { color:var(--ink-2); font-size:14px; margin:0; }

  .hero { display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:18px; }
  .hero-num { font-family:var(--mono); font-size:clamp(34px,6vw,48px); font-weight:800;
              line-height:1; font-variant-numeric:tabular-nums; }
  .hero-un { font-size:13px; font-weight:600; color:var(--ink-2); margin-left:8px; }
  .hero-hint { max-width:44ch; color:var(--ink-2); font-size:12.5px; margin:0; }
  .pill { display:inline-block; margin-top:10px; border:1px solid var(--line); border-radius:999px;
          padding:2px 10px; font-family:var(--mono); font-size:11.5px; font-weight:700; color:var(--ink-2); }
  .pill.bom { border-color:var(--bom); color:var(--bom); }
  .pill.ruim { border-color:var(--ruim); color:var(--ruim); }

  .spots { list-style:none; margin:10px 0 0; padding:0; }
  .spots li { display:flex; align-items:center; gap:12px; padding:9px 0; border-top:1px solid var(--line); }
  .spots li:first-child { border-top:0; }
  .idx { font-family:var(--mono); font-size:11px; color:var(--ink-3); width:16px; }
  .spot-main { flex:1; min-width:0; }
  .spot-main a { color:var(--ink); text-decoration:none; font-size:13px; font-weight:600; }
  .spot-main a:hover { color:var(--accent); text-decoration:underline; }
  .spot-meta { display:block; font-family:var(--mono); font-size:11px; color:var(--ink-3); }
  .spot-ev { font-family:var(--mono); font-size:13.5px; font-weight:700; color:var(--ruim);
             font-variant-numeric:tabular-nums; }

  .rolagem { overflow-x:auto; }
  .matriz { border-collapse:separate; border-spacing:3px; margin-top:10px; width:100%; min-width:420px; }
  .matriz th[scope=col] { font-family:var(--mono); font-size:10px; font-weight:500; color:var(--ink-3); padding-bottom:2px; }
  .matriz th[scope=row] { font-family:var(--mono); font-size:11px; font-weight:500; color:var(--ink-3);
                          text-align:right; padding-right:6px; width:56px; }
  .matriz td { border-radius:6px; text-align:center; padding:7px 4px; }
  .matriz td b { display:block; font-family:var(--mono); font-size:12px; font-weight:700; color:var(--ink); }
  /* Tinta principal com opacidade, e NÃO a secundária: o cinza de --ink-2 é calibrado contra o
     fundo da PÁGINA, e estes números moram sobre um preenchimento teal. Com ele o contraste caía
     para perto de 1,3:1, e piorava conforme a célula escurece — o tamanho da amostra sumia
     justamente nos spots mais caros, que são os que mais precisam dele para se saber se a leitura
     tem lastro. (Nenhuma crase em comentário daqui: tudo isto vive dentro de um template literal.) */
  .matriz td i { display:block; font-family:var(--mono); font-size:9px; font-style:normal;
                 color:var(--ink); opacity:.85; }
  .matriz td.vaz { border:1px dashed var(--line); font-family:var(--mono); font-size:10px; color:var(--ink-3); }

  .chave { display:flex; flex-wrap:wrap; gap:10px 26px; background:var(--bg); border-radius:9px;
           padding:11px; margin:11px 0 0; }
  .chave-item { display:flex; align-items:center; gap:10px; }
  .chave-cel { width:54px; padding:6px 0; border-radius:6px; text-align:center; flex:none; }
  .chave-cel b { display:block; font-family:var(--mono); font-size:12px; color:var(--ink); }
  .chave-cel i { display:block; font-family:var(--mono); font-size:9px; font-style:normal;
                 color:var(--ink); opacity:.85; }
  .chave-cel.vaz { border:1px dashed var(--line); font-family:var(--mono); font-size:10px;
                   color:var(--ink-3); padding:11px 0; }
  .chave-txt { font-size:10.5px; line-height:1.4; color:var(--ink-2); max-width:34ch; }
  .chave-txt b { font-family:var(--mono); color:var(--ink); }

  .prova { border:1px solid var(--line); border-radius:10px; padding:13px; margin-top:10px; }
  .prova header { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between;
                  gap:8px; margin-bottom:7px; font-size:12.5px; }
  .taxas { font-family:var(--mono); font-size:11.5px; color:var(--ink-2); }
  .taxas .depois { font-weight:700; color:var(--ink); }
  .taxas .depois.bom { color:var(--bom); } .taxas .depois.ruim { color:var(--ruim); }
  .prova p { font-size:12px; color:var(--ink-2); margin:0 0 7px; }
  .prova p.tecnico { font-family:var(--mono); font-size:10px; color:var(--ink-3); }
  .puro { display:flex; align-items:baseline; flex-wrap:wrap; gap:8px; background:var(--bg);
          border:1px solid var(--line); border-radius:8px; padding:10px; margin:0 0 7px; }
  .puro-num { font-family:var(--mono); font-size:22px; font-weight:800; font-variant-numeric:tabular-nums; }
  .puro-frac { font-family:var(--mono); font-size:11px; color:var(--ink-3); }
  .puro-txt { flex:1 1 100%; font-size:11.5px; color:var(--ink-2); }
  .rotulo { font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:.08em;
            color:var(--ink-3); margin:9px 0 4px; }
  .acoes { list-style:none; margin:0; padding:0; font-family:var(--mono); font-size:11.5px; }
  .acoes li { display:flex; justify-content:space-between; gap:10px; padding:1.5px 0; }
  .mono { font-family:var(--mono); font-size:11px; }
  .neutro { color:var(--ink-3); } .alerta { color:var(--alerta); } .ruim { color:var(--ruim); }
  .bom { color:var(--bom); }

  .rodape { border-top:1px solid var(--line); padding-top:16px; font-size:11.5px; color:var(--ink-3); }
  .rodape ul { margin:6px 0 0; padding-left:18px; }
  .rodape li { margin-bottom:3px; }
  .rodape a { color:var(--accent); }

  /* Impressão: fundo claro, sem quebrar bloco no meio. Relatório guardado costuma virar papel. */
  @media print {
    :root { --bg:#FFF; --surface:#FFF; --line:#CBD5E1; --ink:#0F1724; --ink-2:#3E4C61; --ink-3:#64748B;
            --logo-ink:#0F1724; --logo-sub:#4A5A70; --cel-alvo:#2DD4BF; }
    body { background:#FFF; }
    .wrap { padding:0; max-width:none; }
    .card, .prova { break-inside:avoid; page-break-inside:avoid; }
  }
</style>
</head>
<body>
<div class="wrap">

  <header class="marca">
    ${logoSvg}
    <div class="carimbo">${escapar(carimbo)}</div>
  </header>

  <div>
    <h1>${escapar(t("title"))}</h1>
    <p class="sub">${escapar(t("subtitle"))}</p>
  </div>

  <section class="card">${heroBloco}</section>
  ${spotsBloco}
  ${matrizBloco}
  ${provaBloco}

  <footer class="rodape">
    <b>${escapar(t("export.notesTitle"))}</b>
    <ul>
      <li>${escapar(t("export.noteScope"))}</li>
      <li>${escapar(t("export.noteEv"))}</li>
      <li>${escapar(t("export.noteIcm"))}</li>
      <li>${escapar(t("export.noteFrozen"))}</li>
    </ul>
    <p style="margin-top:12px"><a href="${base}/evolucao">${escapar(t("export.openApp"))}</a></p>
  </footer>

</div>
</body>
</html>`;
}

/** Dispara o download. Separado do builder porque o builder é puro e testável, e isto não é. */
export function baixarHtml(html: string, nomeArquivo: string): void {
  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revogar na hora cancela o download em alguns navegadores; o tick seguinte já é seguro.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
