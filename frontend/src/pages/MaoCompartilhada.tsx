import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Eye, MessageSquare, Play, XCircle } from "lucide-react";

import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { sharedHand, type SharedHandPayload, type SharedHandStep } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * A página PÚBLICA de uma mão compartilhada — a única tela do produto que sai dele.
 *
 * ── Reescrita de 30/08 (feedback do dono na primeira versão) ──────────────────────────────
 *
 * A v1 mostrava todos os passos de uma vez e perguntava "o que você faz aqui?" sem história —
 * e pior: com o BOARD INTEIRO visível num passo de preflop, porque `decisions.board` guarda o
 * board FINAL da mão. Spoiler e confusão na mesma tela.
 *
 * O desenho novo é o que o dono propôs — dois modos:
 * - **Jogar a mão**: passo a passo; o board é FATIADO pela street do passo (preflop 0, flop 3,
 *   turn 4, river 5 — a mesma lição do hash do solver), o contexto (pote, aposta enfrentada)
 *   aparece, e o veredito de CADA passo só se revela depois da escolha. No passo marcado, a
 *   escolha vira VOTO e o placar da comunidade aparece junto.
 * - **Ver a mão**: leitura direta, tudo revelado, para quem só quer conferir.
 */

const CARTAS_POR_STREET: Record<string, number> = { preflop: 0, flop: 3, turn: 4, river: 5 };

function parseCartas(raw?: string | string[] | null): CardData[] {
  if (!raw) return [];
  const s = (Array.isArray(raw) ? raw.join("") : String(raw)).replace(/[[\]"',\s]/g, "");
  const out: CardData[] = [];
  for (let i = 0; i + 1 < s.length; i += 2) {
    out.push({ rank: s[i] as CardData["rank"], suit: s[i + 1].toLowerCase() as CardData["suit"] });
  }
  return out;
}

/** o board que EXISTE na street do passo — nunca o final da mão */
function boardDaStreet(step: SharedHandStep): CardData[] {
  const n = CARTAS_POR_STREET[(step.street || "").toLowerCase()] ?? 5;
  return parseCartas(step.board).slice(0, n);
}

function opcoesDoPasso(step: SharedHandStep): string[] {
  const enfrenta = Number(step.facing_bb || 0) > 0 || (step.street || "") === "preflop";
  return enfrenta ? ["fold", "call", "raise", "allin"] : ["check", "bet", "allin"];
}

function Contexto({ step, t }: { step: SharedHandStep; t: (k: string, o?: Record<string, unknown>) => string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
      <span className="font-bold text-foreground">{step.street}</span>
      <span>{step.position}{step.vs_position ? ` vs ${step.vs_position}` : ""}</span>
      {step.stack_bb != null && <span>{Number(step.stack_bb).toFixed(0)}bb</span>}
      {step.pot_bb != null && <span>{t("sharedHand.pote", { n: Number(step.pot_bb).toFixed(1) })}</span>}
      {Number(step.facing_bb || 0) > 0 && (
        <span className="text-amber-400">{t("sharedHand.enfrenta", { n: Number(step.facing_bb).toFixed(1) })}</span>
      )}
    </div>
  );
}

function Cartas({ step }: { step: SharedHandStep }) {
  const cartas = parseCartas(step.hero_cards);
  const board = boardDaStreet(step);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex gap-1">{cartas.map((c, j) => <PlayingCard key={j} card={c} size="sm" />)}</div>
      {board.length > 0 && (
        <>
          <span className="text-muted-foreground/50">·</span>
          <div className="flex gap-1">{board.map((c, j) => <PlayingCard key={j} card={c} size="sm" />)}</div>
        </>
      )}
    </div>
  );
}

function Veredito({ step, escolha, t }: {
  step: SharedHandStep; escolha?: string | null; t: (k: string, o?: Record<string, unknown>) => string;
}) {
  const errou = step.label && step.label !== "correct" && step.label !== "gto_correct";
  const melhor = (step.best_action || "").toLowerCase();
  const acertouVisita = escolha && melhor && escolha === melhor;
  return (
    <div className="space-y-1 text-[12.5px]">
      {escolha && (
        <p className="flex items-center gap-1.5">
          {acertouVisita
            ? <CheckCircle2 className="size-3.5 shrink-0 text-primary" aria-hidden />
            : <XCircle className="size-3.5 shrink-0 text-amber-400" aria-hidden />}
          <span className="text-muted-foreground">{t("sharedHand.vocEscolheu")}</span>
          <span className="font-mono font-bold uppercase text-foreground">{escolha}</span>
        </p>
      )}
      <p className="flex flex-wrap items-center gap-1.5">
        <span className="text-muted-foreground">{t("sharedHand.jogou")}</span>
        <span className="font-mono font-bold uppercase text-foreground">{step.action_taken}</span>
        {step.best_action && (
          <>
            <span className="text-muted-foreground">· {t("sharedHand.melhorEra")}</span>
            <span className={cn("font-mono font-bold uppercase", errou ? "text-primary" : "text-foreground")}>
              {step.best_action}
            </span>
          </>
        )}
      </p>
    </div>
  );
}

export default function MaoCompartilhada() {
  const { token = "" } = useParams();
  const { t } = useTranslation("common");
  const { user } = useAuth();
  const [dados, setDados] = useState<SharedHandPayload | null>(null);
  const [erro, setErro] = useState(false);
  const [modo, setModo] = useState<"escolha" | "jogar" | "ver">("escolha");
  const [passo, setPasso] = useState(0);
  const [escolhas, setEscolhas] = useState<Record<number, string>>({});
  const [placar, setPlacar] = useState<Record<string, number>>({});
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    sharedHand.ler(token)
      .then((d) => { setDados(d); setPlacar(d.votos || {}); })
      .catch(() => setErro(true));
  }, [token]);

  const marcado = dados?.passo_marcado ?? null;
  const totalVotos = useMemo(() => Object.values(placar).reduce((a, b) => a + b, 0), [placar]);

  const escolher = async (idx: number, acao: string) => {
    setEscolhas((e) => ({ ...e, [idx]: acao }));
    if (idx === marcado) {
      // só a decisão MARCADA vira voto da comunidade — é a pergunta do dono
      try {
        const r = await sharedHand.votar(token, acao);
        setPlacar(r.votos);
      } catch { /* rate limit: o veredito segue revelado, o placar fica como estava */ }
    }
  };

  const comentar = async () => {
    const texto = comentario.trim();
    if (!texto || !dados) return;
    setEnviando(true);
    try {
      await sharedHand.comentar(token, texto);
      setDados(await sharedHand.ler(token));
      setComentario("");
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

  const passos = dados.passos;
  const atual = passos[Math.min(passo, passos.length - 1)];
  const fim = modo === "jogar" && passo >= passos.length;

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

        {/* ── a escolha do visitante: jogar ou só ver ── */}
        {modo === "escolha" && (
          <div className="flex flex-col gap-2.5 rounded-xl border border-border bg-hud-surface p-5">
            <p className="text-[13px] text-muted-foreground">{t("sharedHand.comoQuer")}</p>
            <button type="button" onClick={() => { setModo("jogar"); setPasso(0); }}
                    className="flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 font-mono text-[12px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90">
              <Play className="size-4" aria-hidden /> {t("sharedHand.jogarMao")}
            </button>
            <button type="button" onClick={() => setModo("ver")}
                    className="flex items-center justify-center gap-2 rounded-lg border border-border px-4 py-3 font-mono text-[12px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary">
              <Eye className="size-4" aria-hidden /> {t("sharedHand.verMao")}
            </button>
          </div>
        )}

        {/* ── JOGAR: um passo por vez, board fatiado, veredito após a escolha ── */}
        {modo === "jogar" && !fim && atual && (
          <div className={cn("rounded-xl border bg-hud-surface p-4",
                             passo === marcado ? "border-primary/40" : "border-border")}>
            <div className="mb-1 flex items-center justify-between">
              <Contexto step={atual} t={t} />
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70">
                {passo + 1}/{passos.length}
              </span>
            </div>
            <div className="my-3"><Cartas step={atual} /></div>

            {!escolhas[passo] ? (
              <div>
                <p className="mb-2 text-[13px] font-medium text-foreground">{t("sharedHand.oQueVoceFaz")}</p>
                <div className="flex flex-wrap gap-1.5">
                  {opcoesDoPasso(atual).map((a) => (
                    <button key={a} type="button" onClick={() => escolher(passo, a)}
                            className="rounded-lg border border-border bg-background/50 px-3.5 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-foreground transition-colors hover:border-primary/50 hover:text-primary">
                      {t(`sharedHand.acao.${a}`)}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-2.5">
                <Veredito step={atual} escolha={escolhas[passo]} t={t} />
                {passo === marcado && totalVotos > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(placar).sort((a, b) => b[1] - a[1]).map(([a, n]) => (
                      <span key={a}
                            className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
                                          a === escolhas[passo] ? "bg-primary/15 text-primary" : "bg-border/50 text-muted-foreground")}>
                        {a} {Math.round((n / totalVotos) * 100)}%
                      </span>
                    ))}
                    <span className="font-mono text-[10px] text-muted-foreground/60">
                      {t("sharedHand.votos", { n: totalVotos })}
                    </span>
                  </div>
                )}
                <button type="button" onClick={() => setPasso((p) => p + 1)}
                        className="rounded-lg bg-primary px-3.5 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90">
                  {passo + 1 < passos.length ? t("sharedHand.proxima") : t("sharedHand.terminar")}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── fim do jogar: resumo comparando cada escolha com o best_action ── */}
        {fim && (
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-center">
            <p className="font-heading text-lg font-bold text-foreground">
              {t("sharedHand.resumo", {
                acertos: passos.filter((p, i) =>
                  (p.best_action || "").toLowerCase() === (escolhas[i] || "")).length,
                total: passos.length,
              })}
            </p>
            <button type="button" onClick={() => setModo("ver")}
                    className="mt-2 font-mono text-[11px] uppercase tracking-wider text-primary hover:underline">
              {t("sharedHand.reverTudo")}
            </button>
          </div>
        )}

        {/* ── VER: tudo revelado, sem quiz ── */}
        {modo === "ver" && passos.map((p, i) => (
          <div key={i} className={cn("rounded-xl border bg-hud-surface p-4",
                                     marcado === i ? "border-primary/40" : "border-border")}>
            <Contexto step={p} t={t} />
            <div className="my-3"><Cartas step={p} /></div>
            <Veredito step={p} t={t} />
          </div>
        ))}

        {modo !== "escolha" && (
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
        )}

        <Link to="/"
              className="rounded-xl bg-primary px-4 py-3 text-center font-mono text-[12px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90">
          {t("sharedHand.cta")}
        </Link>
      </main>
    </div>
  );
}
