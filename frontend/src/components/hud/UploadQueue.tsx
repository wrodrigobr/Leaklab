import { useReducer, useEffect, useRef, useCallback } from "react";
import { CheckCircle2, AlertTriangle, Clock, Loader2, X, UploadCloud, Info } from "lucide-react";
import { tournaments, metrics } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

type QueueStatus = "queued" | "processing" | "done" | "error";

interface QueueItem {
  id: string;
  name: string;
  status: QueueStatus;
  error?: string;
  note?: string;   // mensagem positiva (ex.: summary complementado) — não é erro
}

type Action =
  | { type: "ADD"; items: QueueItem[] }
  | { type: "SET_STATUS"; id: string; status: QueueStatus; error?: string; note?: string }
  | { type: "DISMISS"; id: string }
  | { type: "CLEAR_DONE" };

function reducer(state: QueueItem[], action: Action): QueueItem[] {
  switch (action.type) {
    case "ADD":       return [...state, ...action.items];
    case "SET_STATUS": return state.map((i) => i.id === action.id ? { ...i, status: action.status, error: action.error, note: action.note } : i);
    case "DISMISS":   return state.filter((i) => i.id !== action.id);
    case "CLEAR_DONE": return state.filter((i) => i.status !== "done");
    default:          return state;
  }
}

// ── Status UI ─────────────────────────────────────────────────────────────────

const STATUS_ICON: Record<QueueStatus, React.ReactNode> = {
  queued:     <Clock className="size-3.5 text-muted-foreground" />,
  processing: <Loader2 className="size-3.5 text-amber-400 animate-spin" />,
  done:       <CheckCircle2 className="size-3.5 text-primary" />,
  error:      <AlertTriangle className="size-3.5 text-destructive" />,
};

const STATUS_LABEL: Record<QueueStatus, string> = {
  queued:     "Em fila",
  processing: "Processando…",
  done:       "Torneio enviado ✓",
  error:      "Erro",
};

const STATUS_COLOR: Record<QueueStatus, string> = {
  queued:     "text-muted-foreground",
  processing: "text-amber-400",
  done:       "text-primary",
  error:      "text-destructive",
};

// ── Queue panel ────────────────────────────────────────────────────────────────

function QueuePanel({
  items,
  onDismiss,
  onClearDone,
}: {
  items: QueueItem[];
  onDismiss: (id: string) => void;
  onClearDone: () => void;
}) {
  const pending = items.filter((i) => i.status === "queued" || i.status === "processing").length;
  const anyDone = items.some((i) => i.status === "done");
  const anyError = items.some((i) => i.status === "error");
  // Cabeçalho coerente com o resultado: não dizer "concluída" quando tudo falhou (a msg não condiz).
  const headerLabel = pending > 0
    ? `Importando ${items.length} arquivo${items.length !== 1 ? "s" : ""}`
    : anyDone
      ? (anyError ? "Concluído com avisos" : "Importação concluída")
      : "Não foi possível importar";

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-xl border border-border bg-background shadow-2xl">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2">
          <UploadCloud className="size-3.5 text-primary" />
          <span className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">
            {headerLabel}
          </span>
        </div>
        {pending === 0 && (
          <button
            onClick={onClearDone}
            className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          >
            Fechar
          </button>
        )}
      </div>

      <ul className="max-h-64 overflow-y-auto divide-y divide-border">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
            {STATUS_ICON[item.status]}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground truncate font-medium leading-tight">{item.name}</p>
              <p className={cn("font-mono text-[10px] mt-0.5", STATUS_COLOR[item.status])}>
                {item.note ?? item.error ?? STATUS_LABEL[item.status]}
              </p>
            </div>
            {(item.status === "done" || item.status === "error") && (
              <button
                onClick={() => onDismiss(item.id)}
                className="text-muted-foreground hover:text-foreground shrink-0 transition-colors"
                aria-label="Remover"
              >
                <X className="size-3" />
              </button>
            )}
          </li>
        ))}
      </ul>

      {/* Aviso pós-import: o solver GTO processa as mãos em segundo plano e pode demorar. Só quando
          houve import de MÃOS (item done sem note) — summary complementado não gera análise GTO. */}
      {pending === 0 && items.some((i) => i.status === "done" && !i.note) && (
        <div className="flex items-start gap-2 border-t border-border bg-primary/[0.05] px-4 py-2.5">
          <Info className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
          <p className="text-[11px] leading-snug text-muted-foreground">
            As mãos já estão no seu histórico. A <span className="text-foreground">análise GTO</span> roda
            em segundo plano e pode levar alguns minutos num torneio grande. Pode fechar, os torneios
            mostram o selo <span className="font-mono text-primary">Analisando</span> até concluir.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useUploadQueue(onAllDone?: () => void) {
  const [queue, dispatch] = useReducer(reducer, []);
  const fileMap    = useRef<Map<string, File>>(new Map());
  const processing = useRef(false);
  const cbRef      = useRef(onAllDone);
  cbRef.current = onAllDone;

  const enqueue = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files);
    if (arr.length === 0) return;

    const items: QueueItem[] = arr.map((f, i) => {
      const id = `${Date.now()}-${i}-${f.name}`;
      fileMap.current.set(id, f);
      return { id, name: f.name, status: "queued" as QueueStatus };
    });

    dispatch({ type: "ADD", items });
  }, []);

  const dismiss   = useCallback((id: string) => { fileMap.current.delete(id); dispatch({ type: "DISMISS", id }); }, []);
  const clearDone = useCallback(() => { queue.forEach((i) => { if (i.status === "done") fileMap.current.delete(i.id); }); dispatch({ type: "CLEAR_DONE" }); }, [queue]);

  useEffect(() => {
    const next = queue.find((i) => i.status === "queued");
    if (!next || processing.current) return;

    processing.current = true;
    dispatch({ type: "SET_STATUS", id: next.id, status: "processing" });

    const file = fileMap.current.get(next.id);

    (async () => {
      try {
        if (!file) throw new Error("Arquivo não encontrado na fila");
        const content = await file.text();
        const r = await tournaments.analyze(content, file.name);
        if (r?.kind === "summary") {
          // Era um Tournament Summary, não hand history: dados do torneio complementados.
          const note = r.field_size != null
            ? `Dados complementados: ${r.field_size} jogadores ✓`
            : "Dados do torneio complementados ✓";
          dispatch({ type: "SET_STATUS", id: next.id, status: "done", note });
        } else {
          dispatch({ type: "SET_STATUS", id: next.id, status: "done" });
          metrics.addXp("tournament_imported").catch(() => null);
        }
        window.dispatchEvent(new CustomEvent("leaklab:tournament-imported"));
      } catch (e: unknown) {
        const raw = e instanceof Error ? e.message : "";
        // Nunca mostra "HTTP 404" cru: usa a msg real do backend, senão um genérico legível.
        const msg = raw && !/^HTTP \d+$/.test(raw)
          ? raw
          : `Não foi possível processar (${raw || "erro"}). Verifique se o servidor está atualizado.`;
        dispatch({ type: "SET_STATUS", id: next.id, status: "error", error: msg });
      } finally {
        processing.current = false;
      }
    })();
  }, [queue]);

  useEffect(() => {
    if (queue.length === 0) return;
    const allSettled = queue.every((i) => i.status === "done" || i.status === "error");
    const anyDone    = queue.some((i) => i.status === "done");
    if (allSettled && anyDone) cbRef.current?.();
  }, [queue]);

  const panel = queue.length > 0 ? (
    <QueuePanel items={queue} onDismiss={dismiss} onClearDone={clearDone} />
  ) : null;

  return { enqueue, panel };
}
