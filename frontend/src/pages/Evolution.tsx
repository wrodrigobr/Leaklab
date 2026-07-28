import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, TrendingUp, Minus, ArrowRight, Map } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { evolution, training, type EvolutionReport } from "@/lib/api";
import { useSpotLabel } from "@/lib/spotLabel";
import { cn } from "@/lib/utils";

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
  const { t } = useTranslation("evolution");
  // Fonte ÚNICA do rótulo do spot, a mesma do Training — se cada tela montasse o seu, o mesmo
  // leak apareceria com nomes diferentes em lugares diferentes.
  const spotLabel = useSpotLabel();
  const { data, isLoading } = useQuery({ queryKey: ["evolution"], queryFn: evolution.report });
  const { data: proofData } = useQuery({ queryKey: ["training-proof"], queryFn: training.proof });
  const proof = proofData?.proof ?? [];

  const resumo = data?.resumo;
  const delta = resumo?.delta;
  const bb = resumo?.bb_por_torneio;

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="space-y-4">

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
                  to={`/replay?t=${encodeURIComponent(s.ext)}&h=${encodeURIComponent(s.hand_id)}`}
                  className="group flex items-center gap-3 py-2.5 transition-colors hover:bg-background/40">
                  <span className="w-5 shrink-0 text-center font-mono text-[11px] text-muted-foreground">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold text-foreground">
                      {t("costly.played", { action: s.action, best: s.best_action ?? "—" })}
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
                .map((p) => {
                  const v = p.validacao!;
                  const melhorou = v.veredito === "melhorou";
                  const piorou = v.veredito === "piorou";
                  return (
                    <div key={p.category_key}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-background/60 p-3 ring-1 ring-border">
                      <span className="text-[12px] font-bold text-foreground">
                        {spotLabel(p.category_key, { fallback: p.category_key })}
                      </span>
                      <span className="flex items-center gap-3 font-mono text-[11px]">
                        <span className="text-muted-foreground">{v.taxa_antes}%</span>
                        <ArrowRight className="size-3 text-muted-foreground/50" aria-hidden />
                        <span className={cn("font-bold",
                          melhorou ? "text-emerald-400" : piorou ? "text-red-400" : "text-foreground")}>
                          {v.taxa_depois}%
                        </span>
                        <span className="text-muted-foreground">({v.n_depois})</span>
                      </span>
                    </div>
                  );
                })}
            </div>
            <p className="mt-3 text-[10px] leading-snug text-muted-foreground">{t("proof.disclaimer")}</p>
          </div>
        )}

        {/* ── 5 · Retratos datados ──────────────────────────────────────────────────
            O valor de congelar é poder comparar julho com agosto: um número que muda sozinho não
            serve para comparação. Some quando não há histórico — um bloco vazio dizendo "nenhum
            relatório ainda" só ocupa espaço numa tela que já é longa. */}
        <Historico />

        <Link to="/training"
          className="flex items-center justify-center gap-1.5 rounded-2xl border border-border bg-card/40 p-4 text-[12px] font-bold text-primary transition-colors hover:border-primary/40">
          <Map className="size-4" aria-hidden /> {t("backToTraining")}
        </Link>
      </div>
    </HudLayout>
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
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <span className="font-mono text-[12px] text-foreground">
              {new Date(r.created_at.replace(" ", "T") + "Z").toLocaleDateString()}
            </span>
            <span className="flex items-center gap-3">
              <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {t(`history.motivo.${r.motivo}`, { defaultValue: r.motivo })}
              </span>
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {r.n_decisoes} {t("history.decisions")}
              </span>
            </span>
          </div>
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
    // Escala sequencial de UMA cor (o teal da marca), clara → escura. Nunca arco-íris: aqui a
    // cor codifica magnitude, e magnitude tem ordem.
    const p = Math.min(v / max, 1);
    return { background: `color-mix(in oklab, hsl(var(--primary)) ${8 + p * 72}%, transparent)` };
  };

  return (
    <div className="rounded-2xl border border-border bg-card/40 p-5">
      <h2 className="mb-1 font-heading text-base font-bold text-foreground">{t("matrix.title")}</h2>
      <p className="mb-3 text-[11px] leading-snug text-muted-foreground">{t("matrix.subtitle")}</p>
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
  return (
    <>
      <div className="flex items-center justify-end pr-2 font-mono text-[11px] text-muted-foreground">{pos}</div>
      {buckets.map((b) => {
        const c = grade.get(`${pos}|${b}`);
        return c && c.bb_100 != null ? (
          <div key={b} style={tom(c.bb_100)}
            title={`${pos} · ${b} · ${c.bb_100}bb/100 · ${c.n} decisões`}
            className="flex aspect-[1.9] flex-col items-center justify-center rounded-md">
            <span className="font-mono text-[12px] font-bold text-foreground">{c.bb_100.toFixed(1)}</span>
            <span className="font-mono text-[9px] text-muted-foreground">{c.n}</span>
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
