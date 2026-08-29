import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, MessageSquare, XCircle } from "lucide-react";

import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { sharedHand, type SharedHandPayload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * A página PÚBLICA de uma mão compartilhada — a única tela do produto que sai dele.
 *
 * ── O desenho (29/08) ─────────────────────────────────────────────────────────────────────
 *
 * 1. A pergunta do dono abre a página; quem chega VOTA na decisão marcada ANTES de ver o
 *    veredito. Mini-desafio, não leitura passiva — depois do voto, revela o mix GTO e o
 *    placar dos outros visitantes.
 * 2. Anônimo vota; comentar exige conta (o formulário aparece logado, o convite aparece
 *    deslogado). O dono da mão é anônimo aqui; quem comenta assina o username.
 * 3. O CTA do fim é o produto se vendendo: "analise as suas mãos".
 */

function parseCartas(raw?: string | null): CardData[] {
  if (!raw) return [];
  const s = raw.replace(/[[\]"',\s]/g, "");
  const out: CardData[] = [];
  for (let i = 0; i + 1 < s.length; i += 2) {
    out.push({ rank: s[i] as CardData["rank"], suit: s[i + 1].toLowerCase() as CardData["suit"] });
  }
  return out;
}

function parseBoard(b?: string[] | string | null): CardData[] {
  if (!b) return [];
  if (Array.isArray(b)) return parseCartas(b.join(""));
  return parseCartas(b);
}

const ACOES_VOTO = ["fold", "call", "raise", "allin"] as const;

export default function MaoCompartilhada() {
  const { token = "" } = useParams();
  const { t } = useTranslation("common");
  const { user } = useAuth();
  const [dados, setDados] = useState<SharedHandPayload | null>(null);
  const [erro, setErro] = useState(false);
  const [votou, setVotou] = useState<string | null>(null);
  const [placar, setPlacar] = useState<Record<string, number>>({});
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    sharedHand.ler(token)
      .then((d) => { setDados(d); setPlacar(d.votos || {}); })
      .catch(() => setErro(true));
  }, [token]);

  const votar = async (acao: string) => {
    setVotou(acao);                                    // revela o veredito já no clique
    try {
      const r = await sharedHand.votar(token, acao);
      setPlacar(r.votos);
    } catch {
      // voto falhou (rate limit): o veredito continua revelado, o placar fica como estava
    }
  };

  const comentar = async () => {
    const texto = comentario.trim();
    if (!texto || !dados) return;
    setEnviando(true);
    try {
      await sharedHand.comentar(token, texto);
      const d = await sharedHand.ler(token);
      setDados(d);
      setComentario("");
    } catch {
      // erro fica silencioso aqui; o texto do usuário permanece no campo
    } finally {
      setEnviando(false);
    }
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
  if (!dados) {
    return <div className="flex min-h-dvh items-center justify-center bg-background">
      <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>;
  }

  const marcado = dados.passo_marcado ?? null;
  const totalVotos = Object.values(placar).reduce((a, b) => a + b, 0);

  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-border bg-hud-surface/60">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
          <Link to="/"><img src={logoHorizontal} alt="GrindLab" className="h-7 w-auto" /></Link>
          <Link to="/login"
                className="rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/15">
            {t("sharedHand.analisarMinhas")}
          </Link>
        </div>
      </header>

      <main className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-6">
        {dados.pergunta && (
          <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
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

        {dados.passos.map((p, i) => {
          const eMarcado = marcado === i;
          const cartas = parseCartas(p.hero_cards);
          const board = parseBoard(p.board);
          const errou = p.label && p.label !== "correct" && p.label !== "gto_correct";
          const revela = !eMarcado || votou !== null;
          return (
            <div key={i} className={cn("rounded-xl border bg-hud-surface p-4",
                                       eMarcado ? "border-primary/40" : "border-border")}>
              <div className="mb-2 flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                <span className="font-bold text-foreground">{p.street}</span>
                <span>{p.position}{p.vs_position ? ` vs ${p.vs_position}` : ""}</span>
                {p.stack_bb != null && <span>{Number(p.stack_bb).toFixed(0)}bb</span>}
                {p.pot_bb != null && <span>pot {Number(p.pot_bb).toFixed(1)}bb</span>}
              </div>

              <div className="mb-3 flex items-center gap-3">
                <div className="flex gap-1">
                  {cartas.map((c, j) => <PlayingCard key={j} card={c} size="sm" />)}
                </div>
                {board.length > 0 && (
                  <>
                    <span className="text-muted-foreground/50">·</span>
                    <div className="flex gap-1">
                      {board.map((c, j) => <PlayingCard key={j} card={c} size="sm" />)}
                    </div>
                  </>
                )}
              </div>

              {eMarcado && votou === null ? (
                <div>
                  <p className="mb-2 text-[12px] font-medium text-foreground">
                    {t("sharedHand.oQueVoceFaz")}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {ACOES_VOTO.map((a) => (
                      <button key={a} type="button" onClick={() => votar(a)}
                              className="rounded-lg border border-border bg-background/50 px-3.5 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-foreground transition-colors hover:border-primary/50 hover:text-primary">
                        {t(`sharedHand.acao.${a}`)}
                      </button>
                    ))}
                  </div>
                </div>
              ) : revela && (
                <div className="space-y-1.5">
                  <p className="flex items-center gap-1.5 text-[12px]">
                    {errou
                      ? <XCircle className="size-3.5 shrink-0 text-amber-400" aria-hidden />
                      : <CheckCircle2 className="size-3.5 shrink-0 text-primary" aria-hidden />}
                    <span className="text-muted-foreground">{t("sharedHand.jogou")}</span>
                    <span className="font-mono font-bold uppercase text-foreground">{p.action_taken}</span>
                    {errou && p.best_action && (
                      <>
                        <span className="text-muted-foreground">·</span>
                        <span className="text-muted-foreground">{t("sharedHand.melhorEra")}</span>
                        <span className="font-mono font-bold uppercase text-primary">{p.best_action}</span>
                      </>
                    )}
                  </p>
                  {eMarcado && totalVotos > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {Object.entries(placar).sort((a, b) => b[1] - a[1]).map(([a, n]) => (
                        <span key={a}
                              className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
                                            a === votou ? "bg-primary/15 text-primary" : "bg-border/50 text-muted-foreground")}>
                          {a} {Math.round((n / totalVotos) * 100)}%
                        </span>
                      ))}
                      <span className="font-mono text-[10px] text-muted-foreground/60">
                        {t("sharedHand.votos", { n: totalVotos })}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        <section className="rounded-xl border border-border bg-hud-surface p-4">
          <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            <MessageSquare className="size-3" aria-hidden />
            {t("sharedHand.comentarios")} {dados.comentarios.length > 0 && `(${dados.comentarios.length})`}
          </p>
          {dados.comentarios.map((c) => (
            <div key={c.id} className="border-t border-border/60 py-2 first:border-t-0">
              <p className="font-mono text-[10px] font-bold text-primary">{c.autor}</p>
              <p className="mt-0.5 text-[13px] leading-snug text-foreground">{c.texto}</p>
            </div>
          ))}
          {user ? (
            <div className="mt-2 flex gap-1.5">
              <input
                value={comentario}
                onChange={(e) => setComentario(e.target.value.slice(0, 1000))}
                onKeyDown={(e) => { if (e.key === "Enter") comentar(); }}
                placeholder={t("sharedHand.comentarPlaceholder")}
                className="min-w-0 flex-1 rounded-lg border border-border bg-background/50 px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button type="button" onClick={comentar} disabled={enviando || !comentario.trim()}
                      className="rounded-lg bg-primary px-3.5 font-mono text-[11px] font-bold uppercase text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40">
                {t("sharedHand.enviar")}
              </button>
            </div>
          ) : (
            <p className="mt-2 text-[11.5px] text-muted-foreground">
              <Link to="/login" className="text-primary hover:underline">{t("sharedHand.entrarParaComentar")}</Link>
            </p>
          )}
        </section>

        <Link to="/"
              className="rounded-xl bg-primary px-4 py-3 text-center font-mono text-[12px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90">
          {t("sharedHand.cta")}
        </Link>
      </main>
    </div>
  );
}
