import { useReducer, useEffect, useRef, useCallback, useState } from "react";
import { CheckCircle2, AlertTriangle, Clock, Loader2, X, UploadCloud, Target, ChevronDown, ChevronUp } from "lucide-react";
import { tournaments, metrics, SessionGoal } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

type QueueStatus = "queued" | "processing" | "done" | "error";

interface QueueItem {
  id: string;
  name: string;
  status: QueueStatus;
  error?: string;
}

type Action =
  | { type: "ADD"; items: QueueItem[] }
  | { type: "SET_STATUS"; id: string; status: QueueStatus; error?: string }
  | { type: "DISMISS"; id: string }
  | { type: "CLEAR_DONE" };

function reducer(state: QueueItem[], action: Action): QueueItem[] {
  switch (action.type) {
    case "ADD":       return [...state, ...action.items];
    case "SET_STATUS": return state.map((i) => i.id === action.id ? { ...i, status: action.status, error: action.error } : i);
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
  done:       "Analisado ✓",
  error:      "Erro",
};

const STATUS_COLOR: Record<QueueStatus, string> = {
  queued:     "text-muted-foreground",
  processing: "text-amber-400",
  done:       "text-primary",
  error:      "text-destructive",
};

// ── Session Goal Panel ────────────────────────────────────────────────────────

export function SessionGoalPanel({
  onGoalSaved,
}: {
  onGoalSaved?: (goal: SessionGoal) => void;
}) {
  const [open,       setOpen]       = useState(false);
  const [leakSpot,   setLeakSpot]   = useState("");
  const [targetPct,  setTargetPct]  = useState("");
  const [notes,      setNotes]      = useState("");
  const [saving,     setSaving]     = useState(false);
  const [saved,      setSaved]      = useState<SessionGoal | null>(null);

  const handleSave = async () => {
    setSaving(true);
    try {
      const goal = await metrics.createSessionGoal({
        goal_leak_spot:      leakSpot.trim() || undefined,
        target_standard_pct: targetPct ? parseFloat(targetPct) : undefined,
        notes:               notes.trim() || undefined,
      });
      const g = goal as SessionGoal;
      sessionStorage.setItem("ll_pending_goal", String(g.id));
      setSaved(g);
      setOpen(false);
      onGoalSaved?.(g);
    } catch {
      // silently ignore
    } finally {
      setSaving(false);
    }
  };

  const handleClear = () => {
    setSaved(null);
    setLeakSpot("");
    setTargetPct("");
    setNotes("");
    sessionStorage.removeItem("ll_pending_goal");
  };

  if (saved) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-primary/30 bg-primary/5">
        <Target className="size-3.5 text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-primary">Meta definida</p>
          <p className="text-xs text-muted-foreground truncate">
            {saved.goal_leak_spot || "Foco geral"}
            {saved.target_standard_pct != null && ` · ${saved.target_standard_pct}% standard`}
          </p>
        </div>
        <button
          onClick={handleClear}
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
          aria-label="Remover meta"
        >
          <X className="size-3" />
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-background/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <div className="flex items-center gap-2">
          <Target className="size-3.5 text-muted-foreground" />
          <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
            Definir meta da sessão
          </span>
        </div>
        {open
          ? <ChevronUp className="size-3 text-muted-foreground" />
          : <ChevronDown className="size-3 text-muted-foreground" />
        }
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-2 border-t border-border pt-2">
          <div>
            <label className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Spot de foco</label>
            <input
              type="text"
              value={leakSpot}
              onChange={(e) => setLeakSpot(e.target.value)}
              placeholder="ex: 3-bet OOP, C-bet flop seco…"
              className="mt-1 w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div>
            <label className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Meta de standard% (opcional)</label>
            <input
              type="number"
              value={targetPct}
              onChange={(e) => setTargetPct(e.target.value)}
              placeholder="ex: 65"
              min="0"
              max="100"
              className="mt-1 w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div>
            <label className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Anotação livre (opcional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="ex: Focar em não inflar o pote OOP com top pair fraco…"
              rows={2}
              className="mt-1 w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
          </div>
          <button
            onClick={handleSave}
            disabled={saving || (!leakSpot.trim() && !targetPct && !notes.trim())}
            className="w-full rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary-foreground disabled:opacity-40 transition-opacity"
          >
            {saving ? "Salvando…" : "Salvar meta"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Queue panel ────────────────────────────────────────────────────────────────

function QueuePanel({
  items,
  onDismiss,
  onClearDone,
  pendingGoalId,
}: {
  items: QueueItem[];
  onDismiss: (id: string) => void;
  onClearDone: () => void;
  pendingGoalId: number | null;
}) {
  const pending = items.filter((i) => i.status === "queued" || i.status === "processing").length;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-xl border border-border bg-background shadow-2xl">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2">
          <UploadCloud className="size-3.5 text-primary" />
          <span className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">
            {pending > 0 ? `Importando ${items.length} arquivo${items.length !== 1 ? "s" : ""}` : "Importação concluída"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {pendingGoalId && (
            <span title="Meta da sessão ativa" className="flex items-center gap-1 text-primary">
              <Target className="size-3" />
            </span>
          )}
          {pending === 0 && (
            <button
              onClick={onClearDone}
              className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
            >
              Fechar
            </button>
          )}
        </div>
      </div>

      <ul className="max-h-64 overflow-y-auto divide-y divide-border">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
            {STATUS_ICON[item.status]}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground truncate font-medium leading-tight">{item.name}</p>
              <p className={cn("font-mono text-[10px] mt-0.5", STATUS_COLOR[item.status])}>
                {item.error ?? STATUS_LABEL[item.status]}
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

  // Process one queued item at a time
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
        const result  = await tournaments.analyze(content);
        dispatch({ type: "SET_STATUS", id: next.id, status: "done" });
        metrics.addXp("tournament_imported").catch(() => null);
        // Link pending session goal to the new tournament
        const rawGoalId = sessionStorage.getItem("ll_pending_goal");
        if (rawGoalId && result.tournament_db_id) {
          const goalId = parseInt(rawGoalId, 10);
          metrics.linkSessionGoal(goalId, result.tournament_db_id).catch(() => null);
          sessionStorage.removeItem("ll_pending_goal");
        }
        window.dispatchEvent(new CustomEvent("leaklab:tournament-imported"));
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erro ao processar arquivo";
        dispatch({ type: "SET_STATUS", id: next.id, status: "error", error: msg });
      } finally {
        processing.current = false;
      }
    })();
  }, [queue]);

  // Notify parent when all items settle and at least one succeeded
  useEffect(() => {
    if (queue.length === 0) return;
    const allSettled = queue.every((i) => i.status === "done" || i.status === "error");
    const anyDone    = queue.some((i) => i.status === "done");
    if (allSettled && anyDone) cbRef.current?.();
  }, [queue]);

  const panel = queue.length > 0 ? (
    <QueuePanel
      items={queue}
      onDismiss={dismiss}
      onClearDone={clearDone}
      pendingGoalId={sessionStorage.getItem("ll_pending_goal") ? parseInt(sessionStorage.getItem("ll_pending_goal")!, 10) : null}
    />
  ) : null;

  return { enqueue, panel };
}
