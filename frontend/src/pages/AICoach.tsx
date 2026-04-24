import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send, Sparkles, User } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { coach, CoachContext } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Msg {
  id: number;
  role: "user" | "ai";
  content: string;
}

const SUGGESTIONS = [
  "Quais são meus 3 maiores leaks pré-flop?",
  "Como devo ajustar meu range de SB vs BTN?",
  "Resuma minha performance dos últimos 90 dias",
  "Quando devo 4-bet bluff em torneios?",
];

const AICoach = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [ctx, setCtx] = useState<CoachContext | null>(null);
  const [ctxLoading, setCtxLoading] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    coach
      .context()
      .then((data) => {
        setCtx(data);
        const leakNote =
          data.top_leaks.length > 0
            ? ` Detectei ${data.top_leaks.length} leak(s) prioritários: ${data.top_leaks
                .slice(0, 2)
                .map((l) => l.spot.replace(/_/g, " "))
                .join(", ")}.`
            : " Ainda sem dados de leaks — importe torneios para começar.";
        setMessages([
          {
            id: 1,
            role: "ai",
            content: `Olá${user?.username ? `, ${user.username}` : ""}! Analisei suas últimas ${
              data.hands_analyzed
            } mãos em ${data.tournaments_analyzed} torneios.${leakNote} Por onde quer começar?`,
          },
        ]);
      })
      .catch(() => {
        setMessages([
          {
            id: 1,
            role: "ai",
            content:
              "Olá! Importe torneios para que eu possa analisar seu jogo e oferecer coaching personalizado.",
          },
        ]);
      })
      .finally(() => setCtxLoading(false));
  }, [user?.username]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const userMsg: Msg = { id: Date.now(), role: "user", content: trimmed };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);

    try {
      const res = await coach.chat(trimmed);
      setMessages((m) => [...m, { id: Date.now() + 1, role: "ai", content: res.reply }]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      setMessages((m) => [
        ...m,
        { id: Date.now() + 1, role: "ai", content: `Erro ao processar: ${msg}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <HudLayout
      eyebrow="IA Coach • Alpha"
      title="Converse com seu coach tático"
      description="Pergunte sobre leaks, ranges, posições ou peça resumos de sessões. A IA usa seu histórico importado como contexto."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="lg:col-span-8 flex flex-col rounded-xl border border-border bg-hud-surface min-h-[60vh]">
          <header className="flex items-center justify-between border-b border-border px-5 py-3.5">
            <div className="flex items-center gap-2.5">
              <span className="flex size-8 items-center justify-center rounded-md bg-primary/15 text-primary">
                <Sparkles className="size-4" aria-hidden />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-foreground">Sessão de coaching</h2>
                <p className="font-mono text-[10px] text-muted-foreground">
                  Modelo tático v2.1 •{" "}
                  {ctxLoading
                    ? "carregando contexto…"
                    : ctx
                    ? `contexto: ${ctx.hands_analyzed.toLocaleString()} mãos`
                    : "sem dados"}
                </p>
              </div>
            </div>
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary ring-1 ring-primary/20">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" /> Online
            </span>
          </header>

          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.map((m) => (
              <article
                key={m.id}
                className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <span
                  className={`flex size-8 shrink-0 items-center justify-center rounded-md ${
                    m.role === "ai"
                      ? "bg-primary/15 text-primary"
                      : "bg-secondary text-foreground"
                  }`}
                  aria-hidden
                >
                  {m.role === "ai" ? <Bot className="size-4" /> : <User className="size-4" />}
                </span>
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                    m.role === "ai"
                      ? "bg-hud-elevated text-foreground border border-border"
                      : "bg-primary text-primary-foreground"
                  }`}
                >
                  {m.content}
                </div>
              </article>
            ))}
            {sending && (
              <article className="flex gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary" aria-hidden>
                  <Bot className="size-4" />
                </span>
                <div className="rounded-lg border border-border bg-hud-elevated px-4 py-3">
                  <Loader2 className="size-4 animate-spin text-primary" />
                </div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="border-t border-border p-3"
          >
            <div className="flex items-end gap-2 rounded-lg border border-border bg-background p-2 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/40">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                rows={1}
                placeholder="Pergunte ao coach…"
                className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none"
                aria-label="Mensagem"
                disabled={sending}
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="inline-flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground transition-opacity hover:bg-primary-glow disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Enviar"
              >
                {sending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Send className="size-4" aria-hidden />
                )}
              </button>
            </div>
          </form>
        </section>

        <aside className="lg:col-span-4 space-y-6">
          <section className="rounded-xl border border-border bg-hud-surface p-5">
            <h3 className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-3">
              Sugestões rápidas
            </h3>
            <div className="space-y-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={sending}
                  className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-left text-xs text-foreground transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
            <h3 className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-2">
              Contexto carregado
            </h3>
            {ctxLoading ? (
              <div className="flex items-center gap-2 py-2">
                <Loader2 className="size-3 animate-spin text-primary" />
                <span className="font-mono text-[10px] text-muted-foreground">Carregando…</span>
              </div>
            ) : (
              <ul className="space-y-2 text-xs text-foreground">
                <li className="flex items-center justify-between">
                  <span>Mãos</span>
                  <span className="font-mono tabular-nums text-primary">
                    {ctx ? ctx.hands_analyzed.toLocaleString() : "—"}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span>Torneios</span>
                  <span className="font-mono tabular-nums text-primary">
                    {ctx ? ctx.tournaments_analyzed : "—"}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span>Score médio</span>
                  <span
                    className={`font-mono tabular-nums ${
                      ctx?.avg_score != null
                        ? ctx.avg_score < 0.08
                          ? "text-primary"
                          : ctx.avg_score < 0.15
                          ? "text-warning"
                          : "text-destructive"
                        : "text-muted-foreground"
                    }`}
                  >
                    {ctx?.avg_score != null ? ctx.avg_score.toFixed(4) : "—"}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span>% Standard</span>
                  <span className="font-mono tabular-nums text-muted-foreground">
                    {ctx?.standard_pct != null
                      ? `${(ctx.standard_pct * 100).toFixed(1)}%`
                      : "—"}
                  </span>
                </li>
              </ul>
            )}
            {ctx && ctx.top_leaks.length > 0 && (
              <div className="mt-3 pt-3 border-t border-border/60">
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-2">
                  Top leaks
                </p>
                <ul className="space-y-1">
                  {ctx.top_leaks.slice(0, 3).map((l) => (
                    <li
                      key={l.spot}
                      className="text-[10px] text-muted-foreground flex items-center justify-between gap-2"
                    >
                      <span className="truncate">{l.spot.replace(/_/g, " ")}</span>
                      <span
                        className={`font-mono tabular-nums shrink-0 ${
                          l.avg_score >= 0.36
                            ? "text-destructive"
                            : l.avg_score >= 0.2
                            ? "text-warning"
                            : "text-primary"
                        }`}
                      >
                        {l.avg_score.toFixed(3)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </aside>
      </div>
    </HudLayout>
  );
};

export default AICoach;
