import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, ChevronLeft, ChevronRight, MessageSquare, Pencil, Trash2, XCircle } from "lucide-react";

import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { sharedHand, type ReplayData, type SharedHandPayload, type SharedHandStep } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * A página PÚBLICA de uma mão compartilhada — a única tela do produto que sai dela.
 *
 * ── v3 (30/08, desenho do dono) ───────────────────────────────────────────────────────────
 *
 * Sem quiz, sem modos: o link abre a mão NO REPLAYER (a mesa de verdade, anonimizada no
 * backend — todo nick de poker vira posição), o visitante assiste a mão inteira com os
 * controles, e comenta DEPOIS de assistir. Como não há botões de ação, os comentários vivem
 * na coluna da direita: textbox no topo para quem assiste, lista abaixo, com editar/excluir
 * quando o comentário é seu. Abaixo da mesa, o que o GrindLab disse de cada decisão — a
 * vitrine que faz o link valer.
 */

function Veredito({ step, t }: {
  step: SharedHandStep; t: (k: string, o?: Record<string, unknown>) => string;
}) {
  const errou = step.label && step.label !== "correct" && step.label !== "gto_correct";
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
      {errou
        ? <XCircle className="size-3.5 shrink-0 text-amber-400" aria-hidden />
        : <CheckCircle2 className="size-3.5 shrink-0 text-primary" aria-hidden />}
      <span className="font-mono text-[10px] uppercase text-muted-foreground">{step.street}</span>
      <span className="text-muted-foreground">{t("sharedHand.jogou")}</span>
      <span className="font-mono font-bold uppercase text-foreground">{step.action_taken}</span>
      {errou && step.best_action && (
        <>
          <span className="text-muted-foreground">· {t("sharedHand.melhorEra")}</span>
          <span className="font-mono font-bold uppercase text-primary">{step.best_action}</span>
        </>
      )}
    </div>
  );
}

export default function MaoCompartilhada() {
  const { token = "" } = useParams();
  const { t } = useTranslation("common");
  const { user } = useAuth();
  const [dados, setDados] = useState<SharedHandPayload | null>(null);
  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [erro, setErro] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [comentario, setComentario] = useState("");
  const [editando, setEditando] = useState<number | null>(null);
  const [textoEdicao, setTextoEdicao] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    Promise.all([sharedHand.ler(token), sharedHand.replay(token)])
      .then(([d, r]) => { setDados(d); setReplay(r); })
      .catch(() => setErro(true));
  }, [token]);

  const recarregar = async () => setDados(await sharedHand.ler(token));

  const comentar = async () => {
    const texto = comentario.trim();
    if (!texto) return;
    setEnviando(true);
    try {
      await sharedHand.comentar(token, texto);
      await recarregar();
      setComentario("");
    } finally {
      setEnviando(false);
    }
  };

  const salvarEdicao = async (id: number) => {
    const texto = textoEdicao.trim();
    if (!texto) return;
    await sharedHand.editarComentario(token, id, texto);
    setEditando(null);
    await recarregar();
  };

  const excluir = async (id: number) => {
    await sharedHand.apagarComentario(token, id);
    await recarregar();
  };

  if (erro) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <img src={logoHorizontal} alt="GrindLab" className="h-8 w-auto" />
        <p className="text-sm text-muted-foreground">{t("sharedHand.naoExiste")}</p>
        <Link to="/" className="font-mono text-xs uppercase tracking-wider text-primary hover:underline">
          {t("sharedHand.conhecer")}
        </Link>
      </div>
    );
  }
  if (!dados || !replay) {
    return <div className="flex min-h-dvh items-center justify-center bg-background">
      <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>;
  }

  const timeline = replay.timeline ?? [];
  const step = timeline[Math.min(stepIdx, Math.max(0, timeline.length - 1))];

  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-border bg-hud-surface/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/"><img src={logoHorizontal} alt="GrindLab" className="h-7 w-auto" /></Link>
          <Link to="/login"
                className="rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/15">
            {t("sharedHand.analisarMinhas")}
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5">
        {dados.pergunta && (
          <div className="mb-4 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
            <p className="font-mono text-[9px] font-bold uppercase tracking-widest text-primary">
              {t("sharedHand.perguntaDoDono")}
            </p>
            <p className="mt-1 text-[15px] font-medium text-foreground">{dados.pergunta}</p>
            {dados.autor && (
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                {t("sharedHand.por")} <span className="text-primary">{dados.autor}</span>
              </p>
            )}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          {/* ── esquerda: a mesa + controles + o que o GrindLab disse ── */}
          <div className="min-w-0">
            <div className="rounded-xl border border-border bg-hud-surface p-2">
              {step ? (
                <div className="mx-auto w-full" style={{ aspectRatio: "1160 / 710" }}>
                  <PokerTableV3
                    step={step}
                    hero={replay.hero}
                    heroCards={replay.hero_cards ?? []}
                    bb={replay.bb}
                    fill
                  />
                </div>
              ) : (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  {t("sharedHand.naoExiste")}
                </p>
              )}
              <div className="mt-2 flex items-center justify-center gap-3 pb-1">
                <button type="button" onClick={() => setStepIdx((i) => Math.max(0, i - 1))}
                        disabled={stepIdx === 0}
                        aria-label={t("sharedHand.anterior")}
                        className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30">
                  <ChevronLeft className="size-4" aria-hidden />
                </button>
                <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                  {timeline.length ? stepIdx + 1 : 0}/{timeline.length}
                </span>
                <button type="button" onClick={() => setStepIdx((i) => Math.min(timeline.length - 1, i + 1))}
                        disabled={stepIdx >= timeline.length - 1}
                        aria-label={t("sharedHand.proxima")}
                        className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30">
                  <ChevronRight className="size-4" aria-hidden />
                </button>
              </div>
            </div>

            {/* a vitrine: o veredito do GrindLab por decisão do herói */}
            {dados.passos.length > 0 && (
              <div className="mt-3 rounded-xl border border-border bg-hud-surface p-4">
                <p className="mb-2 font-mono text-[9.5px] font-bold uppercase tracking-widest text-muted-foreground">
                  {t("sharedHand.oQueDisse")}
                </p>
                <div className="flex flex-col gap-1.5">
                  {dados.passos.map((p, i) => <Veredito key={i} step={p} t={t} />)}
                </div>
              </div>
            )}
          </div>

          {/* ── direita: comentários (textbox no topo; editar/excluir do dono do comentário) ── */}
          <aside className="rounded-xl border border-border bg-hud-surface p-4 lg:max-h-[80vh] lg:overflow-y-auto">
            <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              <MessageSquare className="size-3" aria-hidden />
              {t("sharedHand.comentarios")} {dados.comentarios.length > 0 && `(${dados.comentarios.length})`}
            </p>

            {user ? (
              <div className="mb-3 flex flex-col gap-1.5">
                <textarea
                  value={comentario}
                  onChange={(e) => setComentario(e.target.value.slice(0, 1000))}
                  placeholder={t("sharedHand.comentarPlaceholder")}
                  rows={2}
                  className="w-full resize-none rounded-lg border border-border bg-background/50 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button type="button" onClick={comentar} disabled={enviando || !comentario.trim()}
                        className="self-end rounded-lg bg-primary px-3.5 py-1.5 font-mono text-[10.5px] font-bold uppercase text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40">
                  {t("sharedHand.enviar")}
                </button>
              </div>
            ) : (
              <p className="mb-3 text-[11.5px] text-muted-foreground">
                <Link to="/login" className="text-primary hover:underline">{t("sharedHand.entrarParaComentar")}</Link>
              </p>
            )}

            {dados.comentarios.length === 0 && (
              <p className="text-[11.5px] text-muted-foreground/70">{t("sharedHand.semComentarios")}</p>
            )}

            {dados.comentarios.map((c) => {
              const meu = user?.username && c.autor === user.username;
              return (
                <div key={c.id} className="group border-t border-border/60 py-2 first:border-t-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-mono text-[10px] font-bold text-primary">{c.autor}</p>
                    {meu && editando !== c.id && (
                      <span className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <button type="button" aria-label={t("sharedHand.editar")}
                                onClick={() => { setEditando(c.id); setTextoEdicao(c.texto); }}
                                className="rounded p-1 text-muted-foreground hover:text-foreground">
                          <Pencil className="size-3" aria-hidden />
                        </button>
                        <button type="button" aria-label={t("sharedHand.excluir")}
                                onClick={() => excluir(c.id)}
                                className="rounded p-1 text-muted-foreground hover:text-destructive">
                          <Trash2 className="size-3" aria-hidden />
                        </button>
                      </span>
                    )}
                  </div>
                  {editando === c.id ? (
                    <div className="mt-1 flex flex-col gap-1.5">
                      <textarea
                        value={textoEdicao}
                        onChange={(e) => setTextoEdicao(e.target.value.slice(0, 1000))}
                        rows={2}
                        className="w-full resize-none rounded-lg border border-border bg-background/50 px-2.5 py-1.5 text-[12.5px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                      <span className="flex justify-end gap-2">
                        <button type="button" onClick={() => setEditando(null)}
                                className="font-mono text-[10px] uppercase text-muted-foreground hover:text-foreground">
                          {t("sharedHand.cancelar")}
                        </button>
                        <button type="button" onClick={() => salvarEdicao(c.id)}
                                className="font-mono text-[10px] font-bold uppercase text-primary hover:underline">
                          {t("sharedHand.salvar")}
                        </button>
                      </span>
                    </div>
                  ) : (
                    <p className="mt-0.5 text-[13px] leading-snug text-foreground">{c.texto}</p>
                  )}
                </div>
              );
            })}
          </aside>
        </div>

        <Link to="/"
              className="mt-4 block rounded-xl bg-primary px-4 py-3 text-center font-mono text-[12px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90">
          {t("sharedHand.cta")}
        </Link>
      </main>
    </div>
  );
}
