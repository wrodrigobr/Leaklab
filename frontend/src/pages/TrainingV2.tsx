import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Flame, GraduationCap, Lock, RotateCw, Star, Target, Trophy } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { AchievementMedal, EmblemIcon } from "@/components/hud/AchievementMedal";
import { DailyChallengeCard } from "@/components/training/DailyChallengeCard";
import { MasteryGate } from "@/components/training/MasteryGate";
import { training, progression } from "@/lib/api";
import { montarTrilha, emblemaDoCenario, criteriosDoNo, type NoDaTrilha } from "@/lib/trilhaTreino";
import { useSpotLabel } from "@/lib/spotLabel";
import { cn } from "@/lib/utils";

/**
 * Training v2 — a TRILHA (proposta aprovada em project_redesign_trilha_training).
 *
 * Fase 1: página NOVA em /training-v2, a clássica intacta em /training — comparáveis lado a
 * lado. Um caminho vertical de nós (os leaks do jogador, na ordem de EV que o Protocolo já
 * decide), UM CTA dominante no nó ativo, e o resto realocado: números na lateral, catálogo
 * atrás de "Treinar outra coisa", relatório fora da tela de ação.
 *
 * Zero motor novo: `progression.status` + `training.overview` — os MESMOS endpoints da tela
 * clássica. A trilha dá corpo espacial ao que o gate de domínio já decide.
 */

// v2.1 (feedback do usuário na v2): a serpentina com rótulo EMBAIXO desperdiçava a lateral
// dos ícones e encavalava os textos. A trilha virou LINHAS: medalha à esquerda num trilho
// vertical, título/estado AO LADO — cada nó usa a largura inteira e o texto respira.

/** O disco do nó ATIVO: aro teal pulsando com o emblema gravado — mesma linguagem de traço
 *  das medalhas (EmblemIcon), tier teal que as medalhas não têm (ativo não é conquista). */
function DiscoAtivo({ emblem, reaberto }: { emblem: ReturnType<typeof emblemaDoCenario>; reaberto: boolean }) {
  const cor = reaberto ? "#f87171" : "#2DD4BF";
  return (
    <span className="relative inline-flex">
      <span className={cn("absolute inset-0 rounded-full", reaberto ? "animate-pulse" : "anima-halo")}
            style={{ boxShadow: `0 0 0 0 ${cor}66` }} aria-hidden />
      <svg width={84} height={84} viewBox="0 0 48 48" className="drop-shadow-[0_5px_8px_rgba(0,0,0,0.55)]">
        <circle cx="24" cy="24" r="21" fill={reaberto ? "#3b1214" : "#0e3a34"} />
        <circle cx="24" cy="24" r="21" fill="none" stroke={cor} strokeWidth="2.6" />
        <circle cx="24" cy="24" r="17" fill="hsl(var(--background))" />
        <circle cx="24" cy="24" r="17" fill="none" stroke={cor} strokeOpacity="0.5" strokeWidth="1" />
        <ellipse cx="18" cy="15" rx="13" ry="9" fill="rgba(255,255,255,0.12)" />
        <EmblemIcon emblem={emblem} size={48} color={cor} />
      </svg>
    </span>
  );
}

export default function TrainingV2() {
  const { t } = useTranslation("training");
  const spotLabel = useSpotLabel();
  const { data: status } = useQuery({
    queryKey: ["progression-status"], queryFn: () => progression.status(365), staleTime: 60_000,
  });
  const { data: overview } = useQuery({ queryKey: ["training-overview"], queryFn: training.overview });

  const nos = useMemo(() => montarTrilha(status), [status]);
  const [selKey, setSelKey] = useState<string | null>(null);
  // seleção default = o nó ativo (a pergunta que o usuário trouxe já chega respondida)
  const sel: NoDaTrilha | null =
    nos.find((n) => n.key === selKey) ?? nos.find((n) => n.estado === "ativo") ?? nos[0] ?? null;
  const ctxRef = useRef<HTMLDivElement>(null);

  const selecionar = (n: NoDaTrilha) => {
    setSelKey(n.key);
    // no mobile o painel fica abaixo da trilha — rolar até ele é o "bottom sheet" honesto da F1
    if (window.innerWidth < 1024) ctxRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  // estilo do halo do ativo (keyframes uma vez)
  useEffect(() => {
    const st = document.createElement("style");
    st.textContent = `@keyframes trilhaHalo{0%,100%{box-shadow:0 0 0 0 rgba(45,212,191,.4)}55%{box-shadow:0 0 0 16px rgba(45,212,191,0)}}
      .anima-halo{animation:trilhaHalo 1.9s ease-in-out infinite;border-radius:9999px}`;
    document.head.appendChild(st);
    return () => { document.head.removeChild(st); };
  }, []);

  const foco = status?.ativa ?? null;
  const gate = sel ? criteriosDoNo(sel.item) : { ok: 0, total: 0 };

  return (
    <HudLayout eyebrow={t("trilha.eyebrow")} title={t("trilha.title")} description={t("trilha.subtitle")}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="rounded-full bg-primary/10 px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest text-primary ring-1 ring-primary/30">
          {t("trilha.beta")}
        </span>
        <Link to="/training" className="text-[11px] font-bold text-muted-foreground hover:text-foreground hover:underline">
          {t("trilha.voltarClassica")}
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* ── A TRILHA ── */}
        <div className="rounded-2xl border border-border bg-card/40 p-4"
             style={{ background: "radial-gradient(ellipse 120% 45% at 50% 0%, rgba(45,212,191,.05), transparent 60%)" }}>
          {/* unidade: a família do leak em foco, na linguagem do jogador */}
          {foco && (
            <div className="mb-5 flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/[0.08] p-3">
              <EmblemIcon emblem={emblemaDoCenario(foco.scenario)} size={30} className="shrink-0 text-primary" />
              <div className="min-w-0">
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary">{t("trilha.unidade")}</p>
                <p className="truncate font-heading text-base font-bold text-foreground">
                  {spotLabel(foco, { fallback: foco.titulo })}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  {t("trilha.unidadeSub", { ev: Math.abs(foco.ev_loss_bb).toFixed(1), hands: foco.hands })}
                </p>
              </div>
            </div>
          )}

          {nos.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">{t("trilha.vazia")}</p>
          ) : (
            <div className="relative">
              {/* o trilho: linha pontilhada vertical passando pelo CENTRO das medalhas
                  (medalha 64px + padding do botão 12px → centro a 44px) */}
              <div className="pointer-events-none absolute bottom-6 top-6 left-[44px] w-0 border-l-2 border-dashed border-border" aria-hidden />
              <div className="space-y-2">
                {nos.map((n) => {
                  const emblem = emblemaDoCenario(n.item.scenario);
                  const selecionado = sel?.key === n.key;
                  const ativo = n.estado === "ativo";
                  return (
                    <button key={n.key} type="button" onClick={() => selecionar(n)}
                      aria-pressed={selecionado}
                      className={cn(
                        "relative z-[1] flex w-full items-center gap-4 rounded-2xl p-3 text-left transition-colors",
                        ativo ? "bg-primary/[0.08] ring-1 ring-primary/40"
                          : selecionado ? "bg-card/80 ring-1 ring-primary/30"
                          : "hover:bg-card/60",
                        n.reaberto && "ring-1 ring-red-500/40 bg-red-500/[0.05]",
                      )}>
                      {/* a medalha, sempre no trilho */}
                      <span className="relative shrink-0">
                        {ativo ? (
                          <DiscoAtivo emblem={emblem} reaberto={n.reaberto} />
                        ) : n.estado === "bloqueado" ? (
                          <AchievementMedal tier="silver" emblem={emblem} locked size={64} label=""
                                            className="drop-shadow-[0_5px_8px_rgba(0,0,0,0.55)]" />
                        ) : (
                          <>
                            <AchievementMedal tier={n.estado === "comprovado" ? "diamond" : "gold"}
                                              emblem={emblem} size={64} label=""
                                              className={cn("drop-shadow-[0_5px_8px_rgba(0,0,0,0.55)]",
                                                            n.reaberto && "opacity-60 saturate-50")} />
                            {!n.reaberto && (
                              <span className={cn("absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full text-[10px] font-black",
                                n.estado === "comprovado" ? "bg-sky-300 text-sky-950" : "bg-emerald-400 text-emerald-950")}>
                                {n.estado === "comprovado" ? "◆" : "✓"}
                              </span>
                            )}
                          </>
                        )}
                      </span>
                      {/* título e estado AO LADO — a lateral que estava vazia */}
                      <span className="min-w-0 flex-1">
                        <span className={cn("block truncate font-heading text-[15px] font-bold",
                                            n.estado === "bloqueado" ? "text-muted-foreground" : "text-foreground")}>
                          {spotLabel(n.item, { fallback: n.item.titulo })}
                        </span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11.5px]">
                          {ativo && (
                            <span className="rounded-full bg-primary px-2 py-px font-mono text-[9px] font-extrabold tracking-[0.12em] text-primary-foreground">
                              {n.reaberto ? t("trilha.flagReaberto") : t("trilha.flagComecar")}
                            </span>
                          )}
                          <span className={cn(n.reaberto ? "text-red-400"
                            : n.estado === "comprovado" ? "text-sky-300"
                            : n.estado === "dominado" ? "text-emerald-400"
                            : "text-muted-foreground")}>
                            {n.reaberto ? t("trilha.estadoReaberto") : t(`trilha.estado.${n.estado}`)}
                          </span>
                          {typeof n.item.ev_loss_bb === "number" && n.item.ev_loss_bb !== 0 && (
                            <span className="font-mono tabular-nums text-muted-foreground">
                              −{Math.abs(n.item.ev_loss_bb).toFixed(1)}bb
                            </span>
                          )}
                        </span>
                      </span>
                      {ativo && <ArrowRight className="size-4 shrink-0 text-primary" aria-hidden />}
                    </button>
                  );
                })}
              </div>
              {(status?.restantes ?? 0) > 0 && (
                <p className="pb-1 pl-[84px] pt-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
                  {t("trilha.maisAdiante", { count: status!.restantes })}
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── LATERAL: números + contexto do nó + desafio + praticar ── */}
        <div className="space-y-3" ref={ctxRef}>
          <div className="flex gap-2">
            <div className="flex flex-1 flex-col items-center rounded-xl border border-border bg-card/60 py-2.5">
              <span className="flex items-center gap-1 font-mono text-base font-bold text-amber-300">
                <Flame className="size-4" aria-hidden />{overview?.xp.streak ?? "–"}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("trilha.statStreak")}</span>
            </div>
            <div className="flex flex-1 flex-col items-center rounded-xl border border-border bg-card/60 py-2.5">
              <span className="flex items-center gap-1 font-mono text-base font-bold text-foreground">
                <Star className="size-4 text-primary" aria-hidden />{overview?.xp.xp_total ?? "–"}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">XP</span>
            </div>
            <Link to="/leaderboard" className="flex flex-1 flex-col items-center rounded-xl border border-border bg-card/60 py-2.5 transition-colors hover:border-primary/40">
              <Trophy className="size-5 text-primary" aria-hidden />
              <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("trilha.statLiga")}</span>
            </Link>
          </div>

          {/* contexto do nó selecionado — o ÚNICO lugar com CTA grande */}
          {sel && (
            <div className="rounded-2xl border border-border bg-card p-4">
              <p className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                {sel.reaberto ? t("trilha.ctxReaberto")
                  : t(`trilha.ctx.${sel.estado}`)}
              </p>
              <p className="font-heading text-base font-bold text-foreground">
                {spotLabel(sel.item, { fallback: sel.item.titulo })}
              </p>
              {sel.estado === "ativo" && sel.item.mastery?.criterios?.length > 0 && (
                <div className="mt-3">
                  <div className="mb-1 flex items-center justify-between font-mono text-[10px] text-muted-foreground">
                    <span className="uppercase tracking-widest">{t("trilha.gate")}</span>
                    <span className="tabular-nums text-amber-300">{gate.ok}/{gate.total}</span>
                  </div>
                  <MasteryGate criterios={sel.item.mastery.criterios} />
                </div>
              )}
              {sel.estado === "comprovado" && sel.item.validacao && (
                <p className="mt-2 text-[12px] leading-snug text-muted-foreground">
                  {t("trilha.provaNums", {
                    antes: sel.item.validacao.taxa_antes_ajustada ?? sel.item.validacao.taxa_antes,
                    depois: sel.item.validacao.taxa_depois,
                  })}
                </p>
              )}
              {sel.reaberto && (
                <p className="mt-2 text-[12px] leading-snug text-red-300">{t("trilha.reabertoNota")}</p>
              )}

              {sel.estado === "ativo" || sel.reaberto ? (
                <Link to="/leak-trainer?origem=trilha"
                  className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 font-mono text-sm font-extrabold uppercase tracking-wider text-primary-foreground shadow-[0_4px_0_rgba(23,138,124,1)] transition-transform active:translate-y-0.5">
                  <Target className="size-4" aria-hidden /> {t("trilha.ctaContinuar")}
                </Link>
              ) : sel.estado === "dominado" ? (
                <Link to="/ghost"
                  className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-primary/15 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-primary ring-1 ring-primary/30 hover:bg-primary/25">
                  <RotateCw className="size-4" aria-hidden /> {t("trilha.ctaRevisar")}
                </Link>
              ) : sel.estado === "comprovado" ? (
                <Link to="/evolucao"
                  className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-sky-500/15 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-sky-300 ring-1 ring-sky-500/30 hover:bg-sky-500/25">
                  {t("trilha.ctaRelatorio")} <ArrowRight className="size-4" aria-hidden />
                </Link>
              ) : (
                <p className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-muted/10 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-muted-foreground ring-1 ring-border">
                  <Lock className="size-4" aria-hidden /> {t("trilha.ctaBloqueado")}
                </p>
              )}
              <Link to="/leak-trainer"
                className="mt-2 block text-center font-mono text-[11px] font-bold uppercase tracking-widest text-primary/80 hover:text-primary hover:underline">
                {t("trilha.treinarOutra")}
              </Link>
            </div>
          )}

          <DailyChallengeCard />

          {/* praticar: nada se perde — as outras portas continuam a um clique */}
          <div className="rounded-2xl border border-border bg-card/60 p-3">
            <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("trilha.praticar")}</p>
            <div className="grid grid-cols-2 gap-2">
              <Link to="/ghost" className="flex items-center gap-2 rounded-lg bg-background/60 px-2.5 py-2 ring-1 ring-border transition-colors hover:ring-primary/40">
                <RotateCw className="size-3.5 shrink-0 text-primary" aria-hidden />
                <span className="truncate text-[11px] font-bold text-foreground">{t("trainer.review.title")}</span>
              </Link>
              <Link to="/academy" className="flex items-center gap-2 rounded-lg bg-background/60 px-2.5 py-2 ring-1 ring-border transition-colors hover:ring-violet-500/40">
                <GraduationCap className="size-3.5 shrink-0 text-violet-400" aria-hidden />
                <span className="truncate text-[11px] font-bold text-foreground">{t("academy.title")}</span>
              </Link>
            </div>
            <Link to="/training" className="mt-2 block text-center text-[10.5px] text-muted-foreground hover:text-foreground hover:underline">
              {t("trilha.perfilNota")}
            </Link>
          </div>
        </div>
      </div>
    </HudLayout>
  );
}
