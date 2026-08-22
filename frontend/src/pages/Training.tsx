import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Dumbbell, RotateCw, Target, Award, Flame, Star, Trophy, Lock, Map as MapIcon, Play, TrendingUp, TrendingDown, Sparkles, Info } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { training, progression } from "@/lib/api";
import { DailyChallengeCard } from "@/components/training/DailyChallengeCard";
import { TrainingCatalog } from "@/components/training/TrainingCatalog";
import { MasteryGate } from "@/components/training/MasteryGate";
import { useSpotLabel } from "@/lib/spotLabel";
import { cn } from "@/lib/utils";
import { AchievementMedal, EmblemIcon } from "@/components/hud/AchievementMedal";
import { ACHIEVEMENT_MEDALS } from "@/lib/achievementMedals";
import { TIER_COLORS, type MedalTier } from "@/lib/medalTiers";


// A escala de tier é UMA só (lib/medalTiers): as mesmas cores que as medalhas usam. Este mapa
// local tinha um segundo jogo de cores e os rótulos em PT fixo — duas escalas homônimas na mesma
// tela, e uma delas sem i18n.

/** Ocupa o espaço que o conteúdo vai ocupar, com as MESMAS medidas dos blocos reais (jornada de
 *  3 colunas e o painel de status). Esqueleto menor que o conteúdo empurra a página quando os
 *  dados chegam, e o clique do jogador cai noutro lugar — que é a versão pior do problema que ele
 *  relatou. */
function EsqueletoTreino({ rotulo }: { rotulo: string }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      <span className="sr-only">{rotulo}</span>
      <div className="rounded-2xl border border-border bg-card/40 p-5">
        <div className="mb-3 h-4 w-40 animate-pulse rounded bg-muted/40" />
        <div className="grid grid-cols-3 gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-muted/25 ring-1 ring-border/50" />
          ))}
        </div>
      </div>
      <div className="space-y-4 rounded-2xl border border-border bg-card/40 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="h-5 w-36 animate-pulse rounded bg-muted/40" />
          <div className="h-7 w-28 animate-pulse rounded-lg bg-muted/30" />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-muted/25" />
          ))}
        </div>
        <div className="h-20 animate-pulse rounded-xl bg-muted/20" />
      </div>
    </div>
  );
}

export default function Training() {
  const { t } = useTranslation("training");
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const { t: ta } = useTranslation("academy");
  // `isPending` importa tanto quanto `data`: TODO o conteúdo abaixo dos 3 atalhos depende deste
  // overview, então enquanto ele não chega a página fica com os atalhos e mais nada. Reportado:
  // "parece que não tem mais nada na página (...) isso pode direcionar o usuário a clicar em algo
  // antes de ver o conteúdo". Página vazia é uma afirmação, e era a afirmação errada.
  const { data: overview, isPending: carregandoOverview } =
    useQuery({ queryKey: ["training-overview"], queryFn: training.overview });
  // A prova vem no próprio overview: ele já a calculava por dentro para as conquistas, e pedi-la
  // de novo era a segunda metade das ~219 idas ao banco que essa tela fazia. O `?? []` no fim é a
  // ponte para um backend antigo que ainda não devolva o campo.
  const proof = overview?.proof ?? [];
  // O PROTOCOLO é a jornada. Esta tela tinha uma própria (Treinar → Aplicar → Provar, com gate
  // por tier ouro/diamante) que media outra coisa e podia contradizer o Leak Trainer sobre o
  // mesmo leak no mesmo dia. Os tiers continuam existindo como gamificação de ESFORÇO (volume
  // praticado); quem decide progressão é o gate de domínio.
  const { data: protocolo } = useQuery({
    queryKey: ["progression-status", 90],   // janela na key: 90d ≠ 365d da trilha (costura 1)
    queryFn: () => progression.status(),
    staleTime: 60_000,
    retry: false,
  });
  const foco      = protocolo?.ativa ?? null;
  const dominadas = protocolo?.dominadas ?? [];
  const provados  = dominadas.filter((d) => d.estado === "comprovado_no_jogo");

  // Rótulo do spot a partir da category_key — fonte ÚNICA (lib/spotLabel), a mesma que o
  // Dashboard, o Plano de Estudo e o Leak Trainer usam. Antes cada tela tinha a sua e o mesmo
  // leak aparecia com nomes diferentes conforme onde você olhasse.
  const spotLabel  = useSpotLabel();
  const skillLabel = (key: string): string => spotLabel(key, { fallback: key });
  const unlockedCount = overview?.achievements.filter((a) => a.unlocked).length ?? 0;
  const achKey = (k: string) => k.replace(/:/g, "_");   // ':' é separador de namespace no i18next
  // contagem por tier (visão gamificada da evolução, além das barras)
  const tierCounts = (["bronze", "silver", "gold", "diamond"] as const).map((tier) => ({
    tier, count: overview?.skills.filter((s) => s.tier === tier).length ?? 0,
  }));
  // A rampa de onboarding (training_readiness) segue viva SÓ pro iniciante, que precisa de uma
  // meta de volume ("jogue N torneios") antes de existir leak medido. Ela deixou de ser gate de
  // progressão: quem decide isso é o domínio.
  const readiness = overview?.readiness ?? null;
  const isBeginner = readiness?.stage === "beginner";
  const gatePct = readiness && readiness.total > 0
    ? Math.round((readiness.done / readiness.total) * 100) : 0;

  // A JORNADA = os 3 estados do protocolo, aplicados ao leak em foco. Sequencial de verdade:
  // dominar no treino libera o próximo leak, comprovar exige o jogo real.
  const estadoFoco = foco?.estado ?? (dominadas.length ? "dominado_no_treino" : null);
  // Emblemas gravados, o mesmo traço das medalhas. Etapa NÃO é medalha, então vai o glifo sem o
  // disco (`EmblemIcon`): consistência de desenho sem confundir os dois vocabulários.
  const JOURNEY = [
    { key: "train", emblem: "target" as const,
      status: estadoFoco === "em_treino" ? "active" : estadoFoco ? "done" : "active" },
    // O cadeado do "jogar" e RECOMENDACAO DE ESTUDO, nunca bloqueio: o aluno pode jogar e importar
    // quando quiser, e a tela diz isso. O que ele comunica e onde o foco de ESTUDO deveria estar.
    //
    // O bug que o usuario achou: a condicao era `dominadas.length`, ou seja, ter dominado UM leak
    // na vida destravava o passo PARA SEMPRE. Cinco leaks novos podiam aparecer que ele nunca mais
    // fechava — "o ciclo nunca reiniciava". Agora depende de haver leak EM TREINO agora, entao
    // leak novo fecha o ciclo de novo, que e o comportamento pedido.
    { key: "apply", emblem: "cards" as const,
      status: foco ? "locked" : (proof.length ? "done" : "active") },
    { key: "prove", emblem: "seal" as const,
      status: provados.length ? "done" : (!foco && proof.length) ? "active" : "locked" },
  ] as const;

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="space-y-4">

        {/* Fase 1 do redesign (project_redesign_trilha_training): a v2 mora em rota própria e
            esta tela fica INTACTA — um convite discreto, nunca um redirect. */}
        <Link to="/training"
          className="flex items-center justify-between gap-3 rounded-xl border border-primary/25 bg-primary/[0.05] px-3 py-2 text-[12px] transition-colors hover:border-primary/50">
          <span className="text-muted-foreground">
            <span className="mr-2 rounded-full bg-primary/15 px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest text-primary">{t("trilha.beta")}</span>
            {t("trilha.convite")}
          </span>
          <ArrowRight className="size-3.5 shrink-0 text-primary" aria-hidden />
        </Link>

        {/* ── Ações de treino — compactas, no topo (a ação principal vem primeiro) ── */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Link to="/ghost"
            className="group flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/[0.05] p-3 transition-colors hover:border-primary/50">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/30">
              <RotateCw className="size-5 text-primary" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-heading text-base font-bold text-foreground">{t("trainer.review.title")}</h3>
              <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{t("trainer.review.desc")}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-primary transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
          <Link to="/leak-trainer"
            className="group flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-3 transition-colors hover:border-amber-500/50">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 ring-1 ring-amber-500/30">
              <Target className="size-5 text-amber-400" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-heading text-base font-bold text-foreground">{t("trainer.train.title")}</h3>
              <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{t("trainer.train.desc")}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-amber-400 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
          {/* Academia MUDOU para /study (18/08): teoria é objetivo de ESTUDO, não de treino —
              a tela de treino fica com revisar e treinar, que é o que ela promete. */}
        </div>

        {/* ── Catálogo: o jogador ESCOLHE o que treinar ────────────────────────
            Vem logo abaixo dos atalhos e acima do resto porque é a pergunta que ele chega
            fazendo. O motor já aceitava o foco; o que faltava era ele conseguir pedir. */}
        <TrainingCatalog />

        {/* ── Desafio do Dia (#42) — hook diário, some se não há spot aprovado ── */}
        <DailyChallengeCard />

        {/* Enquanto o overview não chega, a página precisa DIZER que ainda está carregando. Sem
            isto ela mostra três atalhos e um vazio, que se lê como "acabou". */}
        {carregandoOverview && <EsqueletoTreino rotulo={t("loading")} />}

        {/* ── Aviso: leaks do jogo ainda sem treino → reinicie o ciclo (novos leaks surgiram) ── */}
        {readiness && (readiness.untrained?.length ?? 0) > 0 && (
          <div className="flex flex-col gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/[0.07] p-4 sm:flex-row sm:items-center">
            <Sparkles className="size-6 shrink-0 text-amber-400" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-foreground">{t("newLeaks.title", { count: readiness.untrained.length })}</p>
              <p className="text-xs leading-snug text-muted-foreground">{t("newLeaks.desc")}</p>
            </div>
            <Link to="/leak-trainer"
              className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
              <Target className="size-4" aria-hidden /> {t("newLeaks.cta")}
            </Link>
          </div>
        )}

        {/* ── A JORNADA — Treinar → Aplicar (gate Ouro) → Provar ───────────────── */}
        {overview && (
          <div className="rounded-2xl border border-border bg-card/40 p-5">
            <h2 className="mb-3 flex items-center gap-2 font-heading text-base font-bold text-foreground">
              <MapIcon className="size-4 text-primary" aria-hidden /> {t("journey.title")}
            </h2>
            <div className="grid grid-cols-3 gap-2">
              {JOURNEY.map(({ key, emblem, status }, i) => {
                // "soon" não existe mais nos status do JOURNEY (active/done/locked) — resíduo removido
                const done = status === "done", active = status === "active";
                const locked = status === "locked";
                return (
                  <div key={key} className="flex items-center gap-2">
                    <div title={t(`journey.${key}.tip`)}
                      className={cn("relative flex flex-1 cursor-help flex-col items-center gap-1.5 rounded-xl p-3 text-center ring-1 transition-colors",
                      active ? "bg-primary/10 ring-primary/40"
                      : done ? "bg-emerald-500/10 ring-emerald-500/30"
                      : "bg-muted/5 opacity-60 ring-border")}>
                      <Info className="absolute right-1.5 top-1.5 size-3 text-muted-foreground/40" aria-hidden />
                      <div className="relative">
                        <EmblemIcon emblem={emblem} size={26} className={cn(active ? "text-primary" : done ? "text-emerald-400" : "text-muted-foreground")} />
                        {done && <CheckCircle2 className="absolute -right-1.5 -top-1.5 size-3.5 text-emerald-400" aria-hidden />}
                        {locked && <Lock className="absolute -right-1.5 -top-1.5 size-3 text-muted-foreground" aria-hidden />}
                      </div>
                      <p className={cn("font-mono text-[11px] font-bold uppercase tracking-wider", active ? "text-foreground" : "text-muted-foreground")}>
                        {t(`journey.${key}.title`)}
                      </p>
                      <p className="text-[10px] leading-tight text-muted-foreground">
                        {t(`journey.${key}.desc`)}
                      </p>
                    </div>
                    {i < JOURNEY.length - 1 && <ArrowRight className="size-4 shrink-0 text-muted-foreground/50" aria-hidden />}
                  </div>
                );
              })}
            </div>
            {foco && (
              // O cadeado precisa dizer que NAO bloqueia. Sem esta linha ele lê como "pare de
              // jogar até treinar", que é o oposto do que o produto quer: sem torneio novo não há
              // amostra, e sem amostra não há validação.
              <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
                {t("journey.lockNote")}
              </p>
            )}

            {/* GATE — agora é o do protocolo (5 critérios sobre o leak em foco), não o de tier.
                O de tier media VOLUME praticado e podia dizer "pronto para aplicar" enquanto o
                Leak Trainer dizia "faltam 3 critérios" sobre o mesmo leak. */}
            {foco ? (
              <div className="mt-4 rounded-xl bg-muted/5 p-4 ring-1 ring-border">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="flex min-w-0 items-center gap-2 text-sm font-bold text-foreground">
                    <Target className="size-4 shrink-0 text-amber-400" aria-hidden />
                    <span className="truncate">{spotLabel(foco, { fallback: foco.titulo })}</span>
                  </p>
                  <span className="shrink-0 font-mono text-xs font-bold tabular-nums text-amber-300">
                    {foco.mastery.criterios.filter((c) => c.ok).length}/{foco.mastery.criterios.length}
                  </span>
                </div>
                <MasteryGate criterios={foco.mastery.criterios} />
                <p className="mt-2 text-xs leading-snug text-muted-foreground">{t("journey.gateHintProtocol")}</p>
                <Link to="/leak-trainer"
                  className="mt-3 inline-flex items-center gap-2 rounded-lg bg-amber-500/15 px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-amber-300 ring-1 ring-amber-500/30 transition-colors hover:bg-amber-500/25">
                  <Target className="size-4" aria-hidden /> {t("journey.keepTraining")}
                </Link>
              </div>
            ) : dominadas.length > 0 ? (
              <div className="mt-4 flex flex-col gap-3 rounded-xl bg-primary/[0.08] p-4 ring-1 ring-primary/30 sm:flex-row sm:items-center">
                <Trophy className="size-6 shrink-0 text-primary" aria-hidden />
                <p className="flex-1 text-sm text-foreground">{t("journey.allMasteredMsg", { count: dominadas.length })}</p>
                <Link to="/dashboard"
                  className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
                  <Play className="size-4" aria-hidden /> {t("journey.applyCta")}
                </Link>
              </div>
            ) : readiness && isBeginner ? (
              <div className="mt-4 rounded-xl bg-primary/[0.06] p-4 ring-1 ring-primary/25">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="flex items-center gap-2 text-sm font-bold text-foreground">
                    <Play className="size-4 text-primary" aria-hidden /> {t("journey.beginnerTitle")}
                  </p>
                  <span className="shrink-0 font-mono text-xs font-bold tabular-nums text-primary">
                    {readiness.done}/{readiness.total} <span className="text-muted-foreground">{t("journey.tourneysUnit")}</span>
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted/30">
                  <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${gatePct}%` }} />
                </div>
                <p className="mt-2 text-xs leading-snug text-muted-foreground">{t("journey.beginnerHint", { done: readiness.done, target: readiness.total })}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link to="/dashboard"
                    className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
                    <Play className="size-4" aria-hidden /> {t("journey.applyCta")}
                  </Link>
                  <Link to="/leak-trainer"
                    className="inline-flex items-center gap-2 rounded-lg bg-amber-500/15 px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-amber-300 ring-1 ring-amber-500/30 transition-colors hover:bg-amber-500/25">
                    <Target className="size-4" aria-hidden /> {t("journey.beginnerTrainCta")}
                  </Link>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-xl bg-muted/5 p-4 ring-1 ring-border">
                <p className="flex items-center gap-2 text-sm font-bold text-foreground">
                  <Lock className="size-4 text-muted-foreground" aria-hidden /> {t("journey.gateTitle")}
                </p>
                <p className="mt-1 text-xs leading-snug text-muted-foreground">{t("journey.noLeakYet")}</p>
                <Link to="/leak-trainer"
                  className="mt-3 inline-flex items-center gap-2 rounded-lg bg-amber-500/15 px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-amber-300 ring-1 ring-amber-500/30 transition-colors hover:bg-amber-500/25">
                  <Target className="size-4" aria-hidden /> {t("journey.keepTraining")}
                </Link>
              </div>
            )}
          </div>
        )}

        {/* ── COMPROVAR — placar, não lista ────────────────────────────────────────────
            Antes isto renderizava `proof.slice(0, 6)` como cards. Três defeitos que a saída de
            produção expôs (60 famílias no banco de um jogador real):

            1. cortava em 6 SEM dizer que cortou, e a ordem não era por relevância — as seis
               visíveis podiam ser justamente as sem veredito;
            2. mostrava DUPLICATAS como leaks distintos: o filtro de categoria ignora o stack de
               propósito, então `rfi:BTN::14/::20/::50` medem a MESMA população e apareciam como
               três leaks de botão onde existe um;
            3. enterrava a única notícia urgente — leak REABERTO por regressão tinha o mesmo peso
               visual de "sem amostra".

            A tela de treino é superfície de AÇÃO ("o que faço agora"). O detalhe é superfície de
            reflexão e mora no relatório. Aqui fica o placar e a porta de entrada — e a regressão,
            que é a única coisa aqui que exige reação imediata, sobe como alerta. */}
        {proof.length > 0 && (() => {
          const verdicts = proof.map((p) => p.validacao?.veredito);
          const provados  = verdicts.filter((v) => v === "melhorou").length;
          const reabertos = verdicts.filter((v) => v === "piorou").length;
          const emValidacao = verdicts.filter((v) => v === "sem_mudanca").length;
          const semAmostra  = proof.length - provados - reabertos - emValidacao;
          // NOMEAR os leaks, e nao so conta-los. O usuario reportou: "aqui so falamos que ele
          // provou algo em jogo, mas nao falamos qual foi o leak". Um placar sem nome nao vira
          // memoria nem orgulho, e no caso da regressao nao vira acao.
          //
          // O rotulo sai de `familia` (sem profundidade), NUNCA de `category_key`: a chave de
          // treino carrega o stack e a medicao o ignora, entao rotular por ela afirmaria uma
          // precisao inexistente ("Abertura de UTG+1 · 50bb" para um numero de todas as
          // profundidades) e duplicaria a mesma familia ate seis vezes. Mesma regra que a pagina
          // de evolucao ja usa.
          const nomes = (v: string) => proof
            .filter((p) => p.validacao?.veredito === v)
            .map((p) => spotLabel(p.familia ?? p.category_key,
                                  { stack: false, fallback: p.category_key }))
            .filter((x, i, arr) => x && arr.indexOf(x) === i);
          const nomesProvados  = nomes("melhorou");
          const nomesReabertos = nomes("piorou");
          return (
            <div className="rounded-2xl border border-border bg-card/40 p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 font-heading text-base font-bold text-foreground">
                  <TrendingUp className="size-4 text-primary" aria-hidden /> {t("proof.title")}
                </h2>
                <Link to="/evolucao"
                  className="flex items-center gap-1 text-[11px] font-bold text-primary hover:underline">
                  {t("proof.seeReport")} <ArrowRight className="size-3" aria-hidden />
                </Link>
              </div>

              {reabertos > 0 && (
                <div className="mb-3 flex items-start gap-2 rounded-xl bg-red-500/10 p-3 ring-1 ring-red-500/30">
                  <TrendingDown className="mt-0.5 size-4 shrink-0 text-red-400" aria-hidden />
                  <div className="min-w-0">
                    <p className="text-[12px] leading-snug text-foreground">
                      {t("proof.reopened", { count: reabertos })}
                    </p>
                    {nomesReabertos.length > 0 && (
                      <p className="mt-0.5 text-[12px] font-medium leading-snug text-red-300">
                        {nomesReabertos.join(" · ")}
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {([
                  ["provados", provados, "text-emerald-400"],
                  ["reopened", reabertos, reabertos > 0 ? "text-red-400" : "text-muted-foreground"],
                  ["validating", emValidacao, "text-foreground"],
                  ["noSample", semAmostra, "text-muted-foreground"],
                ] as const).map(([key, n, color]) => (
                  <div key={key} className="rounded-xl bg-background/60 p-3 ring-1 ring-border">
                    <div className={cn("font-mono text-xl font-bold tabular-nums", color)}>{n}</div>
                    <div className="text-[11px] leading-snug text-muted-foreground">
                      {t(`proof.count.${key}`)}
                    </div>
                  </div>
                ))}
              </div>
              {nomesProvados.length > 0 && (
                <div className="mt-3 rounded-xl bg-emerald-500/[0.07] p-3 ring-1 ring-emerald-500/25">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-emerald-400">
                    {t("proof.provedTitle", { count: nomesProvados.length })}
                  </p>
                  <ul className="mt-1.5 space-y-1">
                    {proof
                      .filter((p) => p.validacao?.veredito === "melhorou")
                      .map((p) => (
                        <li key={p.category_key} className="flex flex-wrap items-baseline gap-x-2 text-[12px]">
                          <span className="font-medium text-foreground">
                            {spotLabel(p.familia ?? p.category_key,
                                       { stack: false, fallback: p.category_key })}
                          </span>
                          {/* O numero ao lado do nome: sem ele o aluno le "provado" e nao sabe o
                              que melhorou nem quanto. Vem da validacao (taxa de erro com intervalo),
                              nao do `delta` cru, que nao tem intervalo de confianca. */}
                          {p.validacao && (
                            <span className="font-mono tabular-nums text-muted-foreground">
                              {t("proof.fromTo", {
                                antes: p.validacao.taxa_antes_ajustada ?? p.validacao.taxa_antes,
                                depois: p.validacao.taxa_depois,
                              })}
                            </span>
                          )}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
              <p className="mt-3 text-[10px] leading-snug text-muted-foreground">{t("proof.disclaimer")}</p>
            </div>
          );
        })()}

        {/* ── SEU TREINO — status/domínio/conquistas (eixo de gamificação, separado do ELO) ── */}
        {overview && (
          <div className="space-y-4 rounded-2xl border border-border bg-card/40 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 font-heading text-lg font-bold text-foreground">
                <Award className="size-5 text-primary" aria-hidden /> {t("status.title")}
              </h2>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 ring-1 ring-primary/25">
                  <Star className="size-3.5 text-primary" aria-hidden />
                  <span className="font-mono text-xs font-bold tabular-nums text-foreground">{overview.xp.xp_total}</span>
                  <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">XP</span>
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-3 py-1.5 ring-1 ring-amber-500/25">
                  <Flame className="size-3.5 text-amber-400" aria-hidden />
                  <span className="font-mono text-xs font-bold tabular-nums text-amber-300">{overview.xp.streak}</span>
                </span>
              </div>
            </div>

            {/* Missões de hoje (Fase 2 — motor de hábito) */}
            {overview.missions.length > 0 && (
              <div>
                <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("missions.title")}</p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {overview.missions.map((m) => {
                    const pct = Math.min(100, Math.round((m.progress / m.target) * 100));
                    return (
                      <div key={m.key} className={cn("rounded-xl p-3 ring-1 transition-colors",
                        m.completed ? "bg-emerald-500/[0.08] ring-emerald-500/30" : "bg-background/60 ring-border")}>
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-[12px] font-bold leading-snug text-foreground">{t(`missions.${m.key}`, { target: m.target })}</span>
                          {m.completed
                            ? <CheckCircle2 className="size-4 shrink-0 text-emerald-400" aria-hidden />
                            : <span className="shrink-0 font-mono text-[10px] font-bold text-primary">+{m.reward}</span>}
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted/30">
                          <div className={cn("h-full rounded-full transition-[width] duration-500", m.completed ? "bg-emerald-400" : "bg-primary")} style={{ width: `${pct}%` }} />
                        </div>
                        <p className="mt-1 font-mono text-[10px] text-muted-foreground">{m.progress}/{m.target}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Medalhas por tier — visão gamificada da evolução */}
            <div className="grid grid-cols-4 gap-2">
              {tierCounts.map(({ tier, count }) => (
                <div key={tier} className={cn("flex flex-col items-center gap-1 rounded-xl py-2.5 ring-1",
                  count > 0 ? "bg-card/60 ring-border" : "bg-muted/5 opacity-50 ring-border")}>
                  {/* Medalha, não troféu: é a MESMA linguagem das conquistas, e o contador de
                      habilidades num tier é o mesmo conceito de nível. Emblema fixo (`chip`) para
                      que a única diferença entre os quatro seja a COR, que é o que o contador diz. */}
                  <AchievementMedal tier={tier as MedalTier} emblem="chip" size={30}
                                    label={t(`tiers.${tier}`)} />
                  <span className="font-mono text-base font-bold tabular-nums text-foreground">{count}</span>
                  <span className="font-mono text-[9px] uppercase tracking-wider"
                        style={{ color: TIER_COLORS[tier as MedalTier]?.light }}>{t(`tiers.${tier}`)}</span>
                </div>
              ))}
            </div>

            {/* Domínio por habilidade — onde o jogador está */}
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("status.skills")}</p>
              {overview.skills.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("status.noSkills")}</p>
              ) : (
                <div className="space-y-2">
                  {overview.skills.slice(0, 6).map((s) => {
                    const cor = (TIER_COLORS[s.tier as MedalTier] ?? TIER_COLORS.bronze).light;
                    return (
                      <div key={s.category_key} className="flex items-center gap-3">
                        <span className="w-40 shrink-0 truncate text-[11px] leading-tight text-foreground sm:w-52">{skillLabel(s.category_key)}</span>
                        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted/30">
                          <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.round(s.mastery)}%`, backgroundColor: cor }} />
                        </div>
                        {s.stale && (
                          <span title={t("status.reviewHint")} className="shrink-0 inline-flex">
                            <RotateCw className="size-3 text-amber-400/80" aria-hidden />
                          </span>
                        )}
                        <span className="w-16 shrink-0 text-right font-mono text-[10px] font-bold uppercase" style={{ color: cor }}>{t(`tiers.${s.tier}`)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Conquistas — COLEÇÃO de medalhas (não sequência): cada uma tem ícone próprio,
                ganha-se em qualquer ordem. Grade que quebra linha, sem números, sem linha do tempo. */}
            <div>
              <div className="mb-1 flex items-center justify-between">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("status.achievements")}</p>
                <span className="font-mono text-[10px] text-muted-foreground">{unlockedCount} {t("status.of")} {overview.achievements.length}</span>
              </div>
              <p className="mb-3 text-[11px] leading-snug text-muted-foreground">{t("status.achievementsHint")}</p>
              <div className="flex flex-wrap gap-3" role="list">
                {overview.achievements.map((a) => {
                  // Medalha por conquista, do mapa ÚNICO. Sem fallback silencioso: uma conquista
                  // fora do mapa viraria bronze genérico, indistinguível de uma que É bronze.
                  const medal = ACHIEVEMENT_MEDALS[a.key];
                  if (!medal) return null;
                  const sel = selecionada === a.key;
                  return (
                    <button key={a.key} type="button" role="listitem"
                      onClick={() => setSelecionada(sel ? null : a.key)}
                      aria-pressed={sel}
                      className={cn("rounded-xl p-1 transition-transform duration-200 hover:scale-110",
                                    sel && "scale-110 ring-1 ring-primary/60")}>
                      <AchievementMedal
                        tier={medal.tier} emblem={medal.emblem} locked={!a.unlocked} size={52}
                        label={t(a.unlocked ? "status.medalAria" : "status.medalAriaLocked", {
                          title: ta(`trainAch.${achKey(a.key)}.title`),
                          tier: t(`tiers.${medal.tier}`),
                        })}
                      />
                    </button>
                  );
                })}
              </div>

              {/* Painel da medalha selecionada.
                  Por que painel e não tooltip: tooltip nativo não existe no toque, e o que o
                  usuário pediu é justamente saber O QUE FALTA — informação que precisa caber com
                  barra e número, não numa linha de hover. O `<title>` que eu tinha posto dentro do
                  SVG ainda por cima SEQUESTRAVA o tooltip do pai e mostrava o texto de
                  acessibilidade ("Medalha prata, conquistada") no lugar da descrição. */}
              {(() => {
                const a = overview.achievements.find((x) => x.key === selecionada);
                const medal = a ? ACHIEVEMENT_MEDALS[a.key] : null;
                if (!a || !medal) {
                  return (
                    <p className="mt-3 text-[11px] italic text-muted-foreground">{t("status.selectHint")}</p>
                  );
                }
                const alvo  = a.target ?? 0;
                const atual = a.progress ?? 0;
                const pct   = alvo > 0 ? Math.min(100, Math.round((atual / alvo) * 100)) : 0;
                const cor   = TIER_COLORS[medal.tier].light;
                return (
                  <div className="mt-3 flex items-start gap-3 rounded-xl bg-card/60 p-3 ring-1 ring-border">
                    <AchievementMedal tier={medal.tier} emblem={medal.emblem} locked={!a.unlocked}
                                      size={44} label="" className="mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-sm font-medium text-foreground">
                          {ta(`trainAch.${achKey(a.key)}.title`)}
                        </span>
                        <span className="font-mono text-[9px] uppercase tracking-wider" style={{ color: cor }}>
                          {t(`tiers.${medal.tier}`)}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground">
                        {ta(`trainAch.${achKey(a.key)}.desc`)}
                      </p>
                      {a.unlocked ? (
                        <p className="mt-1.5 font-mono text-[10px] uppercase tracking-widest" style={{ color: cor }}>
                          {t("status.unlocked")}
                        </p>
                      ) : alvo > 0 ? (
                        <div className="mt-2">
                          <div className="mb-1 flex items-center justify-between font-mono text-[10px]">
                            <span className="uppercase tracking-widest text-muted-foreground">{t("status.locked")}</span>
                            <span className="tabular-nums text-foreground">
                              {t("status.progressOf", { atual, alvo })}
                            </span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-muted/30">
                            <div className="h-full rounded-full transition-[width] duration-500"
                                 style={{ width: `${pct}%`, backgroundColor: cor }} />
                          </div>
                        </div>
                      ) : (
                        <p className="mt-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                          {t("status.locked")}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        )}

      </div>
    </HudLayout>
  );
}
