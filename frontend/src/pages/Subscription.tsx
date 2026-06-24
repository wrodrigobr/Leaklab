import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { HudHeader } from "@/components/hud/HudHeader";
import { useAuth } from "@/lib/auth";
import { subscription, type Invoice } from "@/lib/api";

function fmtDate(s?: string | null) {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
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
const STATUS_CLS: Record<string, string> = {
  approved: "text-emerald-400", paid: "text-emerald-400", refunded: "text-amber-400",
  failed: "text-destructive", pending: "text-muted-foreground",
};

/** Tela de gerenciamento da assinatura: visão clara do plano + próxima cobrança + histórico de
 *  pagamentos + cancelamento discreto (confirmação in-page, sem popup, sem ir pro site do Stripe). */
export default function Subscription() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  useEffect(() => {
    subscription.invoices()
      .then(r => setInvoices(r.invoices ?? []))
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false));
  }, []);

  const isPro = user?.plan === "pro";
  const expires = user?.plan_expires_at;

  const onCancel = async () => {
    setCancelLoading(true);
    try {
      const res = await subscription.cancel();
      setCancelled(res.cancel_at_period_end !== false);
      setConfirming(false);
      await refreshUser();
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
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />
      <main className="mx-auto max-w-2xl space-y-6 px-4 py-8">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> Voltar
        </button>

        <h1 className="font-mono text-lg font-bold tracking-wide text-foreground">Minha assinatura</h1>

        {/* Visão geral do plano */}
        <section className="rounded-xl border border-border bg-hud-surface p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">Plano atual</p>
              <p className="mt-1 flex items-center gap-2 font-mono text-xl font-bold text-foreground">
                {isPro && <ShieldCheck className="size-5 text-primary" />}
                {isPro ? "Pro" : "Free"}
              </p>
            </div>
            <span className={`rounded-full px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 ${
              cancelled ? "text-amber-400 ring-amber-400/30 bg-amber-400/10"
              : isPro ? "text-emerald-400 ring-emerald-500/30 bg-emerald-500/10"
              : "text-muted-foreground ring-border"
            }`}>
              {cancelled ? "Cancelamento agendado" : isPro ? "Ativa" : "Gratuito"}
            </span>
          </div>

          {isPro && (
            <div className="mt-4 border-t border-border/60 pt-4">
              <p className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
                {cancelled ? "Acesso Pro até" : "Próxima cobrança"}
              </p>
              <p className="mt-1 font-mono text-sm font-bold text-foreground">{fmtDate(expires)}</p>
              {cancelled && (
                <p className="mt-1 text-[11px] text-amber-400/90">Sua assinatura não vai renovar; depois dessa data a conta volta para o Free.</p>
              )}
            </div>
          )}
        </section>

        {/* Histórico de pagamentos */}
        <section className="space-y-2">
          <h2 className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Histórico de pagamentos
          </h2>
          <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
            {loading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="size-5 animate-spin" />
              </div>
            ) : invoices.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Nenhum pagamento ainda.</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {invoices.map(inv => (
                    <tr key={inv.id} className="border-b border-border/40 last:border-0">
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{fmtDate(inv.created_at)}</td>
                      <td className="px-4 py-3 font-mono text-foreground">{fmtMoney(inv.amount_cents, inv.currency)}</td>
                      <td className={`px-4 py-3 text-right font-mono text-[10px] font-bold uppercase tracking-wide ${STATUS_CLS[(inv.status || "").toLowerCase()] ?? "text-muted-foreground"}`}>
                        {STATUS_PT[(inv.status || "").toLowerCase()] ?? inv.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Cancelamento — discreto, com confirmação in-page */}
        {isPro && !cancelled && (
          <section className="pt-2">
            {!confirming ? (
              <button
                onClick={() => setConfirming(true)}
                className="font-mono text-[11px] text-muted-foreground/60 underline underline-offset-4 transition-colors hover:text-muted-foreground"
              >
                Cancelar assinatura
              </button>
            ) : (
              <div className="space-y-3 rounded-xl border border-border bg-hud-surface/50 p-4">
                <p className="text-sm font-medium text-foreground">Cancelar sua assinatura?</p>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  Seu Pro continua ativo até <strong className="text-foreground">{fmtDate(expires)}</strong>. Depois dessa data, a conta volta para o Free e a assinatura não renova. Você não perde nada agora.
                </p>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => setConfirming(false)}
                    className="rounded-md bg-primary px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90"
                  >
                    Manter assinatura
                  </button>
                  <button
                    onClick={onCancel}
                    disabled={cancelLoading}
                    className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-50"
                  >
                    {cancelLoading && <Loader2 className="size-3.5 animate-spin" />}
                    {cancelLoading ? "Cancelando…" : "Confirmar cancelamento"}
                  </button>
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
