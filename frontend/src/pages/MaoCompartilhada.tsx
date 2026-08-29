import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, CheckCircle2, ChevronLeft, ChevronRight, Heart, MessageSquare,
         Pause, Pencil, Play, Trash2, XCircle } from "lucide-react";

import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { sharedHand, type ReplayData, type SharedHandPayload, type SharedHandStep } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * A página PÚBLICA de uma mão compartilhada — a única tela do produto que sai dele.
 *
 * ── v4 (30/08, feedback do dono sobre a v3 na tela) ───────────────────────────────────────
 *
 * A v3 espremia a mesa numa coluna estreita e gastava rodapé com um segundo CTA. Aqui a mesa
 * é a protagonista (página larga, coluna de comentários fixa em 300px), os controles ganham
 * autoplay, o CTA de rodapé saiu (o do cabeçalho basta), entrou o VOLTAR e o CURTIR — a
 * curtida usa o mesmo agregado anônimo dos votos, e o coração do feed soma tudo.
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
  const navigate = useNavigate();
  const [dados, setDados] = useState<SharedHandPayload | null>(null);
  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [erro, setErro] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [tocando, setTocando] = useState(false);
  const [curtiu, setCurtiu] = useState(false);
  const [curtidas, setCurtidas] = useState(0);
  const [comentario, setComentario] = useState("");
  const [editando, setEditando] = useState<number | null>(null);
  const [textoEdicao, setTextoEdicao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    Promise.all([sharedHand.ler(token), sharedHand.replay(token)])
      .then(([d, r]) => {
        setDados(d);
        setReplay(r);
        setCurtidas(d.votos?.like ?? 0);
        try { setCurtiu(localStorage.getItem(`gl_like_${token}`) === "1"); } catch { /* privado */ }
      })
      .catch(() => setErro(true));
  }, [token]);

  // autoplay: um passo por batida; para sozinho no fim
  useEffect(() => {
    if (!tocando || !replay) return;
    timer.current = setInterval(() => {
      setStepIdx((i) => {
        if (i >= (replay.timeline?.length ?? 1) - 1) { setTocando(false); return i; }
        return i + 1;
      });
    }, 1300);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [tocando, replay]);

  const voltar = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate(user ? "/maos" : "/");
  };

  const curtir = async () => {
    if (curtiu) return;
    setCurtiu(true);                                  // otimista: curtida não pode travar a tela
    setCurtidas((n) => n + 1);
    try { localStorage.setItem(`gl_like_${token}`, "1"); } catch { /* privado */ }
    try {
      const r = await sharedHand.votar(token, "like");
      setCurtidas(r.votos?.like ?? 0);
    } catch { /* rate limit: a curtida local fica, o agregado corrige na proxima carga */ }
  };

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
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-4 py-2.5">
          <div className="flex items-center gap-3">
            <button type="button" onClick={voltar}
                    className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-primary">
              <ArrowLeft className="size-3.5" aria-hidden /> {t("sharedHand.voltar")}
            </button>
            <Link to="/"><img src={logoHorizontal} alt="GrindLab" className="h-6 w-auto" /></Link>
          </div>
          <Link to="/login"
                className="rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/15">
            {t("sharedHand.analisarMinhas")}
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1500px] px-4 py-4">
        {dados.pergunta && (
          <div className="mb-3 rounded-xl border border-primary/30 bg-primary/5 px-4 py-2.5">
            <p className="text-[14px] font-medium text-foreground">
              <span className="mr-2 font-mono text-[9px] font-bold uppercase tracking-widest text-primary">
                {t("sharedHand.perguntaDoDono")}
              </span>
              {dados.pergunta}
              {dados.autor && (
                <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                  {t("sharedHand.por")} <span className="text-primary">{dados.autor}</span>
                </span>
              )}
            </p>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          {/* ── a mesa, protagonista ── */}
          <div className="min-w-0">
            <div className="rounded-xl border border-border bg-hud-surface p-2">
              {step && (
                <div className="mx-auto w-full" style={{ aspectRatio: "1160 / 710" }}>
                  <PokerTableV3
                    step={step}
                    hero={replay.hero}
                    heroCards={replay.hero_cards ?? []}
                    bb={replay.bb}
                    fill
                  />
                </div>
              )}
              <div className="mt-1.5 flex items-center justify-center gap-2 pb-1">
                <button type="button" onClick={() => { setTocando(false); setStepIdx((i) => Math.max(0, i - 1)); }}
                        disabled={stepIdx === 0}
                        aria-label={t("sharedHand.anterior")}
                        className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30">
                  <ChevronLeft className="size-4" aria-hidden />
                </button>
                <button type="button" onClick={() => setTocando((v) => !v)}
                        aria-label={tocando ? t("sharedHand.pausar") : t("sharedHand.reproduzir")}
                        className="rounded-md bg-primary p-2 text-primary-foreground transition-opacity hover:opacity-90">
                  {tocando ? <Pause className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
                </button>
                <button type="button" onClick={() => { setTocando(false); setStepIdx((i) => Math.min(timeline.length - 1, i + 1)); }}
                        disabled={stepIdx >= timeline.length - 1}
                        aria-label={t("sharedHand.proxima")}
                        className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30">
                  <ChevronRight className="size-4" aria-hidden />
                </button>
                <span className="ml-2 font-mono text-[11px] tabular-nums text-muted-foreground">
                  {timeline.length ? stepIdx + 1 : 0}/{timeline.length}
                </span>
              </div>
            </div>

            {dados.passos.length > 0 && (
              <div className="mt-3 rounded-xl border border-border bg-hud-surface px-4 py-3">
                <p className="mb-1.5 font-mono text-[9.5px] font-bold uppercase tracking-widest text-muted-foreground">
                  {t("sharedHand.oQueDisse")}
                </p>
                <div className="flex flex-col gap-1">
                  {dados.passos.map((p, i) => <Veredito key={i} step={p} t={t} />)}
                </div>
              </div>
            )}
          </div>

          {/* ── direita: curtir + comentários ── */}
          <aside className="rounded-xl border border-border bg-hud-surface p-4 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto">
            <div className="mb-2 flex items-center justify-between">
              <p className="flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                <MessageSquare className="size-3" aria-hidden />
                {t("sharedHand.comentarios")} {dados.comentarios.length > 0 && `(${dados.comentarios.length})`}
              </p>
              <button type="button" onClick={curtir} aria-pressed={curtiu}
                      aria-label={t("sharedHand.curtir")}
                      className={cn(
                        "flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[10.5px] tabular-nums transition-colors",
                        curtiu
                          ? "border-red-400/40 bg-red-400/10 text-red-400"
                          : "border-border text-muted-foreground hover:border-red-400/40 hover:text-red-400",
                      )}>
                <Heart className={cn("size-3", curtiu && "fill-current")} aria-hidden />
                {curtidas}
              </button>
            </div>

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
      </main>
    </div>
  );
}
