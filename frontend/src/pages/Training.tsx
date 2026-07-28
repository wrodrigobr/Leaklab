import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Dumbbell, GraduationCap, RotateCw, Target, Award, Flame, Star, Trophy, Lock, Map as MapIcon, Play, TrendingUp, TrendingDown, Sparkles, Medal, Gem, Compass, Crown, Info, Repeat, Zap, Rocket, type LucideIcon } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { training, progression } from "@/lib/api";
import { DailyChallengeCard } from "@/components/training/DailyChallengeCard";
import { MasteryGate } from "@/components/training/MasteryGate";
import { useSpotLabel } from "@/lib/spotLabel";
import { cn } from "@/lib/utils";

// Cada conquista tem um ÍCONE próprio (não um número) — pra ler como medalha, não como passo de
// uma sequência. Agrupado por natureza: volume=halteres, tier=medalha/troféu/gema, streak=chama.
// Ícone ÚNICO por conquista (nada repetido) — pra ler como uma coleção de medalhas distintas.
const ACH_ICON: Record<string, LucideIcon> = {
  "train:first":    Sparkles,   // primeiro acerto
  "train:reps50":   Dumbbell,   // volume
  "train:reps200":  Repeat,     // mais volume
  "train:reps1000": Crown,      // volume máximo
  "train:silver":   Medal,      // tier prata
  "train:gold":     Trophy,     // tier ouro
  "train:gold3":    Award,      // 3 habilidades no ouro
  "train:diamond":  Gem,        // tier diamante
  "train:explorer": Compass,    // explorar categorias
  "train:streak3":  Flame,      // streak 3
  "train:streak7":  Zap,        // streak 7
  "train:streak30": Rocket,     // streak 30
};

const TIER: Record<string, { label: string; ring: string; text: string }> = {
  bronze:  { label: "Bronze",   ring: "#b08d57", text: "text-[#d9a86a]" },
  silver:  { label: "Prata",    ring: "#c8d0d8", text: "text-slate-200" },
  gold:    { label: "Ouro",     ring: "#f5c542", text: "text-amber-300" },
  diamond: { label: "Diamante", ring: "#5ad1ff", text: "text-cyan-300" },
};

export default function Training() {
  const { t } = useTranslation("training");
  const { t: ta } = useTranslation("academy");
  const { data: overview } = useQuery({ queryKey: ["training-overview"], queryFn: training.overview });
  const { data: proofData } = useQuery({ queryKey: ["training-proof"], queryFn: training.proof });
  const proof = proofData?.proof ?? [];
  // O PROTOCOLO é a jornada. Esta tela tinha uma própria (Treinar → Aplicar → Provar, com gate
  // por tier ouro/diamante) que media outra coisa e podia contradizer o Leak Trainer sobre o
  // mesmo leak no mesmo dia. Os tiers continuam existindo como gamificação de ESFORÇO (volume
  // praticado); quem decide progressão é o gate de domínio.
  const { data: protocolo } = useQuery({
    queryKey: ["progression-status"],
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
  const JOURNEY = [
    { key: "train", icon: Dumbbell,
      status: estadoFoco === "em_treino" ? "active" : estadoFoco ? "done" : "active" },
    { key: "apply", icon: Play,
      status: dominadas.length ? (proof.length ? "done" : "active") : "locked" },
    { key: "prove", icon: TrendingUp,
      status: provados.length ? "done" : dominadas.length && proof.length ? "active" : "locked" },
  ] as const;

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="space-y-4">

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
          <Link to="/academy"
            className="group flex items-center gap-3 rounded-xl border border-violet-500/30 bg-violet-500/[0.06] p-3 transition-colors hover:border-violet-500/50">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 ring-1 ring-violet-500/30">
              <GraduationCap className="size-5 text-violet-400" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-heading text-base font-bold text-foreground">{t("academy.title")}</h3>
              <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{t("academy.desc")}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-violet-400 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>

        {/* ── Desafio do Dia (#42) — hook diário, some se não há spot aprovado ── */}
        <DailyChallengeCard />

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
              {JOURNEY.map(({ key, icon: Icon, status }, i) => {
                const done = status === "done", active = status === "active";
                const locked = status === "locked", soon = status === "soon";
                return (
                  <div key={key} className="flex items-center gap-2">
                    <div title={t(`journey.${key}.tip`)}
                      className={cn("relative flex flex-1 cursor-help flex-col items-center gap-1.5 rounded-xl p-3 text-center ring-1 transition-colors",
                      active ? "bg-primary/10 ring-primary/40"
                      : done ? "bg-emerald-500/10 ring-emerald-500/30"
                      : "bg-muted/5 opacity-60 ring-border")}>
                      <Info className="absolute right-1.5 top-1.5 size-3 text-muted-foreground/40" aria-hidden />
                      <div className="relative">
                        <Icon className={cn("size-6", active ? "text-primary" : done ? "text-emerald-400" : "text-muted-foreground")} aria-hidden />
                        {done && <CheckCircle2 className="absolute -right-1.5 -top-1.5 size-3.5 text-emerald-400" aria-hidden />}
                        {(locked || soon) && <Lock className="absolute -right-1.5 -top-1.5 size-3 text-muted-foreground" aria-hidden />}
                      </div>
                      <p className={cn("font-mono text-[11px] font-bold uppercase tracking-wider", active ? "text-foreground" : "text-muted-foreground")}>
                        {t(`journey.${key}.title`)}
                      </p>
                      <p className="text-[10px] leading-tight text-muted-foreground">
                        {soon ? t("journey.soon") : t(`journey.${key}.desc`)}
                      </p>
                    </div>
                    {i < JOURNEY.length - 1 && <ArrowRight className="size-4 shrink-0 text-muted-foreground/50" aria-hidden />}
                  </div>
                );
              })}
            </div>

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
                  <p className="text-[12px] leading-snug text-foreground">
                    {t("proof.reopened", { count: reabertos })}
                  </p>
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
              {tierCounts.map(({ tier, count }) => {
                const tm = TIER[tier];
                return (
                  <div key={tier} className={cn("flex flex-col items-center gap-0.5 rounded-xl py-2 ring-1",
                    count > 0 ? "bg-card/60 ring-border" : "bg-muted/5 opacity-50 ring-border")}>
                    <Trophy className="size-5" style={{ color: tm.ring }} aria-hidden />
                    <span className="font-mono text-base font-bold tabular-nums text-foreground">{count}</span>
                    <span className={cn("font-mono text-[9px] uppercase tracking-wider", tm.text)}>{tm.label}</span>
                  </div>
                );
              })}
            </div>

            {/* Domínio por habilidade — onde o jogador está */}
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("status.skills")}</p>
              {overview.skills.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("status.noSkills")}</p>
              ) : (
                <div className="space-y-2">
                  {overview.skills.slice(0, 6).map((s) => {
                    const tm = TIER[s.tier] ?? TIER.bronze;
                    return (
                      <div key={s.category_key} className="flex items-center gap-3">
                        <span className="w-40 shrink-0 truncate text-[11px] leading-tight text-foreground sm:w-52">{skillLabel(s.category_key)}</span>
                        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted/30">
                          <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.round(s.mastery)}%`, backgroundColor: tm.ring }} />
                        </div>
                        {s.stale && <RotateCw className="size-3 shrink-0 text-amber-400/80" title={t("status.reviewHint")} aria-hidden />}
                        <span className={cn("w-16 shrink-0 text-right font-mono text-[10px] font-bold uppercase", tm.text)}>{tm.label}</span>
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
              <div className="flex flex-wrap gap-2.5">
                {overview.achievements.map((a) => {
                  const Icon = ACH_ICON[a.key] ?? Award;
                  return (
                    <div key={a.key}
                      title={`${ta(`trainAch.${achKey(a.key)}.title`)} · ${ta(`trainAch.${achKey(a.key)}.desc`)}`}
                      className={cn("relative flex size-11 cursor-default items-center justify-center rounded-xl ring-1 transition-transform hover:scale-110",
                        a.unlocked
                          ? "bg-primary/15 ring-primary/40 shadow-[0_0_14px_-3px] shadow-primary/50"
                          : "bg-muted/10 ring-border")}>
                      <Icon className={cn("size-5", a.unlocked ? "text-primary" : "text-muted-foreground/40")} aria-hidden />
                      {!a.unlocked && (
                        <span className="absolute -bottom-1 -right-1 flex size-4 items-center justify-center rounded-full bg-background ring-1 ring-border">
                          <Lock className="size-2.5 text-muted-foreground" aria-hidden />
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

      </div>
    </HudLayout>
  );
}
