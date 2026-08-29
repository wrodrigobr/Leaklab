import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Crosshair, Flag, Play, X } from "lucide-react";

import { ritual, type RitualDebrief } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * O ritual da sessão: check-in antes de jogar, debriefing depois — o laço que fecha.
 *
 * ── O desenho (30/08, último item do benchmark) ───────────────────────────────────────────
 *
 * O concorrente pergunta e devolve zero. Aqui o foco vem do SEU leak mais caro medido, a
 * linha de base é selada no check-in (o debriefing compara contra a régua do momento da
 * promessa), e o import seguinte fecha o laço: "você prometeu X; nesta sessão fez Y contra
 * os seus Z de sempre".
 *
 * Três estados: sem check-in (formulário), em sessão (a promessa na tela + aquecer), e
 * debriefing (quando o torneio mais novo é posterior ao check-in). A banca é auto-resposta:
 * o produto não conhece a banca do jogador, e fingir que calcula seria pior que perguntar.
 */

interface Props {
  /** id interno do torneio mais recente — vira o debriefing quando importado após o check-in */
  ultimoTorneioId?: number | null;
  ultimoImportadoEm?: string | null;
}

function rotuloDoSpot(spot: string, t: (k: string) => string): string {
  const [street, best] = spot.split("/");
  return `${t(`ritual.street.${street}`) || street} · ${t(`ritual.certoEra`)} ${best}`;
}

export function RitualDaSessao({ ultimoTorneioId, ultimoImportadoEm }: Props) {
  const { t } = useTranslation("dashboard");
  const qc = useQueryClient();
  const [bancaOk, setBancaOk] = useState<boolean | null>(null);

  const { data } = useQuery({ queryKey: ["session-ritual"], queryFn: ritual.estado,
                              staleTime: 60_000 });

  const abrir = useMutation({
    mutationFn: () => ritual.checkin(bancaOk, data?.foco_sugerido?.spot ?? null),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["session-ritual"] }),
  });
  const fechar = useMutation({
    mutationFn: (p: { id: number; tid: number }) => ritual.fechar(p.id, p.tid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["session-ritual"] }),
  });

  // O debriefing só entra quando existe torneio importado DEPOIS do check-in aberto.
  const ck = data?.checkin;
  const temDebrief = Boolean(
    ck && ultimoTorneioId && ultimoImportadoEm && ck.created_at &&
    new Date(ultimoImportadoEm) > new Date(ck.created_at),
  );
  const { data: deb } = useQuery<RitualDebrief>({
    queryKey: ["session-debrief", ultimoTorneioId],
    queryFn: () => ritual.debrief(ultimoTorneioId as number),
    enabled: temDebrief,
    staleTime: 300_000,
  });

  if (!data?.available) return null;

  // ── estado 3: debriefing ──────────────────────────────────────────────────────────────
  if (ck && temDebrief && deb) {
    const foco = deb.foco;
    const melhorou = foco?.taxa_sessao != null && foco.base.taxa != null
      ? foco.taxa_sessao <= foco.base.taxa : null;
    return (
      <section className="rounded-xl border border-primary/30 bg-primary/5 px-5 py-4">
        <p className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
          <Flag className="size-3" aria-hidden /> {t("ritual.debrief.titulo")}
        </p>

        {foco && (
          <div className="mt-2.5">
            <p className="text-[13px] text-muted-foreground">
              {t("ritual.debrief.prometeu")}{" "}
              <span className="font-medium text-foreground">{rotuloDoSpot(foco.spot, t)}</span>
            </p>
            {foco.taxa_sessao == null ? (
              /* sem spot do foco na sessão: nem cumprida nem quebrada — nunca 0% */
              <p className="mt-1 text-[13px] text-muted-foreground">{t("ritual.debrief.semSpot")}</p>
            ) : (
              <p className="mt-1 text-[13px]">
                <span className={cn("font-mono font-bold tabular-nums",
                                    melhorou ? "text-primary" : "text-amber-400")}>
                  {Math.round(foco.taxa_sessao * 100)}%
                </span>{" "}
                <span className="text-muted-foreground">
                  {t("ritual.debrief.deErro", { n: foco.sessao.n })}{" "}
                  {foco.base.taxa != null &&
                    t("ritual.debrief.contraBase", { pct: Math.round(foco.base.taxa * 100) })}
                </span>
              </p>
            )}
          </div>
        )}

        {deb.mao_gatilho && (
          <p className="mt-2 text-[12px] text-muted-foreground">
            {t("ritual.debrief.gatilho")}{" "}
            <Link
              to={`/replayer?t=${deb.tournament_id}&h=${deb.mao_gatilho.hand_id}`}
              className="font-mono text-primary hover:underline"
            >
              {deb.mao_gatilho.street} · {deb.mao_gatilho.action_taken}
              {deb.mao_gatilho.ev_loss_bb != null && ` · −${Number(deb.mao_gatilho.ev_loss_bb).toFixed(1)}bb`}
            </Link>
          </p>
        )}

        <button
          type="button"
          onClick={() => fechar.mutate({ id: ck.id, tid: deb.tournament_id })}
          className="mt-3 rounded-lg bg-primary px-3.5 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90"
        >
          {t("ritual.debrief.fechar")}
        </button>
      </section>
    );
  }

  // ── estado 2: em sessão ───────────────────────────────────────────────────────────────
  if (ck) {
    return (
      <section className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-hud-surface px-5 py-3.5">
        <CheckCircle2 className="size-4 shrink-0 text-primary" aria-hidden />
        <p className="min-w-0 flex-1 text-[13px] text-muted-foreground">
          {t("ritual.emSessao")}{" "}
          {ck.foco_spot
            ? <span className="font-medium text-foreground">{rotuloDoSpot(ck.foco_spot, t)}</span>
            : <span className="font-medium text-foreground">{t("ritual.focoLivre")}</span>}
          {" · "}{t("ritual.debriefQuandoImportar")}
        </p>
      </section>
    );
  }

  // ── estado 1: check-in ────────────────────────────────────────────────────────────────
  const foco = data.foco_sugerido;
  return (
    <section className="rounded-xl border border-border bg-hud-surface px-5 py-4">
      <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
        {t("ritual.titulo")}
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-2.5">
          <span className="text-[13px] text-muted-foreground">{t("ritual.banca")}</span>
          {([true, false] as const).map((v) => (
            <button key={String(v)} type="button" onClick={() => setBancaOk(v)}
                    className={cn(
                      "rounded-md border px-2.5 py-1 font-mono text-[10.5px] font-bold uppercase transition-colors",
                      bancaOk === v
                        ? v ? "border-primary/50 bg-primary/10 text-primary"
                            : "border-amber-400/50 bg-amber-400/10 text-amber-400"
                        : "border-border text-muted-foreground hover:text-foreground",
                    )}>
              {v ? t("ritual.sim") : t("ritual.nao")}
            </button>
          ))}
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <Crosshair className="size-3.5 shrink-0 text-red-400" aria-hidden />
          <span className="truncate text-[13px]">
            <span className="text-muted-foreground">{t("ritual.focoHoje")} </span>
            {foco
              ? <span className="font-medium text-foreground">{rotuloDoSpot(foco.spot, t)}</span>
              : <span className="font-medium text-foreground">{t("ritual.focoLivre")}</span>}
            {foco && (
              <span className="font-mono text-[10.5px] text-muted-foreground/70">
                {" "}({t("ritual.medidoEm", { n: foco.n })})
              </span>
            )}
          </span>
        </div>
      </div>

      {bancaOk === false && (
        /* a resposta honesta ao "não": a sugestão de não jogar, sem bloquear ninguém */
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-amber-400">
          <X className="size-3" aria-hidden /> {t("ritual.bancaNao")}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => abrir.mutate()}
          disabled={abrir.isPending}
          className="rounded-lg bg-primary px-3.5 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Play className="mr-1.5 inline size-3" aria-hidden />{t("ritual.vouJogar")}
        </button>
        {foco && (
          <Link
            to="/leak-trainer"
            className="rounded-lg border border-border px-3.5 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
          >
            {t("ritual.aquecer")}
          </Link>
        )}
      </div>
    </section>
  );
}
