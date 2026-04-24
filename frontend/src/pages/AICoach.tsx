import { useState } from "react";
import { Bot, Send, Sparkles, User } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";

interface Msg {
  id: number;
  role: "user" | "ai";
  content: string;
}

const SUGGESTIONS = [
  "Quais são meus 3 maiores leaks pré-flop?",
  "Como devo ajustar meu range de SB vs BTN?",
  "Resuma minha sessão de ontem",
  "Quando devo 4-bet bluff em torneios?",
];

const SEED: Msg[] = [
  {
    id: 1,
    role: "ai",
    content:
      "Olá! Analisei suas últimas 1.428 mãos. Detectei 2 leaks críticos e 4 ajustes sugeridos. Por onde quer começar?",
  },
];

const AICoach = () => {
  const [messages, setMessages] = useState<Msg[]>(SEED);
  const [input, setInput] = useState("");

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const id = messages.length + 1;
    setMessages((m) => [
      ...m,
      { id, role: "user", content: trimmed },
      {
        id: id + 1,
        role: "ai",
        content:
          "Conecte o Lovable Cloud e ative a IA para receber análises personalizadas em tempo real baseadas no seu histórico de mãos.",
      },
    ]);
    setInput("");
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
                <p className="font-mono text-[10px] text-muted-foreground">Modelo tático v2.1 • contexto: 1.428 mãos</p>
              </div>
            </div>
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary ring-1 ring-primary/20">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" /> Online
            </span>
          </header>

          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.map((m) => (
              <article key={m.id} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <span
                  className={`flex size-8 shrink-0 items-center justify-center rounded-md ${
                    m.role === "ai" ? "bg-primary/15 text-primary" : "bg-secondary text-foreground"
                  }`}
                  aria-hidden
                >
                  {m.role === "ai" ? <Bot className="size-4" /> : <User className="size-4" />}
                </span>
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
                    m.role === "ai"
                      ? "bg-hud-elevated text-foreground border border-border"
                      : "bg-primary text-primary-foreground"
                  }`}
                >
                  {m.content}
                </div>
              </article>
            ))}
          </div>

          {/* Input */}
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
              />
              <button
                type="submit"
                disabled={!input.trim()}
                className="inline-flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground transition-opacity hover:bg-primary-glow disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Enviar"
              >
                <Send className="size-4" aria-hidden />
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
                  className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-left text-xs text-foreground transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
            <ul className="space-y-2 text-xs text-foreground">
              <li className="flex items-center justify-between"><span>Mãos</span><span className="font-mono tabular-nums text-primary">1.428</span></li>
              <li className="flex items-center justify-between"><span>Torneios</span><span className="font-mono tabular-nums text-primary">142</span></li>
              <li className="flex items-center justify-between"><span>Período</span><span className="font-mono text-muted-foreground">90 dias</span></li>
              <li className="flex items-center justify-between"><span>Stake médio</span><span className="font-mono tabular-nums text-muted-foreground">$52</span></li>
            </ul>
          </section>
        </aside>
      </div>
    </HudLayout>
  );
};

export default AICoach;
