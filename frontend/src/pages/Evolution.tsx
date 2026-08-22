import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
// `Map as MapIcon` NÃO é preferência de estilo: importar `Map` cru sombreia o construtor global,
// e o `new Map(...)` do heatmap vira "TypeError: Map is not a constructor" — em RUNTIME, com a
// tela em branco. Nem o `tsc` nem o build pegam, porque o nome é válido nos dois mundos.
import { TrendingDown, TrendingUp, Minus, ArrowRight, ArrowLeft, ChevronRight, Camera, Download, Map as MapIcon } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { evolution, training, type EvolutionReport, type TrainingProofItem } from "@/lib/api";
import { useSpotLabel } from "@/lib/spotLabel";
import { formatApiDate } from "@/lib/apiDate";
import { buildEvolutionHtml, evolutionFileName, baixarHtml } from "@/lib/evolutionExport";
import { cn, formatAction } from "@/lib/utils";

/**
 * Relatório de evolução — a superfície de REFLEXÃO.
 *
 * A tela de treino responde "o que faço agora" e é de ação: abre, clica, sai. Esta responde "como
 * estou indo" e é lida devagar. Misturar as duas piora as duas — quem vai drilar não deve rolar
 * por gráficos até achar o botão, e quem quer refletir não consegue no meio de CTAs.
 *
 * A ordem dos blocos é a decisão de design mais importante aqui, e ela é deliberada:
 *
 *   custo → onde dói → onde melhorou
 *
 * Ranquear por TAXA DE ERRO manda o jogador para o lugar errado: errar 29% de um spot que custa
 * 0,08bb importa menos que errar 6% de um que custa 4bb. Por isso o topo é bb perdidos, e a taxa
 * de erro aparece só no bloco de validação — lá ela é a medida certa, porque é binomial e estável,
 * e a pergunta é outra ("melhorei?", não "no que mexo?").
 */
export default function Evolution() {
  const { t, i18n } = useTranslation("evolution");
  // Fonte ÚNICA do rótulo do spot, a mesma do Training — se cada tela montasse o seu, o mesmo
  // leak apareceria com nomes diferentes em lugares diferentes.
  const spotLabel = useSpotLabel();

  // `/evolucao/:reportId` mostra um RETRATO CONGELADO com a MESMA tela do relatório vivo. Renderizar
  // o passado num layout próprio seria o erro: comparar julho com agosto exige que os dois tenham a
  // mesma forma, senão a diferença que salta aos olhos é a do desenho, não a do jogo.
  const { reportId } = useParams();
  const congelado = !!reportId;

  const vivo = useQuery({
    queryKey: ["evolution"], queryFn: evolution.report, enabled: !congelado,
  });
  const proofVivo = useQuery({
    queryKey: ["training-proof"], queryFn: training.proof, enabled: !congelado,
  });
  const retrato = useQuery({
    queryKey: ["evolution-snapshot", reportId],
    queryFn: () => evolution.snapshot(Number(reportId)),
    enabled: congelado,
  });

  const data = congelado ? retrato.data?.snapshot : vivo.data;
  const proof = (congelado ? retrato.data?.snapshot?.proof : proofVivo.data?.proof) ?? [];
  const isLoading = congelado ? retrato.isLoading : vivo.isLoading;

  const resumo = data?.resumo;
  const delta = resumo?.delta;
  const bb = resumo?.bb_por_torneio;

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="space-y-4">

        {/* Voltar no TOPO. O link para o treino já existia no rodapé, mas esta é uma tela longa
            (quatro blocos e uma tabela): quem entra pelo dashboard e quer sair precisa rolar tudo
            até achar a saída. Saída de tela longa fica onde a pessoa já está olhando. */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link to={congelado ? "/evolucao" : "/training"}
            className="inline-flex items-center gap-1.5 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" aria-hidden />
            {congelado ? t("snapshot.back") : t("back")}
          </Link>

          {/* O arquivo sai dos MESMOS objetos que a tela acabou de renderizar (`data` e `proof`),
              e por isso não pode divergir dela. Só aparece com dado medido: um HTML com "—" em
              tudo não é relatório, é frustração com nome de arquivo. */}
          {!isLoading && data?.resumo?.bb_por_torneio != null && (
            <button type="button"
              onClick={() => baixarHtml(
                buildEvolutionHtml({
                  data, proof, t, spotLabel,
                  origin: window.location.origin,
                  geradoEm: new Date(),
                  congeladoEm: congelado ? formatApiDate(retrato.data?.created_at) : null,
                  locale: i18n.language,
                }),
                evolutionFileName(new Date()))}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 font-mono text-[11px] font-bold text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary">
              <Download className="size-3.5" aria-hidden />
              {t("export.button")}
            </button>
          )}
        </div>

        {/* Faixa de retrato congelado. Sem ela, a tela mostraria números antigos com a cara do
            relatório atual — e o jogador tomaria decisão sobre dado velho achando que é de hoje. */}
        {congelado && retrato.data && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/[0.07] px-4 py-2.5">
            <Camera className="size-4 shrink-0 text-amber-400" aria-hidden />
            <span className="text-[12px] leading-snug text-foreground">
              {t("snapshot.banner", { date: formatApiDate(retrato.data.created_at) ?? "—" })}
            </span>
            <Link to="/evolucao" className="ml-auto text-[11px] font-bold text-primary hover:underline">
              {t("snapshot.viewLive")}
            </Link>
          </div>
        )}

        {/* ── 1 · O número que resume o período ─────────────────────────────────────
            bb por torneio, e não acurácia: é a métrica que o jogador compara com o próprio
            buy-in. Acurácia sobe sem o dinheiro mudar, quando os erros que somem são baratos. */}
        <div className="rounded-2xl border border-border bg-card/40 p-5">
          {isLoading ? (
            <div className="h-16 animate-pulse rounded-xl bg-muted/10" />
          ) : bb == null ? (
            <p className="text-sm text-muted-foreground">{t("empty")}</p>
          ) : (
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="font-mono text-4xl font-bold tabular-nums text-foreground sm:text-5xl">
                  -{bb.toFixed(1)}
                  <span className="ml-2 text-sm font-semibold text-muted-foreground">
                    {t("perTournament")}
                  </span>
                </div>
                {delta != null && (
                  <span className={cn(
                    "mt-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-xs font-bold",
                    delta < 0 ? "border-emerald-500/40 text-emerald-400"
                      : delta > 0 ? "border-red-500/40 text-red-400"
                      : "border-border text-muted-foreground")}>
                    {delta < 0 ? <TrendingDown className="size-3.5" aria-hidden />
                      : delta > 0 ? <TrendingUp className="size-3.5" aria-hidden />
                      : <Minus className="size-3.5" aria-hidden />}
                    {Math.abs(delta).toFixed(1)}bb {t("vsPrevious")}
                  </span>
                )}
              </div>
              <p className="max-w-[42ch] text-[13px] leading-snug text-muted-foreground">
                {t("heroHint", { n: resumo?.n_torneios ?? 0 })}
              </p>
            </div>
          )}
        </div>

        {/* ── 2 · Os spots que mais custaram ────────────────────────────────────────
            A cauda pesada, que a média esconde: em MTT três mãos decidem o torneio. Cada linha
            abre a mão no Replayer — sem isso o jogador lê e não faz nada. */}
        {!!data?.top_spots?.length && (
          <div className="rounded-2xl border border-border bg-card/40 p-5">
            <h2 className="mb-1 font-heading text-base font-bold text-foreground">{t("costly.title")}</h2>
            <p className="mb-3 text-[11px] leading-snug text-muted-foreground">{t("costly.subtitle")}</p>
            <div className="divide-y divide-border">
              {data.top_spots.map((s, i) => (
                <Link key={`${s.ext}-${s.hand_id}`}
                  to={`/replayer?t=${encodeURIComponent(s.ext)}&h=${encodeURIComponent(s.hand_id)}`}
                  className="group flex items-center gap-3 py-2.5 transition-colors hover:bg-background/40">
                  <span className="w-5 shrink-0 text-center font-mono text-[11px] text-muted-foreground">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold text-foreground">
                      {/* O banco guarda "allin"; o vocabulário visível do produto é "Shove". Esta
                          tela era a única que renderizava o valor cru — `formatAction` é a fonte
                          única do rótulo, e onze outros arquivos já a usavam. */}
                      {t("costly.played", {
                        action: formatAction(s.action),
                        best: s.best_action ? formatAction(s.best_action) : "—",
                      })}
                    </span>
                    <span className="block truncate font-mono text-[11px] text-muted-foreground">
                      {s.street} · {s.position}{s.vs_position ? ` vs ${s.vs_position}` : ""} · {s.stack_bb}bb
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="block font-mono text-sm font-bold tabular-nums text-red-400">
                      -{s.ev_loss_bb.toFixed(1)}bb
                    </span>
                    <span className="flex items-center justify-end gap-0.5 text-[10px] text-muted-foreground group-hover:text-primary">
                      {t("costly.open")} <ArrowRight className="size-2.5" aria-hidden />
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* ── 3 · Matriz posição × profundidade ─────────────────────────────────────
            O gráfico mais nativo de poker do relatório: em MTT "abertura de botão" não é uma
            habilidade — a 50bb é range, a 12bb é shove. As faixas são as MESMAS do solver, então
            cada célula corresponde a uma profundidade que ele trata como uma só. */}
        {!!data?.matriz?.length && <Matriz matriz={data.matriz} />}

        {/* ── 4 · Antes e depois ────────────────────────────────────────────────────
            Aqui, e só aqui, a métrica é TAXA DE ERRO — binomial, estável, com intervalo. É a
            medida certa para "melhorei?", e a errada para "no que mexo?". */}
        {!!proof.length && (
          <div className="rounded-2xl border border-border bg-card/40 p-5">
            <h2 className="mb-1 font-heading text-base font-bold text-foreground">{t("proof.title")}</h2>
            <p className="mb-3 text-[11px] leading-snug text-muted-foreground">{t("proof.subtitle")}</p>
            <div className="space-y-2">
              {proof
                .filter((p) => p.validacao && p.validacao.veredito !== "sem_amostra")
                .map((p) => (
                  <LinhaProva key={p.category_key} p={p} spotLabel={spotLabel} />
                ))}
            </div>
            <p className="mt-3 text-[10px] leading-snug text-muted-foreground">{t("proof.disclaimer")}</p>
          </div>
        )}

        {/* ── 5 · Retratos datados ──────────────────────────────────────────────────
            O valor de congelar é poder comparar julho com agosto: um número que muda sozinho não
            serve para comparação. Some quando não há histórico — um bloco vazio dizendo "nenhum
            relatório ainda" só ocupa espaço numa tela que já é longa. */}
        {!congelado && <Historico />}

        {!congelado && (
          <Link to="/training"
            className="flex items-center justify-center gap-1.5 rounded-2xl border border-border bg-card/40 p-4 text-[12px] font-bold text-primary transition-colors hover:border-primary/40">
            <MapIcon className="size-4" aria-hidden /> {t("backToTraining")}
          </Link>
        )}
      </div>
    </HudLayout>
  );
}

/**
 * Uma linha de antes/depois, com o detalhe atrás de um expansor.
 *
 * Duas coisas que o número sozinho não conta, e que a auditoria da tela expôs:
 *
 * 1. **O rótulo não cita profundidade.** A `category_key` carrega o stack em que o TREINO
 *    acontece, mas o filtro da MEDIÇÃO o ignora — rotular "Abertura de UTG+1 · 50bb" para um
 *    número medido em todas as profundidades é afirmar precisão que não existe.
 *
 * 2. **A taxa agregada dilui.** Em RFI ~84% das decisões são folds triviais. Um "8,1% → 0%"
 *    verdadeiro pode significar "acertei 50 folds óbvios" enquanto o limp de posição inicial erra
 *    3 de 3. A quebra por ação é o que transforma o número em diagnóstico, e é justamente o que
 *    faz o jogador confiar quando o resultado o surpreende.
 *
 * Expansor e não tooltip: o conteúdo é rico demais para um `title`, e tooltip não existe no toque.
 */
function LinhaProva({ p, spotLabel }: {
  p: TrainingProofItem;
  spotLabel: ReturnType<typeof useSpotLabel>;
}) {
  const { t } = useTranslation("evolution");
  const v = p.validacao!;
  const melhorou = v.veredito === "melhorou";
  const piorou = v.veredito === "piorou";
  const acoes = (p.acoes ?? []).filter((a) => a.n > 0);
  const ic = v.ic_diferenca;

  // AGINDO × PASSANDO, e deliberadamente NÃO "trivial × real".
  //
  // Fold não é sinônimo de trivial: 4 dos 128 folds de UTG+1 eram mãos que deviam abrir — leak de
  // aperto, erro de verdade. E foldar A5s numa profundidade limítrofe é decisão, não automatismo.
  // Separar por pureza da estratégia (100% × mista) seria o critério certo, mas o banco só guarda
  // `gto_label`, que é a faixa de frequência da AÇÃO JOGADA, não a pureza do spot.
  //
  // Então o corte é pelo que os dados sustentam: onde você AGIU (comissão) e onde PASSOU
  // (omissão). São erros diferentes, pedem treino diferente, e nenhum dos dois é descartável.
  const somar = (f: (a: { acao: string }) => boolean) =>
    acoes.filter(f).reduce((s, a) => ({ n: s.n + a.n, erros: s.erros + a.erros }), { n: 0, erros: 0 });
  const agindo = somar((a) => a.acao !== "fold");
  const passando = somar((a) => a.acao === "fold");
  const pct = (x: { n: number; erros: number }) => (x.n ? Math.round((x.erros / x.n) * 100) : null);
  const pctAgindo = pct(agindo);

  // PUREZA — o corte que muda a conduta. Vazio para decisões sem `gto_top_freq` (sem cobertura
  // ou anteriores ao backfill): elas ficam fora dos dois lados em vez de virar "puro" por omissão.
  const puro = p.pureza?.puro ?? { n: 0, erros: 0 };
  const misto = p.pureza?.misto ?? { n: 0, erros: 0 };

  // Só destaca no cabeçalho quando a diferença muda a leitura — senão vira ruído em toda linha.
  const destacaAgindo =
    pctAgindo !== null && agindo.n >= 5 && v.taxa_depois != null &&
    pctAgindo - v.taxa_depois >= 10;

  return (
    <details className="group rounded-xl bg-background/60 ring-1 ring-border">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 p-3">
        <span className="flex items-center gap-1.5 text-[12px] font-bold text-foreground">
          <ChevronRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden />
          {/* `familia` (sem stack) é a chave que a medição usa; a category_key fica de reserva. */}
          {spotLabel(p.familia ?? p.category_key, { stack: false, fallback: p.category_key })}
        </span>
        <span className="flex items-center gap-3 font-mono text-[11px]">
          <span className="text-muted-foreground">{v.taxa_antes}%</span>
          <ArrowRight className="size-3 text-muted-foreground/50" aria-hidden />
          <span className={cn("font-bold",
            melhorou ? "text-emerald-400" : piorou ? "text-red-400" : "text-foreground")}>
            {v.taxa_depois}%
          </span>
          <span className="text-muted-foreground">({v.n_depois})</span>
          {/* O número que muda a decisão do jogador, quando o agregado o esconde. */}
          {destacaAgindo && (
            <span className="rounded-full border border-amber-500/40 px-2 py-0.5 text-[10px] font-bold text-amber-400">
              {t("proof.actingBadge", { pct: pctAgindo })}
            </span>
          )}
        </span>
      </summary>

      <div className="space-y-3 border-t border-border px-3 pb-3 pt-2.5 text-[11px] leading-snug">
        {/* O veredito em PORTUGUÊS COMUM, e o intervalo de confiança fora dele.
            A versão anterior abria com "De 14.6% (ajustado para 14.3%) para 16% em 75 decisões. O
            intervalo de 95% é [-13 · 8.8] e cruza o zero" — quatro números e dois termos de
            estatística antes de qualquer significado. Quem lê este relatório está evoluindo, não
            auditando: precisa saber PRIMEIRO se melhorou, e só depois com que evidência. A conta
            não some, desce para o rodapé técnico, para quem quiser conferir. */}
        <p className="text-muted-foreground">
          {t(`proof.explain.${v.veredito}`, {
            antes: v.taxa_antes, ajustado: v.taxa_antes_ajustada ?? v.taxa_antes,
            depois: v.taxa_depois, n: v.n_depois,
          })}
        </p>
        {ic && (
          <p className="font-mono text-[10px] leading-snug text-muted-foreground/70">
            {t("proof.technical", {
              lo: ic[0], hi: ic[1], n: v.n_depois,
              ajustado: v.taxa_antes_ajustada ?? v.taxa_antes,
            })}
          </p>
        )}

        {/* PUREZA primeiro: é o corte que muda a conduta.
            Errar spot puro significa não conhecer a range — grave, e o mais barato de consertar.
            Errar spot misto é defensável, porque o próprio GTO mistura ali. Acertar spot puro não
            mede nada, e é a maioria das decisões de RFI. */}
        {/* PUREZA — e deliberadamente NÃO dois números lado a lado.
            A primeira versão desta tela mostrava as duas TAXAS em cartões gêmeos, e isso convida
            uma comparação que não se sustenta: "erro" é `played_freq < 0.25`, então num spot misto
            (55/45) AS DUAS ações passam e errar exige escolher uma terceira que o GTO nunca faz.
            O spot misto tem chance estruturalmente menor de ser marcado como erro. Ler "8,8% no
            misto contra 14,6% no puro" como "sou melhor no difícil" é confundir a régua com o
            resultado — e foi o que a tela sugeria.
            Agora só a taxa do PURO é apresentada como taxa (ali existe UMA resposta certa, e a
            medida é limpa). O misto vira contagem, com a explicação do porquê. */}
        {puro.n > 0 && (
          <div className="rounded-lg bg-card/60 p-3 ring-1 ring-border">
            <div className="flex items-baseline gap-2">
              <span className={cn("font-mono text-2xl font-bold tabular-nums",
                puro.erros === 0 ? "text-muted-foreground" : "text-red-400")}>
                {pct(puro)}%
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {puro.erros}/{puro.n}
              </span>
            </div>
            <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
              {t("proof.purity.pure")}
            </div>
          </div>
        )}
        <p className="text-muted-foreground">
          {t(puro.erros > 0 ? "proof.purityHintErrs" : "proof.purityHint")}
        </p>
        {misto.n > 0 && (
          <p className="text-muted-foreground">
            {t("proof.mixedNote", { erros: misto.erros, n: misto.n })}
          </p>
        )}

        {/* Comissão × omissão — a segunda leitura, mais discreta. */}
        {(agindo.n > 0 || passando.n > 0) && (
          <p className="font-mono text-[10px] text-muted-foreground">
            {t("proof.commission", {
              agindo: pct(agindo) ?? "—", nAgindo: agindo.n,
              passando: pct(passando) ?? "—", nPassando: passando.n,
            })}
          </p>
        )}

        {!!acoes.length && (
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {t("proof.byAction")}
            </p>
            <div className="space-y-1">
              {acoes.map((a) => {
                const pct = a.n ? Math.round((a.erros / a.n) * 100) : 0;
                return (
                  <div key={a.acao} className="flex items-center justify-between gap-2 font-mono">
                    <span className="text-foreground">{t(`proof.action.${a.acao}`, { defaultValue: a.acao })}</span>
                    <span className={cn("tabular-nums",
                      a.erros === 0 ? "text-muted-foreground"
                        : pct >= 50 ? "text-red-400" : "text-amber-400")}>
                      {a.erros}/{a.n} {a.erros > 0 && `· ${pct}%`}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </details>
  );
}

/** Histórico de retratos. Cada linha abre o snapshot daquele dia — números congelados, não a
 *  página: o visual pode melhorar sem invalidar relatório antigo.
 *
 *  A variação vem do próprio snapshot comparado ao anterior, e é o motivo de o histórico existir:
 *  a tela de cima mostra COMO VOCÊ ESTÁ, esta mostra PARA ONDE ESTÁ INDO. */
function Historico() {
  const { t } = useTranslation("evolution");
  const { data } = useQuery({ queryKey: ["evolution-history"], queryFn: evolution.history });
  const reports = data?.reports ?? [];
  if (!reports.length) return null;

  return (
    <div className="rounded-2xl border border-border bg-card/40 p-5">
      <h2 className="mb-1 font-heading text-base font-bold text-foreground">{t("history.title")}</h2>
      <p className="mb-3 text-[11px] leading-snug text-muted-foreground">{t("history.subtitle")}</p>
      <div className="divide-y divide-border">
        {reports.map((r) => (
          <Link key={r.id} to={`/evolucao/${r.id}`}
            className="group flex flex-wrap items-center justify-between gap-2 py-2.5 transition-colors hover:bg-background/40">
            <span className="font-mono text-[12px] text-foreground">
              {formatApiDate(r.created_at) ?? "—"}
            </span>
            <span className="flex items-center gap-3">
              <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {t(`history.motivo.${r.motivo}`, { defaultValue: r.motivo })}
              </span>
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {r.n_decisoes} {t("history.decisions")}
              </span>
              <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

/** Mapa de calor. Célula sem amostra fica VAZIA, nunca zero: ausência de dado e "você joga
 *  perfeito aqui" são coisas diferentes, e confundi-las é a mentira mais fácil de contar num
 *  mapa de calor. */
function Matriz({ matriz }: { matriz: EvolutionReport["matriz"] }) {
  const { t } = useTranslation("evolution");
  const ORDEM = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
  const buckets = [...new Set(matriz.map((c) => c.bucket))].sort(
    (a, b) => parseInt(a) - parseInt(b));
  const grade = new Map(matriz.map((c) => [`${c.position}|${c.bucket}`, c]));
  const posicoes = ORDEM.filter((p) => matriz.some((c) => c.position === p));
  const max = Math.max(...matriz.map((c) => c.bb_100 ?? 0), 1);

  const tom = (v: number) => {
    // Escala sequencial de UMA cor. Nunca arco-íris: aqui a cor codifica magnitude, e magnitude
    // tem ordem.
    //
    // O destino da rampa NÃO é o teal da marca, e isso não é escolha estética. `--primary` é uma
    // cor CLARA (hsl 172 66% 50%): num tema escuro a célula clareava conforme o spot encarecia, e
    // a tinta clara em cima dela colapsava — medido em 2,27:1 no número grande e 1,77:1 no
    // pequeno na célula mais cara. Ou seja, o dado sumia exatamente onde ele mais importa, e o
    // tamanho da amostra, que é o que diz se a leitura tem lastro, sumia primeiro.
    //
    // Trocar a cor do texto não resolveria: nenhuma tinta funciona numa rampa que atravessa o
    // meio da escala de luminância. Quem tem que mudar é a rampa, que agora ESCURECE em direção a
    // um teal profundo — a célula anda para longe da tinta, nunca na direção dela.
    const p = Math.min(v / max, 1);
    return { background: `color-mix(in oklab, #0B6B61 ${8 + p * 84}%, transparent)` };
  };

  return (
    <div className="rounded-2xl border border-border bg-card/40 p-5">
      <h2 className="mb-1 font-heading text-base font-bold text-foreground">{t("matrix.title")}</h2>
      <p className="mb-3 text-[11px] leading-snug text-muted-foreground">{t("matrix.subtitle")}</p>

      {/* CHAVE DE LEITURA, acima da grade e não no rodapé.
          Cada quadrante traz DOIS números e nada dizia o que era cada um. A legenda existia, mas
          embaixo, em cinza pequeno, e dizia "número menor" — que tanto lê como "o de valor menor"
          quanto "o de baixo". Num mapa de calor a pessoa interpreta os números ANTES de chegar ao
          rodapé, então a chave precisa vir antes, e apontar para uma célula de verdade em vez de
          descrever com palavras. O quadrante vazio entra na chave pelo mesmo motivo: sem amostra e
          jogo perfeito são coisas diferentes, e é a confusão mais fácil de cometer aqui. */}
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl bg-background/50 p-3">
        <div className="flex items-center gap-2.5">
          <div style={tom(max * 0.62)}
            className="flex aspect-[1.9] w-[54px] shrink-0 flex-col items-center justify-center rounded-md">
            <span className="font-mono text-[12px] font-bold text-foreground">5.2</span>
            <span className="font-mono text-[9px] text-foreground/85">66</span>
          </div>
          <div className="text-[10px] leading-tight text-muted-foreground">
            <div><span className="font-mono font-bold text-foreground">5.2</span> · {t("matrix.keyTop")}</div>
            <div className="mt-0.5"><span className="font-mono font-bold text-foreground">66</span> · {t("matrix.keyBottom")}</div>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="flex aspect-[1.9] w-[54px] shrink-0 items-center justify-center rounded-md border border-dashed border-border">
            <span className="font-mono text-[10px] text-muted-foreground/60">{t("matrix.empty")}</span>
          </div>
          <span className="max-w-[22ch] text-[10px] leading-tight text-muted-foreground">{t("matrix.keyEmpty")}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="grid gap-1"
          style={{ gridTemplateColumns: `60px repeat(${buckets.length}, minmax(58px, 1fr))`, minWidth: 420 }}>
          <div />
          {buckets.map((b) => (
            <div key={b} className="pb-1 text-center font-mono text-[10px] text-muted-foreground">{b}</div>
          ))}
          {posicoes.map((p) => (
            <FragmentRow key={p} pos={p} buckets={buckets} grade={grade} tom={tom} vazio={t("matrix.empty")} />
          ))}
        </div>
      </div>
      <p className="mt-3 font-mono text-[10px] text-muted-foreground">{t("matrix.legend")}</p>
    </div>
  );
}

function FragmentRow({ pos, buckets, grade, tom, vazio }: {
  pos: string; buckets: string[];
  grade: Map<string, EvolutionReport["matriz"][number]>;
  tom: (v: number) => React.CSSProperties; vazio: string;
}) {
  const { t } = useTranslation("evolution");
  return (
    <>
      <div className="flex items-center justify-end pr-2 font-mono text-[11px] text-muted-foreground">{pos}</div>
      {buckets.map((b) => {
        const c = grade.get(`${pos}|${b}`);
        return c && c.bb_100 != null ? (
          <div key={b} style={tom(c.bb_100)}
            title={t("celulaTitulo", { pos, bucket: b, bb: c.bb_100, n: c.n })}
            className="flex aspect-[1.9] flex-col items-center justify-center rounded-md">
            <span className="font-mono text-[12px] font-bold text-foreground">{c.bb_100.toFixed(1)}</span>
            {/* `foreground/70` e NÃO `muted-foreground`: aquele cinza (L 47%) é calibrado contra o
                fundo da PÁGINA, e aqui o fundo é um preenchimento teal. O contraste ficava perto
                de 1,3:1, e piorava justamente onde a célula é mais escura — ou seja, o tamanho da
                amostra sumia nos spots mais caros, que são os que mais precisam dele para se saber
                se a leitura tem lastro. Texto sobre cor sólida herda a tinta do texto principal,
                com opacidade para a hierarquia. */}
            <span className="font-mono text-[9px] text-foreground/85">{c.n}</span>
          </div>
        ) : (
          <div key={b} className="flex aspect-[1.9] items-center justify-center rounded-md border border-dashed border-border">
            <span className="font-mono text-[10px] text-muted-foreground/60">{vazio}</span>
          </div>
        );
      })}
    </>
  );
}
