import { useCallback, useRef, useState } from "react";
import { FileUp, Loader2, ShieldCheck, Target, Sparkles, UploadCloud, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { tournaments } from "@/lib/api";

const SUPPORTED = [".txt", ".log"];

const MODULES = [
  {
    code: "MÓDULO 01",
    title: "Detecção de leaks",
    description:
      "Identificação automática de padrões sub-ótimos no seu game tree, com severidade e perda de EV calculadas mão a mão.",
    icon: Target,
  },
  {
    code: "MÓDULO 02",
    title: "Bankroll Guard",
    description:
      "Tracking de variância e gráfico de evolução do bankroll torneio a torneio, para decisões de stake com confiança.",
    icon: ShieldCheck,
  },
  {
    code: "MÓDULO 03",
    title: "Coach Neural",
    description:
      "Análise conversacional da IA com seus dados reais: ranges, ICM, leaks e plano de estudo personalizado.",
    icon: Sparkles,
  },
];

interface Props {
  onComplete?: () => void;
}

export function EmptyDashboard({ onComplete }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback(
    async (file: File) => {
      setStatus("loading");
      setErrorMsg("");
      try {
        const content = await file.text();
        await tournaments.analyze(content);
        onComplete?.();
      } catch (err: unknown) {
        setStatus("error");
        const msg = err instanceof Error ? err.message : "Erro ao analisar arquivo";
        setErrorMsg(msg.includes("já foi importado") ? msg : msg);
      }
    },
    [onComplete]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  const handleFiles = (selected: FileList | null) => {
    if (selected?.[0]) processFile(selected[0]);
  };

  return (
    <div className="space-y-16">
      <section className="relative">
        <div className="absolute -top-7 left-0 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          Phase 01 // Data acquisition
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={cn(
            "bg-hud-surface border border-border p-1 transition-colors rounded-xl",
            isDragging && "border-primary"
          )}
        >
          <div
            className={cn(
              "border border-dashed border-border rounded-lg py-20 px-6 text-center transition-colors",
              isDragging && "border-primary/40 bg-primary/5",
              status === "error" && "border-destructive/40 bg-destructive/5"
            )}
          >
            <div className="mb-8 flex justify-center">
              <div className="size-16 rounded-full border border-border flex items-center justify-center bg-background">
                <div className="size-8 bg-primary/10 rounded-sm flex items-center justify-center">
                  {status === "loading" ? (
                    <Loader2 className="size-4 text-primary animate-spin" aria-hidden />
                  ) : status === "error" ? (
                    <XCircle className="size-4 text-destructive" aria-hidden />
                  ) : (
                    <UploadCloud className="size-4 text-primary" aria-hidden />
                  )}
                </div>
              </div>
            </div>

            <h1 className="text-3xl md:text-4xl font-medium tracking-tight text-foreground mb-3">
              {status === "loading"
                ? "Analisando torneio…"
                : status === "error"
                ? "Erro ao importar"
                : "Inicialize sua base tática"}
            </h1>
            <p className="text-muted-foreground max-w-md mx-auto mb-10 text-sm leading-relaxed">
              {status === "error"
                ? errorMsg
                : status === "loading"
                ? "O HUD será populado assim que a varredura terminar."
                : "Envie seu arquivo de hand history (PokerStars .txt) para calibrar o HUD e expor os leaks da sua mesa."}
            </p>

            {status !== "loading" && (
              <button
                type="button"
                onClick={() => { setStatus("idle"); inputRef.current?.click(); }}
                className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-8 py-4 font-mono text-xs font-bold uppercase tracking-widest-2 transition-colors hover:bg-primary-glow rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <FileUp className="size-3.5" aria-hidden />
                {status === "error" ? "Tentar novamente" : "Importar Hand History"}
              </button>
            )}

            <input
              ref={inputRef}
              type="file"
              accept=".txt,.log"
              className="sr-only"
              onChange={(e) => handleFiles(e.target.files)}
              aria-label="Selecionar arquivo de hand history"
            />

            <div className="mt-8 flex flex-wrap justify-center items-center gap-3 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
              {SUPPORTED.map((ext, i) => (
                <span key={ext} className="flex items-center gap-3">
                  {i > 0 && <span className="h-3 w-px bg-border" aria-hidden />}
                  {ext}
                </span>
              ))}
              <span className="h-3 w-px bg-border" aria-hidden />
              <span>PokerStars</span>
              <span className="h-3 w-px bg-border" aria-hidden />
              <span>AES-256</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-6 flex items-baseline justify-between">
          <h2 className="text-sm font-bold uppercase tracking-widest-2 text-foreground">
            O que será desbloqueado
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            03 módulos // aguardando dados
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {MODULES.map((m) => {
            const Icon = m.icon;
            return (
              <article
                key={m.code}
                className="tactical-corners relative bg-hud-surface border border-border p-6 transition-transform hover:-translate-y-1 rounded-lg"
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="font-mono text-[10px] tracking-widest-2 text-primary uppercase">
                    {m.code}
                  </span>
                  <Icon className="size-4 text-primary/60" aria-hidden />
                </div>
                <h3 className="text-lg font-medium text-foreground mb-2">{m.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed mb-6">{m.description}</p>
                <div className="flex items-center gap-3">
                  <div className="h-1 flex-1 bg-border overflow-hidden rounded-full">
                    <div className="h-full w-0 bg-primary" />
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground">0%</span>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
