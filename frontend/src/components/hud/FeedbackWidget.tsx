import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MessageSquarePlus, Lightbulb, Heart, AlertCircle, X, Loader2, Check, Send } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { support } from "@/lib/api";
import { cn } from "@/lib/utils";

const NUDGE_KEY = "leaklab_feedback_nudge";
const HIDE_ON = ["/replayer", "/leak-trainer", "/ghost"];   // telas imersivas: não poluir o drill
const NUDGE_AFTER = 3;   // mostra o nudge proativo após N aberturas de tela autenticada

const TYPES = [
  { value: "suggestion", icon: Lightbulb },
  { value: "praise", icon: Heart },
  { value: "problem", icon: AlertCircle },
] as const;

/** Canal de feedback/sugestões do jogador: FAB global + modal + nudge proativo. Grava em support_tickets
 * (reusa support.contact) com category suggestion/praise/problem → aparece na inbox de suporte do admin. */
export function FeedbackWidget() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const { t } = useTranslation("common");
  const [open, setOpen] = useState(false);
  const [nudge, setNudge] = useState(false);
  const [type, setType] = useState<string>("suggestion");
  const [message, setMessage] = useState("");
  const [rating, setRating] = useState(0);
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  // nudge: conta aberturas; ao cruzar o limiar, aparece UMA vez (depois fica só o FAB)
  useEffect(() => {
    if (!user) return;
    try {
      const s = JSON.parse(localStorage.getItem(NUDGE_KEY) || "{}");
      if (s.shown) return;
      const count = (s.count || 0) + 1;
      localStorage.setItem(NUDGE_KEY, JSON.stringify({ ...s, count }));
      if (count >= NUDGE_AFTER) setNudge(true);
    } catch { /* localStorage indisponível: sem nudge, sem quebrar */ }
  }, [user]);

  const markNudgeDone = () => {
    setNudge(false);
    try { localStorage.setItem(NUDGE_KEY, JSON.stringify({ shown: true, count: NUDGE_AFTER })); } catch { /* noop */ }
  };

  if (!user || HIDE_ON.some((p) => pathname.startsWith(p))) return null;

  const submit = async () => {
    if (!message.trim() || status === "sending") return;
    setStatus("sending");
    try {
      const subject = `${t(`feedback.type.${type}`)}${rating ? ` · ${rating}/5` : ""}`;
      await support.contact({ category: type, subject, message: message.trim() });
      setStatus("sent");
      setTimeout(() => {
        setOpen(false); setStatus("idle"); setMessage(""); setRating(0); setType("suggestion");
      }, 1800);
    } catch { setStatus("error"); }
  };

  return (
    <>
      {/* Nudge proativo */}
      {nudge && !open && (
        <div className="fixed bottom-[4.5rem] right-4 z-40 max-w-[260px] animate-fade-in rounded-xl border border-amber-500/40 bg-hud-surface p-3 shadow-xl">
          <button onClick={markNudgeDone} className="absolute right-2 top-2 text-muted-foreground transition-colors hover:text-foreground"><X className="size-3.5" aria-hidden /></button>
          <p className="pr-4 text-xs leading-relaxed text-foreground">{t("feedback.nudge")}</p>
          <button onClick={() => { markNudgeDone(); setOpen(true); }}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-black transition-colors hover:bg-amber-400">
            <Lightbulb className="size-3" aria-hidden /> {t("feedback.nudgeCta")}
          </button>
        </div>
      )}

      {/* FAB */}
      <button onClick={() => { setOpen(true); markNudgeDone(); }} title={t("feedback.title")} aria-label={t("feedback.title")}
        className="fixed bottom-4 right-4 z-40 inline-flex size-12 items-center justify-center rounded-full bg-amber-500 text-black shadow-lg transition-transform hover:scale-105 active:scale-95">
        <MessageSquarePlus className="size-5" aria-hidden />
      </button>

      {/* Modal */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
          onClick={() => status !== "sending" && setOpen(false)}>
          <div className="w-full max-w-md rounded-t-2xl border border-border bg-background p-5 sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
            {status === "sent" ? (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                <Check className="size-10 text-emerald-400" aria-hidden />
                <p className="text-sm text-foreground">{t("feedback.thanks")}</p>
              </div>
            ) : (
              <>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-heading text-lg font-bold text-foreground">{t("feedback.title")}</h2>
                  <button onClick={() => setOpen(false)} className="text-muted-foreground transition-colors hover:text-foreground"><X className="size-5" aria-hidden /></button>
                </div>
                <p className="mb-3 text-xs leading-relaxed text-muted-foreground">{t("feedback.subtitle")}</p>

                <div className="grid grid-cols-3 gap-2">
                  {TYPES.map(({ value, icon: Icon }) => (
                    <button key={value} onClick={() => setType(value)}
                      className={cn("flex flex-col items-center gap-1 rounded-lg border p-2.5 text-[11px] font-medium transition-colors",
                        type === value ? "border-amber-500/60 bg-amber-500/10 text-amber-400" : "border-border text-muted-foreground hover:border-amber-500/40")}>
                      <Icon className="size-4" aria-hidden /> {t(`feedback.type.${value}`)}
                    </button>
                  ))}
                </div>

                <textarea value={message} onChange={(e) => setMessage(e.target.value.slice(0, 2000))}
                  placeholder={t("feedback.placeholder")} rows={4}
                  className="mt-3 w-full resize-none rounded-lg border border-border bg-hud-surface p-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-amber-500" />

                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[11px] text-muted-foreground">{t("feedback.rating")}</span>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} onClick={() => setRating(rating === n ? 0 : n)} aria-label={`${n}/5`}
                      className={cn("text-base leading-none transition-colors", n <= rating ? "text-amber-400" : "text-muted-foreground/40 hover:text-amber-400/60")}>★</button>
                  ))}
                </div>

                {status === "error" && <p className="mt-2 text-[11px] text-destructive">{t("feedback.error")}</p>}

                <button onClick={submit} disabled={!message.trim() || status === "sending"}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400 disabled:opacity-40">
                  {status === "sending" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />} {t("feedback.send")}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
