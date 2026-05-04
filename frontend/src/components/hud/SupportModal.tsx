import { useState } from "react";
import { X, MessageSquarePlus, CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { request } from "@/lib/api";

interface Props {
  onClose: () => void;
}

type Category = "bug" | "question" | "suggestion" | "billing" | "other";

export function SupportModal({ onClose }: Props) {
  const { t } = useTranslation("common");
  const { user } = useAuth();

  const [category, setCategory] = useState<Category>("question");
  const [subject, setSubject]   = useState("");
  const [message, setMessage]   = useState("");
  const [status, setStatus]     = useState<"idle" | "sending" | "success" | "error">("idle");

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
    setStatus("sending");
    try {
      await request("/support/contact", {
        method: "POST",
        body: JSON.stringify({ category, subject: subject.trim(), message: message.trim() }),
      });
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-hud-surface shadow-elevated flex flex-col">

        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border">
          <div className="flex items-center gap-2">
            <MessageSquarePlus className="size-4 text-primary" />
            <span className="font-mono text-[11px] font-bold uppercase tracking-widest text-foreground">
              {t("supportModal.title")}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Fechar"
          >
            <X className="size-4" />
          </button>
        </div>

        {status === "success" ? (
          <div className="flex flex-col items-center gap-4 px-8 py-12 text-center">
            <CheckCircle2 className="size-10 text-primary" />
            <p className="text-sm text-muted-foreground leading-relaxed">{t("supportModal.success")}</p>
            <button
              onClick={onClose}
              className="mt-2 rounded-md bg-primary px-5 py-2 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
            >
              OK
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

            {status === "error" && (
              <p className="text-xs text-destructive">{t("supportModal.error")}</p>
            )}

            <button
              type="submit"
              disabled={status === "sending" || !message.trim()}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow disabled:opacity-50"
            >
              {status === "sending" ? t("supportModal.sending") : t("supportModal.send")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
