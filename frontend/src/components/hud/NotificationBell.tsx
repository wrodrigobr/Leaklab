import { useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Bell, Trash2, MessageSquarePlus } from "lucide-react";
import { cn } from "@/lib/utils";
import { notifications as notifApi, NotificationItem } from "@/lib/api";

const TYPE_ICON: Record<string, string> = {
  elo_band_up: "🏅",
  elo_band_down: "📉",
  coach_message: "💬",
  student_message: "💬",
  achievement: "⭐",
  coach_annotation: "✍️",
  admin_message: "📣",
  admin_broadcast: "📣",
};

interface NotificationBellProps {
  /** Atalhos de conversa (chat coach / suporte) renderizados no topo do dropdown.
      Recebe `close` p/ fechar o painel ao abrir um modal/drawer. */
  renderActions?: (close: () => void) => ReactNode;
  /** Não-lidas externas (mensagens do coach + respostas de suporte) somadas ao badge. */
  extraUnread?: number;
}

export function NotificationBell({ renderActions, extraUnread = 0 }: NotificationBellProps = {}) {
  const { t } = useTranslation("common");
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(() => {
    notifApi.unreadCount().then((r) => setUnread(r.unread)).catch(() => {});
  }, []);

  // Poll do contador (cache-warm: 270s para não estourar o cache da sessão)
  useEffect(() => {
    refreshCount();
    const id = setInterval(refreshCount, 60_000);
    return () => clearInterval(id);
  }, [refreshCount]);

  // Fechar ao clicar fora
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      notifApi.list().then((r) => setItems(r.notifications)).catch(() => {});
      if (unread > 0) {
        notifApi.markAllRead().then(() => setUnread(0)).catch(() => {});
      }
    }
  };

  const totalUnread = unread + (extraUnread || 0);

  // Clicar numa notificação: navega (se tiver link), dispensa (remove) e tira da lista —
  // assim a lista não cresce indefinidamente.
  const onItemClick = (n: NotificationItem) => {
    setItems((prev) => prev.filter((x) => x.id !== n.id));
    notifApi.dismiss(n.id).catch(() => {});
    if (n.link) navigate(n.link);
    setOpen(false);
  };

  const clearAll = () => {
    setItems([]);
    setUnread(0);
    notifApi.dismissAll().catch(() => {});
  };

  const renderText = (n: NotificationItem): string => {
    const p = n.payload as { band?: string; delta?: number; title?: string; body?: string };
    switch (n.type) {
      case "elo_band_up":    return t("notifications.eloBandUp", { band: p.band, delta: p.delta });
      case "elo_band_down":  return t("notifications.eloBandDown", { band: p.band, delta: p.delta });
      case "coach_message":  return t("notifications.coachMessage");
      case "student_message":return t("notifications.studentMessage");
      case "achievement":    return t("notifications.achievement", { title: p.title });
      case "coach_annotation": return t("notifications.coachAnnotation");
      case "admin_message":
      case "admin_broadcast": return p.title || p.body || t("notifications.adminMessage");
      default:               return n.type;
    }
  };
  // corpo opcional (subtítulo) — usado nas mensagens do admin (título + corpo)
  const renderBody = (n: NotificationItem): string | null => {
    const p = n.payload as { title?: string; body?: string };
    if ((n.type === "admin_message" || n.type === "admin_broadcast") && p.title && p.body) return p.body;
    return null;
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        aria-label={t("notifications.title")}
        className="relative inline-flex items-center justify-center size-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
      >
        <Bell className="size-4" />
        {totalUnread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground flex items-center justify-center">
            {totalUnread > 9 ? "9+" : totalUnread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-72 max-h-[28rem] overflow-y-auto rounded-xl border border-border bg-hud-surface shadow-lg z-50">
          {/* Atalhos de conversa (chat coach / suporte) */}
          {renderActions && (
            <div className="p-1.5 border-b border-border">
              {renderActions(() => setOpen(false))}
            </div>
          )}
          {/* Sugestões e feedback (abre o modal do FeedbackWidget via evento global) */}
          <button
            onClick={() => { setOpen(false); window.dispatchEvent(new Event("leaklab:open-feedback")); }}
            className="flex w-full items-center gap-2 border-b border-border px-3 py-2.5 text-left text-[12px] text-foreground transition-colors hover:bg-primary/5"
          >
            <MessageSquarePlus className="size-4 shrink-0 text-amber-400" aria-hidden />
            {t("feedback.title")}
          </button>
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              {t("notifications.title")}
            </span>
            {items.length > 0 && (
              <button
                onClick={clearAll}
                className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-muted-foreground hover:text-destructive transition-colors"
              >
                <Trash2 className="size-3" /> {t("notifications.clearAll")}
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">{t("notifications.empty")}</p>
          ) : (
            <ul className="divide-y divide-border/50">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => onItemClick(n)}
                    className={cn(
                      "w-full flex items-start gap-2 px-3 py-2.5 text-left hover:bg-primary/5 transition-colors",
                      !n.read && "bg-primary/[0.04]"
                    )}
                  >
                    <span className="text-base leading-none mt-0.5">{TYPE_ICON[n.type] ?? "🔔"}</span>
                    <span className="flex-1 min-w-0">
                      <span className="block text-[12px] text-foreground leading-snug">{renderText(n)}</span>
                      {renderBody(n) && (
                        <span className="mt-0.5 block text-[11px] text-muted-foreground leading-snug">{renderBody(n)}</span>
                      )}
                    </span>
                    {!n.read && <span className="size-1.5 rounded-full bg-primary shrink-0 mt-1.5" />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
