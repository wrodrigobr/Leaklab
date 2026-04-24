import { useCallback, useRef, useState } from "react";
import { FileUp, Loader2, UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

const SUPPORTED = ["PokerStars", "GGPoker", "ACR", "Winamax", "888"];

export function UploadZone() {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length) setFiles(dropped);
  }, []);

  const handleFiles = (selected: FileList | null) => {
    if (selected?.length) setFiles(Array.from(selected));
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
          isDragging ? "border-primary bg-primary/5 scale-[1.01]" : "border-border hover:border-primary/50"
        )}
      >
        <div className="flex size-16 items-center justify-center rounded-full bg-background ring-1 ring-border">
          {files.length ? (
            <Loader2 className="size-7 text-primary animate-spin" aria-hidden />
          ) : (
            <UploadCloud className="size-7 text-primary" aria-hidden />
          )}
        </div>

        <div className="space-y-1">
          <h3 className="text-base font-medium text-foreground">
            {files.length ? `Processando ${files.length} arquivo(s)…` : "Analisar nova sessão"}
          </h3>
          <p className="max-w-sm text-xs text-muted-foreground">
            Arraste logs de torneios (.txt, .zip) ou clique para iniciar a varredura tática.
          </p>
        </div>

        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <FileUp className="size-3.5" aria-hidden />
          Iniciar upload
        </button>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".txt,.zip,.log"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
          aria-label="Selecionar arquivos de log"
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
      </div>
    </section>
  );
}
