import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Flame, GraduationCap, Lock, RotateCw, Star, Target, Trophy } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { AchievementMedal, EmblemIcon, type MedalEmblem } from "@/components/hud/AchievementMedal";
import { DailyChallengeCard } from "@/components/training/DailyChallengeCard";
import { training, progression } from "@/lib/api";
import { montarTrilha, emblemaDoCenario, emblemaDoCriterio, placarDaTrilha,
  criteriosDoNo, type NoDaTrilha } from "@/lib/trilhaTreino";
import { useSpotLabel } from "@/lib/spotLabel";
import { cn } from "@/lib/utils";

/**
 * Training v2 — COCKPIT DE SESSÃO (v3 do redesign, síntese do painel de design).
 *
 * A decisão de hierarquia que o painel cravou: missão > jornada. O leak ATIVO domina a tela
 * como painel de missão, com os 5 critérios do gate como MOSTRADORES (medalha que se
 * materializa: contorno cinza → arco teal de progresso → ouro cheia). A trilha inteira
 * colapsa numa RÉGUA horizontal de medalhas no topo, com o placar permanente à direita —
 * bb COMPROVADOS somam só o que o jogo real validou (a proposta do chart caiu por um eixo
 * que mentia; aqui número só entra auditado). Regressão nunca some: traço vermelho na régua
 * + bloco com os números no painel. Ver project_redesign_trilha_training.
 *
 * Zero motor novo: progression.status + training.overview, os mesmos da tela clássica
 * (intacta em /training).
 */

/** Medalha EM CONSTRUÇÃO do critério: contorno cinza + arco de progresso teal. Os TRÊS
 *  estados do mostrador são inequívocos de propósito (correção obrigatória do crítico):
 *  ouro cheia = cumprido · arco+valor = em progresso · cinza sem arco = não iniciado.
 *  Cadeado NUNCA aparece aqui — cadeado é vocabulário de trilha bloqueada. */
function MedalhaEmConstrucao({ emblem, pct, size = 48 }: { emblem: MedalEmblem; pct: number; size?: number }) {
  const C = 2 * Math.PI * 21;
  const on = C * Math.max(0, Math.min(1, pct));
  return (
    <svg width={size} height={size} viewBox="-2 -2 52 52" aria-hidden>
      <circle cx="24" cy="24" r="21" fill="#0d1424" stroke="#3a465c" strokeWidth="1.6" strokeOpacity=".7" />
      <circle cx="24" cy="24" r="17.4" fill="hsl(var(--background))" stroke="#3a465c" strokeWidth=".8" strokeOpacity=".5" />
      <g opacity=".55"><EmblemIcon emblem={emblem} size={48} color="#8f9aa6" /></g>
      {pct > 0 && (
        <circle cx="24" cy="24" r="21" fill="none" stroke="#2DD4BF" strokeWidth="2.6"
          strokeLinecap="round" strokeDasharray={`${on.toFixed(1)} ${C.toFixed(1)}`}
          transform="rotate(-90 24 24)" />
      )}
    </svg>
  );
}

/** Disco do nó ATIVO: aro teal (vermelho se reaberto) com halo pulsando. */
function DiscoAtivo({ emblem, reaberto, size = 76 }: { emblem: MedalEmblem; reaberto: boolean; size?: number }) {
  const cor = reaberto ? "#f87171" : "#2DD4BF";
  return (
    <svg width={size} height={size} viewBox="-3 -3 54 54" className="shrink-0 drop-shadow-[0_5px_8px_rgba(0,0,0,0.55)]" aria-hidden>
      <circle cx="24" cy="24" r="23" fill="none" stroke={cor} strokeWidth="1.2" opacity=".5">
        <animate attributeName="r" values="23;24.4;23" dur="1.9s" repeatCount="indefinite" />
        <animate attributeName="opacity" values=".5;.12;.5" dur="1.9s" repeatCount="indefinite" />
      </circle>
      <circle cx="24" cy="24" r="21" fill={reaberto ? "#3b1214" : "#0e3a34"} />
      <circle cx="24" cy="24" r="21" fill="none" stroke={cor} strokeWidth="2.4" />
      <circle cx="24" cy="24" r="17" fill="hsl(var(--background))" />
      <circle cx="24" cy="24" r="17" fill="none" stroke={cor} strokeOpacity="0.5" strokeWidth="1" />
      <ellipse cx="18" cy="15" rx="13" ry="9" fill="rgba(255,255,255,0.12)" />
      <EmblemIcon emblem={emblem} size={48} color={cor} />
    </svg>
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
  const placar = useMemo(() => placarDaTrilha(nos), [nos]);
  const idxAtivo = nos.findIndex((n) => n.estado === "ativo");
  const [selKey, setSelKey] = useState<string | null>(null);
  const sel: NoDaTrilha | null =
    nos.find((n) => n.key === selKey) ?? (idxAtivo >= 0 ? nos[idxAtivo] : nos[0]) ?? null;
  const emConsulta = !!sel && sel.estado !== "ativo";

  // a régua centra o nó ativo ao montar (o "você está aqui" chega visível sem scroll manual)
  const reguaRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = reguaRef.current?.querySelector('[data-ativo="1"]');
    if (el) el.scrollIntoView({ inline: "center", block: "nearest" });
  }, [nos.length]);

  const gate = sel ? criteriosDoNo(sel.item) : { ok: 0, total: 0 };

  const painelMissao = (n: NoDaTrilha) => {
    const emblem = emblemaDoCenario(n.item.scenario);
    const criterios = n.item.mastery?.criterios ?? [];
    return (
      <div className={cn("rounded-2xl border p-5",
        n.reaberto ? "border-red-500/40 bg-red-500/[0.04]"
                   : "border-primary/30 bg-[radial-gradient(ellipse_120%_60%_at_50%_0%,rgba(45,212,191,.07),hsl(var(--card))_70%)]")}>
        <div className="flex items-center gap-4">
          <DiscoAtivo emblem={emblem} reaberto={n.reaberto} />
          <div className="min-w-0">
            <p className={cn("font-mono text-[10.5px] font-bold uppercase tracking-[0.18em]",
                             n.reaberto ? "text-red-400" : "text-primary")}>
              {n.reaberto ? t("trilha.ctxReaberto") : t("trilha.missaoAtiva")}
              {typeof n.item.ev_loss_bb === "number" && (
                <span className="text-muted-foreground"> · {t("trilha.medidos",
                  { ev: Math.abs(n.item.ev_loss_bb).toFixed(1), hands: n.item.hands ?? 0 })}</span>
              )}
            </p>
            <h2 className="truncate font-heading text-2xl font-bold leading-tight text-foreground">
              {spotLabel(n.item, { fallback: n.item.titulo })}
            </h2>
            <p className="text-[12.5px] text-muted-foreground">{t("trilha.feche5")}</p>
          </div>
        </div>

        {/* os 5 mostradores — o centro visual da tela */}
        {criterios.length > 0 && (
          <div className="mt-5 grid grid-cols-2 gap-2.5 sm:grid-cols-5">
            {criterios.map((c) => {
              const pct = c.alvo > 0 ? c.atual / c.alvo : 0;
              const estado = c.ok ? "done" : pct > 0 ? "prog" : "zero";
              return (
                <div key={c.key} title={c.desc}
                  className={cn("flex flex-col items-center rounded-xl border px-2 py-3 text-center",
                    estado === "done" ? "border-[#f5c542]/35 bg-background/60"
                                      : "border-border bg-background/50")}>
                  {c.ok
                    ? <AchievementMedal tier="gold" emblem={emblemaDoCriterio(c.key)} size={48} label="" />
                    : <MedalhaEmConstrucao emblem={emblemaDoCriterio(c.key)} pct={pct} />}
                  <span className={cn("mt-1.5 font-mono text-[13px] font-bold tabular-nums",
                    estado === "done" ? "text-[#f5c542]" : estado === "prog" ? "text-foreground" : "text-muted-foreground")}>
                    {c.atual}/{c.alvo}
                  </span>
                  <span className="text-[11px] leading-tight text-muted-foreground">{c.label}</span>
                </div>
              );
            })}
          </div>
        )}

        {n.reaberto && n.item.validacao && (
          <div className="mt-4 rounded-xl border border-red-500/35 bg-red-500/[0.07] p-3 text-[12.5px] leading-snug text-red-200">
            {t("trilha.reabertoNums", {
              antes: n.item.validacao.taxa_antes_ajustada ?? n.item.validacao.taxa_antes,
              depois: n.item.validacao.taxa_depois, n: n.item.validacao.n_depois,
            })}{" "}{t("trilha.reabertoNota")}
          </div>
        )}

        <div className="mt-5 flex items-center justify-between">
          <span className="font-mono text-[12px] font-bold uppercase tracking-[0.14em] text-amber-300">
            {t("trilha.gate")} · {gate.ok}/{gate.total}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground">{t("trilha.gateNota")}</span>
        </div>
        <Link to="/leak-trainer?origem=trilha"
          className="mt-2.5 flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3.5 font-mono text-base font-extrabold uppercase tracking-wider text-primary-foreground shadow-[0_4px_0_rgba(23,138,124,1)] transition-transform active:translate-y-0.5">
          <Target className="size-5" aria-hidden />
          {n.reaberto ? t("trilha.ctaRetreinar") : t("trilha.ctaTreinarAgora")}
        </Link>
        <Link to="/leak-trainer"
          className="mt-2 block text-center font-mono text-[10.5px] font-bold uppercase tracking-[0.14em] text-primary/70 hover:text-primary hover:underline">
          {t("trilha.treinarOutra")}
        </Link>
      </div>
    );
  };

  const painelConsulta = (n: NoDaTrilha) => {
    const emblem = emblemaDoCenario(n.item.scenario);
    return (
      <div className="rounded-2xl border border-border bg-card p-5">
        <button type="button" onClick={() => setSelKey(null)}
          className="mb-3 flex items-center gap-1.5 font-mono text-[10.5px] font-bold uppercase tracking-[0.14em] text-primary hover:underline">
          <ArrowLeft className="size-3.5" aria-hidden /> {t("trilha.voltarMissao")}
        </button>
        <div className="flex items-center gap-4">
          {n.estado === "bloqueado"
            ? <AchievementMedal tier="silver" emblem={emblem} locked size={64} label="" />
            : <span className="relative inline-flex">
                <AchievementMedal tier={n.estado === "comprovado" ? "diamond" : "gold"} emblem={emblem}
                  size={64} label="" className={cn(n.reaberto && "opacity-60 saturate-50")} />
              </span>}
          <div className="min-w-0">
            <p className={cn("font-mono text-[10.5px] font-bold uppercase tracking-[0.18em]",
              n.reaberto ? "text-red-400"
                : n.estado === "comprovado" ? "text-sky-300"
                : n.estado === "dominado" ? "text-emerald-400" : "text-muted-foreground")}>
              {n.reaberto ? t("trilha.ctxReaberto") : t(`trilha.ctx.${n.estado}`)}
            </p>
            <h2 className="truncate font-heading text-xl font-bold leading-tight text-foreground">
              {spotLabel(n.item, { fallback: n.item.titulo })}
            </h2>
            {typeof n.item.ev_loss_bb === "number" && n.item.ev_loss_bb !== 0 && (
              <p className="font-mono text-[12px] tabular-nums text-muted-foreground">
                {t("trilha.medidos", { ev: Math.abs(n.item.ev_loss_bb).toFixed(1), hands: n.item.hands ?? 0 })}
              </p>
            )}
          </div>
        </div>

        {n.estado === "comprovado" && n.item.validacao && (
          <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">
            {t("trilha.provaNums", {
              antes: n.item.validacao.taxa_antes_ajustada ?? n.item.validacao.taxa_antes,
              depois: n.item.validacao.taxa_depois,
            })}
          </p>
        )}
        {n.estado === "bloqueado" && (
          <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">{t("trilha.bloqueadoNota")}</p>
        )}

        {n.estado === "dominado" ? (
          <Link to="/ghost"
            className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-primary/15 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-primary ring-1 ring-primary/30 hover:bg-primary/25">
            <RotateCw className="size-4" aria-hidden /> {t("trilha.ctaRevisar")}
          </Link>
        ) : n.estado === "comprovado" ? (
          <Link to="/evolucao"
            className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-sky-500/15 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-sky-300 ring-1 ring-sky-500/30 hover:bg-sky-500/25">
            {t("trilha.ctaRelatorio")}
          </Link>
        ) : (
          <p className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-muted/10 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-muted-foreground ring-1 ring-border">
            <Lock className="size-4" aria-hidden /> {t("trilha.ctaBloqueado")}
          </p>
        )}
      </div>
    );
  };

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

      {/* ── FAIXA A: a régua da trilha + placar ── */}
      <div className="mb-4 flex items-center gap-4 rounded-2xl border border-border bg-background/80 px-4 py-2.5">
        <div ref={reguaRef} className="relative flex flex-1 items-start gap-3 overflow-x-auto pb-1 pt-1">
          <div className="pointer-events-none absolute left-2 right-2 top-[23px] border-t-2 border-dashed border-border" aria-hidden />
          {nos.map((n, i) => {
            const emblem = emblemaDoCenario(n.item.scenario);
            const mostraRotulo = n.estado === "ativo" || sel?.key === n.key
              || Math.abs(i - idxAtivo) === 1;
            return (
              <button key={n.key} type="button" onClick={() => setSelKey(n.estado === "ativo" ? null : n.key)}
                data-ativo={n.estado === "ativo" ? "1" : undefined}
                title={spotLabel(n.item, { fallback: n.item.titulo })}
                className={cn("relative z-[1] w-[64px] shrink-0 text-center transition-transform hover:-translate-y-0.5",
                              sel?.key === n.key && "scale-105")}>
                {n.estado === "ativo" ? (
                  <span className="inline-flex"><DiscoAtivo emblem={emblem} reaberto={n.reaberto} size={48} /></span>
                ) : n.estado === "bloqueado" ? (
                  <AchievementMedal tier="silver" emblem={emblem} locked size={44} label="" />
                ) : (
                  <span className="relative inline-flex">
                    <AchievementMedal tier={n.estado === "comprovado" ? "diamond" : "gold"} emblem={emblem}
                      size={44} label="" className={cn(n.reaberto && "opacity-60 saturate-50")} />
                    {!n.reaberto && (
                      <span className={cn("absolute -right-0.5 -top-0.5 flex size-3.5 items-center justify-center rounded-full text-[8px] font-black",
                        n.estado === "comprovado" ? "bg-sky-300 text-sky-950" : "bg-emerald-400 text-emerald-950")}>
                        {n.estado === "comprovado" ? "◆" : "✓"}
                      </span>
                    )}
                  </span>
                )}
                {n.reaberto && <span className="mx-auto mt-0.5 block h-[3px] w-7 rounded bg-red-400" aria-hidden />}
                <span className={cn("mt-0.5 block truncate text-[9.5px] leading-tight",
                  mostraRotulo ? "text-foreground" : "text-transparent select-none")}>
                  {spotLabel(n.item, { fallback: n.item.titulo, stack: false })}
                </span>
              </button>
            );
          })}
          {(status?.restantes ?? 0) > 0 && (
            <span className="mt-3 shrink-0 self-start font-mono text-[9.5px] uppercase tracking-[0.14em] text-muted-foreground/70">
              {t("trilha.maisAdiante", { count: status!.restantes })}
            </span>
          )}
        </div>
        <div className="shrink-0 text-right">
          {placar.bbComprovados > 0 && (
            <p className="font-mono text-[15px] font-extrabold tabular-nums text-primary">
              +{placar.bbComprovados}bb
            </p>
          )}
          <p className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-muted-foreground">
            {placar.bbComprovados > 0 ? t("trilha.placarBb") + " · " : ""}
            {t("trilha.placarDominados", { n: placar.dominados, m: placar.total })}
          </p>
        </div>
      </div>

      {/* ── FAIXAS B + C ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          {sel ? (emConsulta ? painelConsulta(sel) : painelMissao(sel)) : (
            <div className="rounded-2xl border border-border bg-card/40 p-8 text-center text-sm text-muted-foreground">
              {t("trilha.vazia")}
            </div>
          )}
        </div>

        <aside className="space-y-2.5">
          <div className="flex items-center justify-between rounded-xl border border-border bg-card/60 px-3.5 py-2.5">
            <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              <Flame className="size-3.5 text-amber-400" aria-hidden /> {t("trilha.statStreak")}
            </span>
            <span className="font-mono text-sm font-extrabold tabular-nums text-amber-300">{overview?.xp.streak ?? "–"}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-border bg-card/60 px-3.5 py-2.5">
            <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              <Star className="size-3.5 text-primary" aria-hidden /> XP
            </span>
            <span className="font-mono text-sm font-extrabold tabular-nums text-foreground">{overview?.xp.xp_total ?? "–"}</span>
          </div>
          <Link to="/leaderboard" className="flex items-center justify-between rounded-xl border border-border bg-card/60 px-3.5 py-2.5 transition-colors hover:border-primary/40">
            <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              <Trophy className="size-3.5 text-primary" aria-hidden /> {t("trilha.statLiga")}
            </span>
            <span className="font-mono text-[10px] text-primary">→</span>
          </Link>

          <DailyChallengeCard />

          <div className="rounded-xl border border-border bg-card/60 p-3">
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
        </aside>
      </div>
    </HudLayout>
  );
}
