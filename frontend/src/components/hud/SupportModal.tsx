import { useState, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { X, MessageSquarePlus, CheckCircle2, Inbox, PenLine, Loader2, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { support, MyTicket } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  onClose: () => void;
  initialTab?: "new" | "inbox";
}

type Category = "bug" | "question" | "suggestion" | "billing" | "other";

const CATEGORY_LABEL: Record<string, string> = {
  bug: "Bug", question: "Dúvida", suggestion: "Sugestão", billing: "Cobrança", other: "Outro",
};

function TicketCard({ ticket, onDelete }: { ticket: MyTicket; onDelete: () => void }) {
  const { t } = useTranslation("common");
  const [open, setOpen] = useState(!!ticket.admin_reply);

  return (
    <div className={cn(
      "rounded-lg border p-4 space-y-2 transition-colors",
      ticket.admin_reply ? "border-primary/20 bg-primary/5" : "border-border bg-background/40"
    )}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-[9px] font-bold uppercase tracking-wider bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
          {CATEGORY_LABEL[ticket.category] ?? ticket.category}
        </span>
        {ticket.admin_reply ? (
          <span className="font-mono text-[9px] font-bold uppercase tracking-wider bg-primary/10 text-primary px-2 py-0.5 rounded-full">
            Respondido
          </span>
        ) : (
          <span className="font-mono text-[9px] font-bold uppercase tracking-wider bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
            Aguardando
          </span>
        )}
        <span className="font-mono text-[10px] text-muted-foreground ml-auto">
          {new Date(ticket.created_at).toLocaleDateString("pt-BR")}
        </span>
        <button onClick={onDelete} title={t("supportModal.delete")} aria-label={t("supportModal.delete")}
          className="text-muted-foreground/50 transition-colors hover:text-destructive">
          <Trash2 className="size-3.5" aria-hidden />
        </button>
      </div>

      {ticket.subject && (
        <p className="text-sm font-semibold text-foreground">{ticket.subject}</p>
      )}

      {open ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{ticket.message}</p>
          {ticket.admin_reply && (
            <div className="rounded-md border border-primary/20 bg-background px-3 py-2.5 space-y-1">
              <p className="font-mono text-[9px] font-bold uppercase tracking-wider text-primary">
                Resposta da equipe · {ticket.replied_at ? new Date(ticket.replied_at).toLocaleDateString("pt-BR") : ""}
              </p>
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{ticket.admin_reply}</p>
            </div>
          )}
          <button onClick={() => setOpen(false)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors">
            Recolher
          </button>
        </div>
      ) : (
        <button onClick={() => setOpen(true)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors">
          {ticket.admin_reply ? "Ver mensagem e resposta →" : "Ver mensagem →"}
        </button>
      )}
    </div>
  );
}

export function SupportModal({ onClose, initialTab = "new" }: Props) {
  const { t } = useTranslation("common");
  const { user } = useAuth();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"new" | "inbox">(initialTab);
  const [category, setCategory]   = useState<Category>("question");
  const [subject, setSubject]     = useState("");
  const [message, setMessage]     = useState("");
  const [formStatus, setFormStatus] = useState<"idle" | "sending" | "success" | "error">("idle");

  const { data: ticketsData, isLoading: ticketsLoading } = useQuery({
    queryKey: ["my-support-tickets"],
    queryFn:  support.myTickets,
    staleTime: 30_000,
  });
  const tickets = ticketsData?.tickets ?? [];
  const repliedCount = tickets.filter(t => t.admin_reply).length;

  const delMut = useMutation({
    mutationFn: (id: number) => support.deleteTicket(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-support-tickets"] }),
  });
  const clearMut = useMutation({
    mutationFn: () => support.clearTickets(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-support-tickets"] }),
  });

  // Mark all replied tickets as read as soon as inbox tab is visible
  useEffect(() => {
    if (activeTab !== "inbox") return;
    support.markRead().then(() => {
      qc.invalidateQueries({ queryKey: ["my-support-unread"] });
    }).catch(() => null);
  }, [activeTab]);

  const categories: { value: Category; label: string }[] = [
    { value: "bug",        label: t("supportModal.categories.bug") },
    { value: "question",   label: t("supportModal.categories.question") },
    { value: "suggestion", label: t("supportModal.categories.suggestion") },
    { value: "billing",    label: t("supportModal.categories.billing") },
    { value: "other",      label: t("supportModal.categories.other") },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;
    setFormStatus("sending");
    try {
      await support.contact({ category, subject: subject.trim(), message: message.trim() });
      setFormStatus("success");
      qc.invalidateQueries({ queryKey: ["my-support-tickets"] });
      qc.invalidateQueries({ queryKey: ["my-support-unread"] });
    } catch {
      setFormStatus("error");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-hud-surface shadow-elevated flex flex-col max-h-[90vh]">

        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <MessageSquarePlus className="size-4 text-primary" />
            <span className="font-mono text-[11px] font-bold uppercase tracking-widest text-foreground">
              {t("supportModal.title")}
            </span>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors" aria-label="Fechar">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex border-b border-border shrink-0">
          <button
            onClick={() => setActiveTab("new")}
            className={cn(
              "flex items-center gap-1.5 px-5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors",
              activeTab === "new"
                ? "text-primary border-b-2 border-primary -mb-px"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <PenLine className="size-3" />
            Nova mensagem
          </button>
          <button
            onClick={() => setActiveTab("inbox")}
            className={cn(
              "relative flex items-center gap-1.5 px-5 py-2.5 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors",
              activeTab === "inbox"
                ? "text-primary border-b-2 border-primary -mb-px"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Inbox className="size-3" />
            Minhas mensagens
            {repliedCount > 0 && (
              <span className="ml-1 flex size-4 items-center justify-center rounded-full bg-primary font-mono text-[9px] font-bold text-primary-foreground">
                {repliedCount > 9 ? "9+" : repliedCount}
              </span>
            )}
          </button>
        </div>

        <div className="overflow-y-auto flex-1">
          {activeTab === "new" && (
            formStatus === "success" ? (
              <div className="flex flex-col items-center gap-4 px-8 py-12 text-center">
                <CheckCircle2 className="size-10 text-primary" />
                <p className="text-sm text-muted-foreground leading-relaxed">{t("supportModal.success")}</p>
                <button
                  onClick={() => { setFormStatus("idle"); setMessage(""); setSubject(""); setActiveTab("inbox"); }}
                  className="mt-2 rounded-md bg-primary px-5 py-2 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
                >
                  Ver minhas mensagens
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-6 py-5">
                {user && (
                  <p className="font-mono text-[10px] text-muted-foreground">
                    {user.username} · {user.email ?? ""}
                  </p>
                )}

                <div className="flex flex-wrap gap-1.5">
                  {categories.map((c) => (
                    <button
                      key={c.value}
                      type="button"
                      onClick={() => setCategory(c.value)}
                      className={`rounded-full px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-wide transition-colors ${
                        category === c.value
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>

                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {t("supportModal.subject")}
                  </label>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder={t("supportModal.subjectPlaceholder")}
                    maxLength={120}
                    className="w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {t("supportModal.message")}
                  </label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t("supportModal.messagePlaceholder")}
                    rows={5}
                    maxLength={2000}
                    required
                    className="w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                  />
                  <p className="text-right font-mono text-[9px] text-muted-foreground">{message.length}/2000</p>
                </div>

                {formStatus === "error" && (
                  <p className="text-xs text-destructive">{t("supportModal.error")}</p>
                )}

                <button
                  type="submit"
                  disabled={formStatus === "sending" || !message.trim()}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow disabled:opacity-50"
                >
                  {formStatus === "sending" ? t("supportModal.sending") : t("supportModal.send")}
                </button>
              </form>
            )
          )}

          {activeTab === "inbox" && (
            <div className="px-6 py-5 space-y-3">
              {ticketsLoading ? (
                <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  <span className="font-mono text-xs">Carregando…</span>
                </div>
              ) : tickets.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
                  <Inbox className="size-8 opacity-30" />
                  <p className="font-mono text-xs">Nenhuma mensagem enviada ainda.</p>
                </div>
              ) : (
                <>
                  <div className="flex justify-end">
                    <button
                      onClick={() => { if (window.confirm(t("supportModal.confirmClear"))) clearMut.mutate(); }}
                      disabled={clearMut.isPending}
                      className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-destructive disabled:opacity-40"
                    >
                      <Trash2 className="size-3" aria-hidden /> {t("supportModal.clearAll")}
                    </button>
                  </div>
                  {tickets.map((ticket) => (
                    <TicketCard key={ticket.id} ticket={ticket} onDelete={() => delMut.mutate(ticket.id)} />
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
