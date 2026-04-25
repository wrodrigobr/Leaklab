import { useState } from "react";
import { Brain, ChevronDown, Loader2, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { tournaments } from "@/lib/api";

interface Props {
  tournamentName: string;
  tournamentDbId: number;
  existingSummary?: string | null;
}

export function TournamentAiReport({ tournamentName, tournamentDbId, existingSummary }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(existingSummary ?? null);
  const [error, setError] = useState("");

  const requestAnalysis = async () => {
    setOpen(true);
    if (summary) return;
    setLoading(true);
    setError("");
    try {
      const res = await tournaments.summary(tournamentDbId);
      setSummary(res.summary);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao gerar análise");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={requestAnalysis}
        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary shadow-[0_0_24px_-6px_hsl(var(--primary)/0.5)] transition-all hover:bg-primary/15 hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Sparkles className="size-3.5" aria-hidden />
        Análise IA do torneio
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Análise IA do torneio"
          className="fixed inset-0 z-50 flex items-stretch justify-end bg-background/80 backdrop-blur-sm animate-fade-in"
          onClick={() => setOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="flex h-full w-full max-w-2xl flex-col border-l border-border bg-hud-surface shadow-2xl"
          >
            <header className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="relative flex size-9 items-center justify-center rounded-md bg-primary/10 ring-1 ring-primary/30">
                  <Brain className="size-4 text-primary" aria-hidden />
                </span>
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                    AI Coach Report
                  </div>
                  <div className="text-sm font-semibold text-foreground">{tournamentName}</div>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Fechar"
              >
                <X className="size-4" aria-hidden />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <LoadingState />
              ) : error ? (
                <ErrorState message={error} />
              ) : summary ? (
                <SummaryContent text={summary} />
              ) : null}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function LoadingState() {
  const stages = [
    "Carregando decisões do torneio…",
    "Calculando padrões de leak…",
    "Avaliando contexto ICM e ranges…",
    "Gerando análise personalizada…",
  ];
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-8 py-16 text-center">
      <div className="relative">
        <Loader2 className="size-10 animate-spin text-primary" aria-hidden />
        <Sparkles className="absolute -right-2 -top-2 size-4 text-primary animate-pulse" aria-hidden />
      </div>
      <div className="space-y-2">
        <div className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
          IA processando
        </div>
        <h3 className="text-base font-semibold text-foreground">Analisando torneio completo</h3>
      </div>
      <ul className="space-y-1.5 text-left">
        {stages.map((s, i) => (
          <li
            key={i}
            className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground"
          >
            <span className="size-1 rounded-full bg-primary animate-pulse" aria-hidden />
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-8 py-16 text-center">
      <p className="text-sm text-destructive">{message}</p>
      <p className="text-xs text-muted-foreground">
        Verifique se a chave de API está configurada e tente novamente.
      </p>
    </div>
  );
}

function SummaryContent({ text }: { text: string }) {
  const hasMarkdown = /^#{1,3} /m.test(text);

  if (!hasMarkdown) {
    // Prosa pura — divide por quebras de parágrafo e renderiza direto
    const paragraphs = text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
    return (
      <div className="p-5 space-y-4">
        {paragraphs.map((p, i) => (
          <p key={i} className="text-sm leading-relaxed text-foreground">{p}</p>
        ))}
        <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground text-center pt-2">
          LeakLabs AI Coach • Powered by Claude Haiku
        </p>
      </div>
    );
  }

  // Markdown estruturado — usa seções colapsáveis
  const sections = text
    .split(/\n(?=#{1,3} |\*\*[A-Z])/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div className="space-y-3 p-5">
      {sections.map((section, i) => (
        <SummarySection key={i} text={section} />
      ))}
      <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground text-center pt-2">
        LeakLabs AI Coach • Powered by Claude Haiku
      </p>
    </div>
  );
}

function SummarySection({ text }: { text: string }) {
  const [open, setOpen] = useState(true);
  const lines = text.split("\n");
  const firstLine = lines[0];
  const isHeading = /^#{1,3} /.test(firstLine);
  const title = isHeading ? firstLine.replace(/^#{1,3} /, "") : firstLine;
  const body = lines.slice(isHeading ? 1 : 0).join("\n").trim();

  const toneClasses = firstLine.toLowerCase().includes("erro") || firstLine.toLowerCase().includes("leak") || firstLine.toLowerCase().includes("falha")
    ? { border: "border-destructive/30", bg: "bg-destructive/5", text: "text-destructive" }
    : firstLine.toLowerCase().includes("ponto forte") || firstLine.toLowerCase().includes("acert") || firstLine.toLowerCase().includes("solid")
    ? { border: "border-primary/30", bg: "bg-primary/5", text: "text-primary" }
    : { border: "border-border", bg: "bg-hud-elevated/40", text: "text-muted-foreground" };

  if (!body && !isHeading) {
    return (
      <div className="rounded-lg border border-border bg-hud-elevated/30 px-4 py-3">
        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">{text}</p>
      </div>
    );
  }

  return (
    <section className={cn("overflow-hidden rounded-xl border", toneClasses.border, toneClasses.bg)}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={open}
      >
        <h3 className={cn("font-mono text-[11px] font-bold uppercase tracking-widest-2", toneClasses.text)}>
          {title}
        </h3>
        <ChevronDown
          className={cn("size-4 text-muted-foreground transition-transform shrink-0", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open && body && (
        <div className="border-t border-border/40 px-4 py-3.5">
          <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">{body}</p>
        </div>
      )}
    </section>
  );
}
