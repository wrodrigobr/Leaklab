import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Send, Loader2, MessageSquare, ChevronDown, ChevronUp } from "lucide-react";
import { playerMessages, CoachMessage } from "@/lib/api";

export function CoachMessagesPanel({ coachUsername }: { coachUsername?: string }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const [open, setOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["player-coach-messages"],
    queryFn: playerMessages.list,
    refetchInterval: 15_000,
  });

  const sendMut = useMutation({
    mutationFn: (text: string) => playerMessages.send(text),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["player-coach-messages"] });
      qc.invalidateQueries({ queryKey: ["player-messages-unread"] });
    },
  });

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data?.messages, open]);

  // Clear header badge immediately when panel is opened and messages are loaded
  useEffect(() => {
    if (open && data?.messages?.length) {
      qc.invalidateQueries({ queryKey: ["player-messages-unread"] });
    }
  }, [open, data?.messages?.length, qc]);

  const handleSend = () => {
    const text = body.trim();
    if (!text || sendMut.isPending) return;
    sendMut.mutate(text);
  };

  const messages: CoachMessage[] = data?.messages ?? [];
  const unreadCount = messages.filter((m) => m.sender_role === "coach" && !m.read_at).length;

  return (
    <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 border-b border-border"
      >
        <div className="flex items-center gap-2">
          <GraduationCap className="size-3.5 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-foreground">
            {coachUsername ? `Coach ${coachUsername}` : "Mensagens do Coach"}
          </span>
          {unreadCount > 0 && (
            <span className="flex items-center justify-center size-4 rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground">
              {unreadCount}
            </span>
          )}
        </div>
        {open ? <ChevronUp className="size-3.5 text-muted-foreground" /> : <ChevronDown className="size-3.5 text-muted-foreground" />}
      </button>

      {open && (
        <>
          <div className="h-64 overflow-y-auto px-4 py-3 space-y-3">
            {isLoading && (
              <p className="text-xs text-muted-foreground text-center py-8 animate-pulse">Carregando…</p>
            )}
            {!isLoading && messages.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <MessageSquare className="size-5 text-muted-foreground/40" />
                <p className="text-xs text-muted-foreground">
                  Nenhuma mensagem ainda.<br />Envie uma dúvida ao seu coach.
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.sender_role === "student" ? "justify-end" : "justify-start"}`}
              >
                <div className={`max-w-[78%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                  m.sender_role === "student"
                    ? "bg-primary text-primary-foreground"
                    : m.read_at == null
                      ? "bg-primary/5 border border-primary/30 text-foreground"
                      : "bg-background border border-border text-foreground"
                }`}>
                  {m.sender_role === "coach" && (
                    <p className="font-mono text-[9px] font-bold uppercase tracking-wider text-primary mb-1">
                      {coachUsername ?? "Coach"}
                    </p>
                  )}
                  {m.body}
                  <p className={`font-mono text-[9px] mt-1 ${
                    m.sender_role === "student" ? "text-primary-foreground/60" : "text-muted-foreground"
                  }`}>
                    {new Date(m.created_at).toLocaleString("pt-BR", {
                      day: "2-digit", month: "2-digit",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-border px-3 py-2.5 flex gap-2">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="Pergunta ou dúvida… (Enter para enviar)"
              rows={2}
              className="flex-1 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
            <button
              onClick={handleSend}
              disabled={!body.trim() || sendMut.isPending}
              className="self-end rounded-md bg-primary px-3 py-1.5 text-primary-foreground disabled:opacity-40 transition-opacity"
            >
              {sendMut.isPending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
