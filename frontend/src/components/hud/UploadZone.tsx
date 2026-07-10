import { useCallback, useRef, useState } from "react";
import { CheckCircle2, FileUp, Loader2, UploadCloud, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { tournaments } from "@/lib/api";

interface AnalyzeResult {
  tournament_id: string;
  tournament_db_id: number;
  hero: string;
  total_hands: number;
}

interface Props {
  onResult?: (result: AnalyzeResult) => void;
}

const SUPPORTED = ["PokerStars", "GGPoker", "ACR", "CoinPoker"];

export function UploadZone({ onResult }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback(
    async (file: File) => {
      setStatus("loading");
      setMessage("");
      try {
        const content = await file.text();
        const result = await tournaments.analyze(content, file.name);
        setStatus("ok");
        setMessage(
          `${result.hero} • ${result.total_hands} mãos importadas`
        );
        onResult?.({
          tournament_id: result.tournament_id,
          tournament_db_id: result.tournament_db_id,
          hero: result.hero,
          total_hands: result.total_hands,
        });
      } catch (err: unknown) {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Erro ao analisar arquivo");
      }
    },
    [onResult]
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

  const reset = () => {
    setStatus("idle");
    setMessage("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <section
      aria-label="Upload de log de torneio"
      className="relative group"
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <div className="absolute -inset-px rounded-xl bg-gradient-accent opacity-20 blur transition-opacity group-hover:opacity-40 pointer-events-none" />
      <div
        className={cn(
          "relative flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed bg-hud-surface p-10 text-center transition-all",
          isDragging ? "border-primary bg-primary/5 scale-[1.01]" : "border-border hover:border-primary/50",
          status === "ok" && "border-primary/50 bg-primary/5",
          status === "error" && "border-destructive/50 bg-destructive/5"
        )}
      >
        <div className="flex size-16 items-center justify-center rounded-full bg-background ring-1 ring-border">
          {status === "loading" && <Loader2 className="size-7 text-primary animate-spin" aria-hidden />}
          {status === "ok" && <CheckCircle2 className="size-7 text-primary" aria-hidden />}
          {status === "error" && <XCircle className="size-7 text-destructive" aria-hidden />}
          {status === "idle" && <UploadCloud className="size-7 text-primary" aria-hidden />}
        </div>

        <div className="space-y-1">
          <h3 className="text-base font-medium text-foreground">
            {status === "loading" && "Analisando torneio…"}
            {status === "ok" && "Torneio importado!"}
            {status === "error" && "Erro ao importar"}
            {status === "idle" && "Analisar nova sessão"}
          </h3>
          <p className="max-w-sm text-xs text-muted-foreground">
            {message ||
              "Arraste logs de torneios (.txt) ou clique para iniciar a varredura tática."}
          </p>
        </div>

        {status === "idle" || status === "error" ? (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={status === "loading"}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50"
          >
            <FileUp className="size-3.5" aria-hidden />
            Iniciar upload
          </button>
        ) : status === "ok" ? (
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-5 py-2 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary transition-all hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Importar outro
          </button>
        ) : null}

        <input
          ref={inputRef}
          type="file"
          accept=".txt,.log"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
          aria-label="Selecionar arquivo de log"
        />

        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          {SUPPORTED.map((s) => (
            <span
              key={s}
              className="rounded-sm bg-background px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground ring-1 ring-border"
            >
              {s}
            </span>
          ))}
        </div>

        <div className="mt-3 pt-3 border-t border-border/40 text-center">
          <p className="text-[11px] text-muted-foreground mb-2">
            Não tem hand history? Reconstrua manualmente uma mão (análise de vídeo, anotação, etc).
          </p>
          <a
            href="/hand-builder"
            className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-primary hover:underline"
          >
            Abrir Hand Builder →
          </a>
        </div>
      </div>
    </section>
  );
}
