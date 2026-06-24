import { useEffect, useState } from "react";
import { X, Loader2, Ban } from "lucide-react";
import { toast } from "sonner";
import { subscription, type Invoice } from "@/lib/api";

function fmtDate(s?: string | null) {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return s;
  }
}
function fmtMoney(cents: number, currency = "brl") {
  const v = (cents || 0) / 100;
  return (currency || "brl").toLowerCase() === "brl" ? `R$ ${v.toFixed(2)}` : `$${v.toFixed(2)}`;
}
const STATUS_PT: Record<string, string> = {
  approved: "Pago", paid: "Pago", failed: "Falhou", refunded: "Estornado", pending: "Pendente",
};

/** Gerência da assinatura IN-APP: próxima cobrança + histórico de pagamentos + cancelamento
 *  (agendado pro fim do período, via backend → Stripe). Sem mandar o cliente pro site do Stripe. */
export function SubscriptionModal({ open, onClose, planExpiresAt, onChanged }: {
  open: boolean;
  onClose: () => void;
  planExpiresAt?: string | null;
  onChanged: () => void;
}) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setCancelled(false);
    subscription.invoices()
      .then(r => setInvoices(r.invoices ?? []))
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  const onCancel = async () => {
    if (!window.confirm(
      "Cancelar sua assinatura? Você mantém o Pro até o fim do período já pago; depois ela não renova."
    )) return;
    setCancelLoading(true);
    try {
      const res = await subscription.cancel();
      setCancelled(res.cancel_at_period_end !== false);
      onChanged();
      toast.success(res.cancel_at_period_end
        ? "Assinatura cancelada. Seu Pro segue ativo até o fim do período atual."
        : "Assinatura cancelada.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Não foi possível cancelar a assinatura.");
    } finally {
      setCancelLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-background p-5 shadow-2xl">
        <button
          onClick={onClose}
          aria-label="Fechar"
          className="absolute right-3 top-3 rounded-full bg-background/80 p-1.5 text-muted-foreground ring-1 ring-border transition-colors hover:bg-secondary hover:text-foreground"
        >
          <X className="size-4" />
        </button>
        <h2 className="mb-4 font-mono text-sm font-bold uppercase tracking-widest-2 text-foreground">
          Gerenciar assinatura
        </h2>

        {/* Próxima cobrança / acesso */}
        <div className="mb-4 rounded-lg border border-border/60 bg-hud-surface/40 p-3">
          <p className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
            {cancelled ? "Acesso Pro até" : "Próxima cobrança"}
          </p>
          <p className="mt-0.5 font-mono text-sm font-bold text-foreground">{fmtDate(planExpiresAt)}</p>
          {cancelled && <p className="mt-1 text-[11px] text-amber-400/90">Cancelada, não renova.</p>}
        </div>

        {/* Histórico de pagamentos */}
        <p className="mb-2 font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
          Histórico de pagamentos
        </p>
        <div className="max-h-48 overflow-y-auto rounded-lg border border-border/50">
          {loading ? (
            <div className="flex items-center justify-center py-6 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
            </div>
          ) : invoices.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">Nenhum pagamento ainda.</p>
          ) : (
            <table className="w-full text-xs">
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} className="border-b border-border/40 last:border-0">
                    <td className="px-3 py-2 font-mono text-muted-foreground">{fmtDate(inv.created_at)}</td>
                    <td className="px-3 py-2 font-mono text-foreground">{fmtMoney(inv.amount_cents, inv.currency)}</td>
                    <td className="px-3 py-2 text-right font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      {STATUS_PT[(inv.status || "").toLowerCase()] ?? inv.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Cancelar (com confirmação) */}
        {!cancelled && (
          <button
            onClick={onCancel}
            disabled={cancelLoading}
            className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-md border border-destructive/40 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
          >
            {cancelLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Ban className="size-3.5" />}
            {cancelLoading ? "Cancelando…" : "Cancelar assinatura"}
          </button>
        )}
      </div>
    </div>
  );
}
